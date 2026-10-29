from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

import pytest
from icalendar import Calendar

from weekglass.cli import main

from .conftest import NOW, calendar, make_config, simple_ics, vevent


def run(capsys, *args: str):
    code = main(list(args))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def work_calendar(tmp_path: Path) -> Path:
    return simple_ics(
        tmp_path,
        "work.ics",
        vevent(uid="meeting", start="20261026T100000", end="20261026T110000", summary="周会"),
        vevent(uid="review", start="20261026T140000", end="20261026T150000", summary="评审"),
    )


def full_week_calendar(tmp_path: Path) -> Path:
    return simple_ics(
        tmp_path,
        "full.ics",
        *[
            vevent(uid=f"e{day}", start=f"202610{day}T090000", end=f"202610{day}T180000", summary="占满")
            for day in range(26, 31)
        ],
    )


def test_version_and_help(capsys):
    code, out, err = run(capsys, "version")
    assert code == 0 and out == "weekglass 0.1.0\n" and err == ""

    code, out, _err = run(capsys, "version", "--json")
    assert code == 0
    assert json.loads(out) == {"name": "weekglass", "version": "0.1.0", "schema_version": 1}

    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "0.1.0" in captured.out


def test_audit_outputs_all_formats(tmp_path, capsys):
    work = work_calendar(tmp_path)
    json_path = tmp_path / "report.json"
    html_path = tmp_path / "report.html"
    plan_path = tmp_path / "focus.ics"
    code, out, err = run(
        capsys,
        "audit",
        str(work),
        "--week",
        "2026-10-26",
        "--json",
        str(json_path),
        "--html",
        str(html_path),
        "--plan-out",
        str(plan_path),
    )
    assert code == 0, err
    assert "Weekglass 0.1.0" in out
    assert "完整专注" in out
    assert json_path.exists() and html_path.exists() and plan_path.exists()
    payload = json.loads(json_path.read_text())
    assert payload["week"]["iso"] == "2026-W44"
    assert payload["plan_path"] == str(plan_path)
    assert Calendar.from_ical(plan_path.read_text()).walk("VEVENT")


def test_audit_quiet_and_stdout_json(tmp_path, capsys):
    work = work_calendar(tmp_path)
    code, out, err = run(capsys, "audit", str(work), "--week", "2026-10-26", "--quiet", "--json", "-")
    assert code == 0 and err == ""
    assert out.startswith("{")
    json.loads(out)


def test_audit_stdout_html(tmp_path, capsys):
    work = work_calendar(tmp_path)
    code, out, err = run(capsys, "audit", str(work), "--week", "2026-10-26", "--html", "-")
    assert code == 0 and err == ""
    assert out.startswith("<!doctype html>")
    assert "<html" in out


def test_audit_stdout_plan_only(tmp_path, capsys):
    work = work_calendar(tmp_path)
    code, out, err = run(capsys, "audit", str(work), "--week", "2026-10-26", "--plan-out", "-")
    assert code == 0 and err == ""
    assert out.startswith("BEGIN:VCALENDAR")
    assert "Weekglass 0.1.0 ·" not in out


def test_audit_no_suggestions_still_succeeds_without_plan(tmp_path, capsys):
    full = full_week_calendar(tmp_path)
    plan_path = tmp_path / "focus.ics"
    code, out, err = run(capsys, "audit", str(full), "--week", "2026-10-26", "--plan-out", str(plan_path))
    assert code == 0
    assert "没有 ≥ 90 分钟" in out
    assert not plan_path.exists()


def test_plan_success_and_no_suggestions(tmp_path, capsys):
    work = work_calendar(tmp_path)
    out_path = tmp_path / "focus.ics"
    code, out, err = run(capsys, "plan", str(work), "--week", "2026-10-26", "--out", str(out_path))
    assert code == 0 and err == ""
    assert "已写入" in out
    assert out_path.exists()

    full = full_week_calendar(tmp_path)
    no_path = tmp_path / "none.ics"
    code, out, err = run(capsys, "plan", str(full), "--week", "2026-10-26", "--out", str(no_path))
    assert code == 5
    assert "no_suggestions" in err
    assert not no_path.exists()

    code, out, err = run(capsys, "plan", str(full), "--week", "2026-10-26", "--out", "-")
    assert code == 5 and out == ""
    assert "no_suggestions" in err


def test_plan_json_stdout_and_out_file(tmp_path, capsys):
    work = work_calendar(tmp_path)
    out_path = tmp_path / "focus.ics"
    code, out, err = run(
        capsys,
        "plan",
        str(work),
        "--week",
        "2026-10-26",
        "--out",
        str(out_path),
        "--json",
        "-",
    )
    assert code == 0
    payload = json.loads(out)
    assert payload["week"]["iso"] == "2026-W44"
    assert payload["suggestions"][0]["rank"] == 1
    assert "已写入" not in out
    assert out_path.exists()


def test_plan_two_stdout_outputs(tmp_path, capsys):
    work = work_calendar(tmp_path)
    code, _out, err = run(capsys, "plan", str(work), "--week", "2026-10-26", "--out", "-", "--json", "-")
    assert code == 2
    assert "two_stdout_outputs" in err


def test_duplicate_outputs_and_two_stdout_audit(tmp_path, capsys):
    work = work_calendar(tmp_path)
    same = tmp_path / "same.json"
    code, _out, err = run(capsys, "audit", str(work), "--week", "2026-10-26", "--json", str(same), "--html", str(same))
    assert code == 2
    assert "duplicate_output" in err

    code, _out, err = run(capsys, "audit", str(work), "--week", "2026-10-26", "--json", "-", "--html", "-")
    assert code == 2
    assert "two_stdout_outputs" in err


