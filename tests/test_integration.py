from __future__ import annotations

import json

from weekglass.cli import analyze, main
from weekglass.config import load_config

from .conftest import make_config, simple_ics, vevent


def test_empty_calendar_produces_empty_week(tmp_path, capsys):
    path = tmp_path / "empty.ics"
    path.write_text("BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Empty//EN\nEND:VCALENDAR\n")
    cfg = make_config()
    report, suggestions, _plan = analyze([str(path)], cfg)
    assert report.metrics.event_count == 0
    assert report.metrics.available_minutes == 2400
    assert len(report.days) == 5
    assert len(suggestions) == 3
    assert report.sources[0].events_total == 0
    assert any(w.code == "empty_week" for w in report.warnings)

    code = main(["audit", str(path), "--week", "2026-10-26", "--json", "-", "--quiet"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["metrics"]["event_count"] == 0
    assert any(w["code"] == "empty_week" for w in payload["warnings"])


def test_multi_day_all_day_event_only_occupies_its_days(tmp_path):
    path = simple_ics(
        tmp_path,
        "all-day.ics",
        """BEGIN:VEVENT
UID:holiday
DTSTAMP:20261001T000000Z
DTSTART;VALUE=DATE:20261026
DTEND;VALUE=DATE:20261028
SUMMARY:两天假期
END:VEVENT""",
    )
    cfg = make_config(env={"WEEKGLASS_ALL_DAY_BUSY": "1"})
    report, _suggestions, _plan = analyze([str(path)], cfg)
    assert report.days[0].available_minutes == 480
    assert report.days[0].busy_minutes == 480
    assert report.days[1].busy_minutes == 480
    assert report.days[2].busy_minutes == 0
    assert report.metrics.all_day_events == 1


def test_include_weekend_cli(tmp_path):
    path = simple_ics(tmp_path, "work.ics", vevent(uid="a", start="20261026T100000", end="20261026T110000"))
    cfg = load_config(
        {"WEEKGLASS_TZ": "Asia/Shanghai", "WEEKGLASS_NOW": "2026-10-29T18:00:00+08:00"},
        cli={"include_weekend": True, "week": "2026-10-26"},
    )
    report, _s, _p = analyze([str(path)], cfg)
    assert len(report.days) == 7
    assert report.days[-1].weekday == "周日"


def test_transparent_all_day_does_not_occupy_even_with_flag(tmp_path):
    path = simple_ics(
        tmp_path,
        "transparent.ics",
        """BEGIN:VEVENT
UID:transparent
DTSTAMP:20261001T000000Z
DTSTART;VALUE=DATE:20261028
DTEND;VALUE=DATE:20261029
TRANSP:TRANSPARENT
SUMMARY:不占用的全天
END:VEVENT""",
    )
    cfg = make_config(env={"WEEKGLASS_ALL_DAY_BUSY": "1"})
    report, _suggestions, _plan = analyze([str(path)], cfg)
    assert report.metrics.all_day_events == 1
    assert report.days[2].all_day_events == 1
    assert report.days[2].busy_minutes == 0
