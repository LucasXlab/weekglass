from __future__ import annotations

from weekglass.metrics import compute_metrics, suggest_focus_blocks

from .conftest import at, make_config, make_event


def suggestions(events, cfg=None):
    cfg = cfg or make_config()
    _metrics, days = compute_metrics(events, cfg, duplicates=0, cancelled=0, transparent=0)
    return suggest_focus_blocks(days, events, cfg)


def fmt(s):
    return f"{s.weekday} {s.start:%H:%M}-{s.end:%H:%M} {s.minutes}"


def busy_other_days(keep: int = 26):
    return [make_event(at(day, 9), at(day, 18), summary=f"占满{day}") for day in range(26, 31) if day != keep]


def test_default_prefers_morning_and_midweek():
    result = suggestions([])
    assert [fmt(s) for s in result] == [
        "周二 09:00-12:00 180",
        "周三 09:00-12:00 180",
        "周四 09:00-12:00 180",
    ]
    assert [s.rank for s in result] == [1, 2, 3]


def test_90_minute_block():
    events = [make_event(at(26, 10, 30), at(26, 12)), make_event(at(26, 13), at(26, 18)), *busy_other_days()]
    result = suggestions(events)
    assert len(result) == 1
    assert result[0].start.strftime("%H:%M") == "09:00"
    assert result[0].minutes == 90
    assert result[0].end.strftime("%H:%M") == "10:30"


def test_grid_alignment_ceil_and_floor():
    events = [
        make_event(at(26, 9, 7), at(26, 9, 8)),
        make_event(at(26, 10, 50), at(26, 12)),
        make_event(at(26, 13), at(26, 18)),
        *busy_other_days(),
    ]
    result = suggestions(events)
    # Free 09:08-10:50; ceil to 09:15, floor to 10:45 => 90 minutes.
    assert result[0].start.strftime("%H:%M") == "09:15"
    assert result[0].end.strftime("%H:%M") == "10:45"
    assert result[0].minutes == 90


def test_cap_and_larger_min_focus():
    events = [make_event(at(day, 9), at(day, 18), summary=f"占满{day}") for day in range(26, 31)]
    # Busy 09:00-18:00 leaves nothing.
    assert suggestions(events) == []

    events = [make_event(at(26, 9), at(26, 13)), *busy_other_days()]
    result = suggestions(events)
    # Free 13:00-18:00 = 300 -> capped at 180.
    assert result[0].start.strftime("%H:%M") == "13:00"
    assert result[0].end.strftime("%H:%M") == "16:00"
    assert result[0].minutes == 180

    cfg = make_config(env={"WEEKGLASS_MIN_FOCUS_MINUTES": "240"})
    result = suggestions(events, cfg)
    assert result[0].start.strftime("%H:%M") == "13:00"
    assert result[0].end.strftime("%H:%M") == "17:00"
    assert result[0].minutes == 240


def test_max_suggestions_and_max_per_day():
    assert suggestions([], make_config(env={"WEEKGLASS_MAX_SUGGESTIONS": "0"})) == []
    result = suggestions([], make_config(env={"WEEKGLASS_MAX_SUGGESTIONS": "2"}))
    assert len(result) == 2

    result = suggestions(
        [],
        make_config(env={"WEEKGLASS_MAX_SUGGESTIONS": "10", "WEEKGLASS_MAX_PER_DAY": "2"}),
    )
    assert len(result) == 10
    counts: dict[str, int] = {}
    for item in result:
        counts[item.weekday] = counts.get(item.weekday, 0) + 1
    assert all(value == 2 for value in counts.values())


def test_no_suggestions_when_min_focus_is_whole_day():
    cfg = make_config(env={"WEEKGLASS_MIN_FOCUS_MINUTES": "480"})
    assert suggestions([], cfg) == []


def test_suggestion_reason_and_no_overlap():
    events = [make_event(at(26, 10), at(26, 11), summary="会议")]
    result = suggestions(events)
    for item in result:
        assert "连续空闲" in item.reason
        assert item.start < item.end
        for event in events:
            assert not (item.start < event.end and event.start < item.end)


def test_rank_is_contiguous():
    result = suggestions([], make_config(env={"WEEKGLASS_MAX_SUGGESTIONS": "4"}))
    assert [s.rank for s in result] == [1, 2, 3, 4]
