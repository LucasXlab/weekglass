from __future__ import annotations

import json

from weekglass.cli import analyze
from weekglass.report import build_view, render_html, render_json

from .conftest import calendar, make_config, simple_ics, vevent


def make_report(tmp_path, *, summary="周会", location="会议室"):
    path = simple_ics(
        tmp_path,
        "work.ics",
        vevent(uid="a", start="20261026T100000", end="20261026T110000", summary=summary, extra=f"LOCATION:{location}"),
        vevent(uid="b", start="20261026T140000", end="20261026T150000", summary="评审"),
    )
    cfg = make_config()
    report, suggestions, _plan = analyze([str(path)], cfg, "focus.ics")
    return cfg, report, suggestions


def test_json_schema_and_status(tmp_path):
    cfg, report, _suggestions = make_report(tmp_path)
    payload = json.loads(render_json(report))
    assert payload["schema_version"] == 1
    assert payload["tool"] == {"name": "weekglass", "version": "0.1.0"}
    assert payload["week"] == {
        "iso": "2026-W44",
        "start": "2026-10-26",
        "end": "2026-11-01",
        "analyzed_days": 5,
        "timezone": "Asia/Shanghai",
    }
    assert payload["plan_path"] == "focus.ics"
    assert payload["events"][0]["status"] in {"confirmed", "tentative"}
    assert payload["events"][0]["transparency"] in {"opaque", "transparent"}
    assert isinstance(payload["metrics"]["busy_pct"], float)
    assert payload["suggestions"]
    assert payload["sources"][0]["path"].endswith("work.ics")
    assert render_json(report).endswith("\n")


def test_html_contains_numbers_and_no_absolute_path(tmp_path):
    cfg, report, _suggestions = make_report(tmp_path)
    html = render_html(report, cfg, "focus.ics")
    assert "2026-W44" in html
    assert "完整专注" in html
    assert "Content-Security-Policy" in html
    assert "default-src 'none'" in html
    assert "focus.ics" in html
    assert str(tmp_path) not in html
    assert "http://" not in html
    assert "https://" not in html
    assert "prefers-color-scheme" in html
    assert "@media (max-width: 760px)" in html


def test_html_escapes_xss(tmp_path):
    cfg, report, _suggestions = make_report(
        tmp_path,
        summary="<script>alert(1)</script>",
        location='<img src=x onerror="alert(2)">',
    )
    html = render_html(report, cfg, None)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<img src=x" not in html
    assert "&lt;img" in html


def test_view_labels_and_metrics(tmp_path):
    cfg, report, suggestions = make_report(tmp_path)
    view = build_view(report, cfg, "focus.ics")
    assert view["days_label"] == "5 个工作日"
    assert view["max_per_day"] == 1
    assert len(view["days"]) == 5
    assert view["metrics"]["busy"] == "2 小时"
    assert view["suggestions"][0]["rank"] == 1
    assert view["plan_file"] == "focus.ics"


def test_html_without_suggestions_and_with_warning(tmp_path):
    path = simple_ics(
        tmp_path,
        "full.ics",
        *[
            vevent(uid=f"e{day}", start=f"202610{day}T090000", end=f"202610{day}T180000", summary="占满")
            for day in range(26, 31)
        ],
    )
    cfg = make_config()
    report, suggestions, _plan = analyze([str(path)], cfg, "focus.ics")
    assert suggestions == []
    html = render_html(report, cfg, None)
    assert "没有 ≥ 90 分钟的连续空闲" in html
    assert "本次没有生成 .ics 文件" in html
