from __future__ import annotations

import pytest

from weekglass.formatting import round1
from weekglass.metrics import compute_day, compute_metrics

from .conftest import at, make_config, make_event


def metrics(events, cfg=None, *, duplicates=0, cancelled=0, transparent=0):
    cfg = cfg or make_config()
    return compute_metrics(events, cfg, duplicates=duplicates, cancelled=cancelled, transparent=transparent)


def day(events, day_number=26, cfg=None):
    return compute_day(at(day_number, 0), events, cfg or make_config())


def test_empty_week_has_two_blocks_per_day():
    m, days = metrics([])
    assert m.available_minutes == 2400
    assert m.busy_minutes == 0
    assert m.free_minutes == 2400
    assert m.focus_minutes == 2400
    assert m.fragmented_minutes == 0
    assert m.focus_blocks == 10
    assert m.fragments == 0
    assert m.longest_focus_minutes == 300
    assert m.busy_pct == 0.0
    assert m.fragmentation_pct == 0.0
    assert len(days) == 5


def test_full_day_busy_and_percentages():
    events = [make_event(at(day, 9), at(day, 18), summary=f"整天{day}") for day in range(26, 31)]
    m, days = metrics(events)
    assert days[0].available_minutes == 480
    assert days[0].busy_minutes == 480
    assert days[0].free_minutes == 0
    assert days[0].focus_minutes == 0
    assert days[0].fragmented_minutes == 0
    assert days[0].busy_pct == 100.0
    assert m.fragmentation_pct == 0.0
    assert m.focus_pct == 0.0


def test_90_minutes_is_focus_and_89_is_fragment():
    busy = [make_event(at(26, 10, 30), at(26, 12)), make_event(at(26, 13), at(26, 18))]
    m, days = metrics(busy)
    assert days[0].free_minutes == 90
    assert days[0].focus_minutes == 90
    assert days[0].fragmented_minutes == 0
    assert days[0].focus_blocks == 1
    assert days[0].fragments == 0

    busy_89 = [make_event(at(26, 10, 29), at(26, 12)), make_event(at(26, 13), at(26, 18))]
    m, days = metrics(busy_89)
    assert days[0].free_minutes == 89
    assert days[0].focus_minutes == 0
    assert days[0].fragmented_minutes == 89
    assert days[0].focus_blocks == 0
    assert days[0].fragments == 1
    assert m.fragmentation_pct == 4.4


def test_lunch_is_removed_and_meeting_at_lunch_does_not_inflate_busy():
    events = [make_event(at(26, 12, 15), at(26, 12, 45), summary="午休会")]
    m, days = metrics(events)
    assert days[0].available_minutes == 480
    assert days[0].busy_minutes == 0
    assert days[0].focus_minutes == 480
    assert days[0].focus_blocks == 2

    cfg = make_config(cli={"lunch": (None, None)})
    m, days = metrics(events, cfg)
    assert days[0].available_minutes == 540
    assert days[0].busy_minutes == 30
    assert days[0].focus_minutes == 510


def test_overlap_merge_and_busy_blocks():
    events = [
        make_event(at(26, 9), at(26, 11), summary="A"),
        make_event(at(26, 10), at(26, 12), summary="B"),
    ]
    m, days = metrics(events)
    assert days[0].busy_minutes == 180
    assert days[0].busy_blocks == 1
    assert days[0].free_minutes == 300
    assert days[0].focus_minutes == 300


def test_buffer_expands_timed_events():
    events = [make_event(at(26, 10), at(26, 10, 30), summary="A")]
    cfg = make_config(env={"WEEKGLASS_BUFFER_MINUTES": "10"})
    m, days = metrics(events, cfg)
    assert days[0].busy_minutes == 50
    assert days[0].free_minutes == 430
    assert days[0].focus_minutes == 300
    assert days[0].fragmented_minutes == 130
    assert days[0].fragments == 2


def test_back_to_back_pairs():
    events = [
        make_event(at(26, 10), at(26, 10, 30), summary="A"),
        make_event(at(26, 10, 30), at(26, 11), summary="B"),
        make_event(at(26, 11, 5), at(26, 11, 30), summary="C"),
        make_event(at(26, 11, 36), at(26, 12), summary="D"),
    ]
    m, _days = metrics(events)
    assert m.back_to_back_pairs == 2


def test_after_hours_weekend_and_all_day():
    events = [
        make_event(at(26, 8), at(26, 9), summary="早"),
        make_event(at(26, 18), at(26, 19), summary="晚"),
        make_event(at(31, 10), at(31, 11), summary="周六"),
    ]
    m, days = metrics(events)
    assert days[0].after_hours_minutes == 120
    assert m.after_hours_minutes == 120
    assert m.weekend_minutes == 60

    all_day = [make_event(at(26, 0), at(27, 0), summary="全天", all_day=True, busy=False)]
    m, days = metrics(all_day)
    assert days[0].busy_minutes == 0
    assert days[0].all_day_events == 1
    cfg = make_config(env={"WEEKGLASS_ALL_DAY_BUSY": "1"})
    m, days = metrics(all_day, cfg)
    assert days[0].busy_minutes == 480
    assert days[0].free_minutes == 0
    assert days[1].busy_minutes == 0


def test_include_weekend_changes_available_days():
    cfg = make_config(cli={"include_weekend": True})
    m, days = metrics([], cfg)
    assert len(days) == 7
    assert m.available_minutes == 3360
    assert days[-1].weekday == "周日"


def test_counts_are_passed_through_and_focus_plus_fragment_equals_free():
    events = [make_event(at(26, 10), at(26, 11), summary="A")]
    m, days = metrics(events, duplicates=2, cancelled=3, transparent=4)
    assert m.duplicate_events == 2
    assert m.cancelled_events == 3
    assert m.transparent_events == 4
    assert m.event_count == 1
    for d in days:
        assert d.focus_minutes + d.fragmented_minutes == d.free_minutes


def test_round_half_up():
    assert round1(2.25) == 2.3
    assert round1(2.35) == 2.4
    assert round1(0) == 0.0