def test_overwrite_requires_force(tmp_path, capsys):
    work = work_calendar(tmp_path)
    path = tmp_path / "report.json"
    path.write_text("old")
    code, _out, err = run(capsys, "audit", str(work), "--week", "2026-10-26", "--json", str(path), "--quiet")
    assert code == 6
    assert "output_exists" in err

    code, _out, err = run(capsys, "audit", str(work), "--week", "2026-10-26", "--json", str(path), "--force", "--quiet")
    assert code == 0
    assert json.loads(path.read_text())["week"]["iso"] == "2026-W44"


def test_parent_directories_are_created(tmp_path, capsys):
    work = work_calendar(tmp_path)
    path = tmp_path / "nested" / "deep" / "report.json"
    code, _out, err = run(capsys, "audit", str(work), "--week", "2026-10-26", "--json", str(path), "--quiet")
    assert code == 0
    assert path.exists()


def test_errors_have_exit_codes(tmp_path, capsys):
    work = work_calendar(tmp_path)
    missing = tmp_path / "missing.ics"
    code, _out, err = run(capsys, "audit", str(missing), "--week", "2026-10-26")
    assert code == 3
    assert "file_unreadable" in err

    bad = tmp_path / "bad.ics"
    bad.write_text("not an ics")
    code, _out, err = run(capsys, "audit", str(bad), "--week", "2026-10-26")
    assert code == 4
    assert "invalid_ics" in err

    code, _out, err = run(capsys, "audit", str(work), "--week", "2026-1-1")
    assert code == 2
    assert "bad_week" in err

    code, _out, err = run(capsys, "audit", str(work), "--week", "2026-10-26", "--min-focus", "481")
    assert code == 2
    assert "min-focus" in err


def test_invalid_env_exit_8(tmp_path, capsys, monkeypatch):
    work = work_calendar(tmp_path)
    monkeypatch.setenv("WEEKGLASS_MIN_FOCUS_MINUTES", "999")
    code, _out, err = run(capsys, "audit", str(work), "--week", "2026-10-26")
    assert code == 8
    assert "WEEKGLASS_MIN_FOCUS_MINUTES" in err


def test_input_file_is_never_modified(tmp_path, capsys):
    work = work_calendar(tmp_path)
    before = hashlib.sha256(work.read_bytes()).hexdigest()
    code, _out, err = run(capsys, "audit", str(work), "--week", "2026-10-26", "--json", "-", "--quiet")
    assert code == 0, err
    after = hashlib.sha256(work.read_bytes()).hexdigest()
    assert before == after


def test_demo_and_force(tmp_path, capsys):
    out = tmp_path / "demo"
    code, text, err = run(capsys, "demo", "--out", str(out), "--now", NOW.isoformat())
    assert code == 0, err
    for name in ("work.ics", "personal.ics", "focus.ics", "report.json", "report.html"):
        assert (out / name).exists(), name
    payload = json.loads((out / "report.json").read_text())
    assert payload["generated_at"] == NOW.isoformat()
    assert payload["week"]["iso"] == "2026-W44"

    code, text, err = run(capsys, "demo", "--out", str(out))
    assert code == 6
    assert "output_exists" in err

    code, text, err = run(capsys, "demo", "--out", str(out), "--force", "--quiet", "--now", NOW.isoformat())
    assert code == 0 and text == ""


def test_demo_deterministic(tmp_path, capsys):
    out = tmp_path / "demo"
    run(capsys, "demo", "--out", str(out), "--now", NOW.isoformat(), "--quiet")
    first = {name: (out / name).read_bytes() for name in ("report.json", "report.html", "focus.ics")}
    run(capsys, "demo", "--out", str(out), "--now", NOW.isoformat(), "--quiet", "--force")
    for name, content in first.items():
        assert (out / name).read_bytes() == content, name


def test_max_report_events_truncates(tmp_path, capsys, monkeypatch):
    events = [
        vevent(uid=f"e{i}", start="20261026T100000", end="20261026T110000", summary=f"事件{i}")
        for i in range(101)
    ]
    path = simple_ics(tmp_path, "many.ics", *events)
    monkeypatch.setenv("WEEKGLASS_MAX_REPORT_EVENTS", "100")
    code, out, err = run(capsys, "audit", str(path), "--week", "2026-10-26", "--json", "-", "--quiet")
    assert code == 0, err
    payload = json.loads(out)
    assert len(payload["events"]) == 100
    assert payload["metrics"]["event_count"] == 101
    assert any(w["code"] == "report_truncated" for w in payload["warnings"])


def test_concurrent_atomic_writes(tmp_path):
    from weekglass.outputs import write_text

    target = tmp_path / "same.txt"
    payloads = [("A" * 1000) + str(i) for i in range(8)]

    def worker(payload: str):
        write_text(str(target), payload, force=True)

    threads = [threading.Thread(target=worker, args=(payload,)) for payload in payloads]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert target.read_text() in payloads


def test_max_per_day_and_config_flags(tmp_path, capsys):
    work = work_calendar(tmp_path)
    code, out, err = run(
        capsys,
        "audit",
        str(work),
        "--week",
        "2026-10-26",
        "--max-per-day",
        "2",
        "--max-suggestions",
        "10",
        "--json",
        "-",
        "--quiet",
    )
    assert code == 0, err
    payload = json.loads(out)
    assert len(payload["suggestions"]) == 9
    assert payload["settings"]["max_per_day"] == 2
