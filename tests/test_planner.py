from __future__ import annotations

from datetime import timedelta

import pytest
from icalendar import Calendar

from weekglass.errors import NoSuggestionsError
from weekglass.metrics import compute_metrics, suggest_focus_blocks
from weekglass.planner import build_plan

from .conftest import at, make_config, make_event


def plan_for(events, cfg=None):
    cfg = cfg or make_config()
    _m, days = compute_metrics(events, cfg, duplicates=0, cancelled=0, transparent=0)
    items = suggest_focus_blocks(days, events, cfg)
    return cfg, items, build_plan(items, cfg)


def test_plan_roundtrip_and_fields():
    cfg, items, text = plan_for([])
    assert len(items) == 3
    assert "\r\n" in text
    calendar = Calendar.from_ical(text)
    events = calendar.walk("VEVENT")
    assert len(events) == 3
    assert str(calendar.get("PRODID")).startswith("-//Weekglass//Focus Plan")
    assert str(calendar.get("X-WR-CALNAME")) == "Weekglass 专注计划 2026-W44"

    first = events[0]
    assert str(first.get("SUMMARY")) == "专注块 · Weekglass"
    assert str(first.get("STATUS")) == "CONFIRMED"
    assert str(first.get("TRANSP")) == "OPAQUE"
    assert str(first.get("X-WEEKGLASS-TZ")) == "Asia/Shanghai"
    assert [str(c) for c in first.get("CATEGORIES").cats] == ["专注"]
    start = first.get("DTSTART").dt
    assert start.utcoffset() == timedelta(0)
    assert start.isoformat() == "2026-10-27T01:00:00+00:00"
    assert str(first.get("UID")).startswith("weekglass-")
    assert "导入前请确认" in str(first.get("DESCRIPTION"))
    assert first.get("DTSTAMP").dt.isoformat() == "2026-10-29T10:00:00+00:00"


def test_plan_is_deterministic():
    cfg, _items, first = plan_for([])
    _cfg, _items, second = plan_for([])
    assert first == second
    cfg2 = make_config(cli={"now": "2026-10-29T19:00:00+08:00"})
    _c, _i, third = plan_for([], cfg2)
    assert third != first


def test_plan_uids_are_unique_and_rank_sensitive():
    cfg = make_config(env={"WEEKGLASS_MAX_SUGGESTIONS": "3"})
    _m, days = compute_metrics([], cfg, duplicates=0, cancelled=0, transparent=0)
    items = suggest_focus_blocks(days, [], cfg)
    text = build_plan(items, cfg)
    calendar = Calendar.from_ical(text)
    uids = [str(e.get("UID")) for e in calendar.walk("VEVENT")]
    assert len(uids) == len(set(uids))
    moved = items[:]
    moved[0].rank = 99
    reformatted = build_plan(moved, cfg)
    calendar2 = Calendar.from_ical(reformatted)
    uids2 = [str(e.get("UID")) for e in calendar2.walk("VEVENT")]
    assert uids[0] != uids2[0]


def test_plan_without_suggestions_raises():
    cfg = make_config()
    with pytest.raises(NoSuggestionsError) as exc:
        build_plan([], cfg)
    assert exc.value.exit_code == 5
