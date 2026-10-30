from __future__ import annotations

from dataclasses import replace

import pytest

from weekglass.config import load_config
from weekglass.errors import CalendarError, InputError
from weekglass.ics import load_events

from .conftest import NOW, calendar, make_config, simple_ics, vevent, write_ics


def load(tmp_path, body: str, cfg=None, name="one.ics"):
    path = write_ics(tmp_path, name, body)
    return load_events([str(path)], cfg or make_config())


def test_timed_all_day_and_tentative(tmp_path):
    body = calendar(
        vevent(uid="a", start="20261026T100000", end="20261026T110000", summary="会议"),
        vevent(uid="b", start="20261028", end="20261029", summary="全天", all_day=True),
        vevent(uid="c", start="20261026T140000", end="20261026T150000", summary="暂定", extra="STATUS:TENTATIVE"),
    )
    sources, events, warnings, duplicates, cancelled, transparent = load(tmp_path, body)
    assert len(events) == 3
    assert events[0].summary == "会议"
    assert events[0].all_day is False and events[0].busy is True
    all_day = next(e for e in events if e.uid == "b")
    assert all_day.all_day is True and all_day.busy is False
    tentative = next(e for e in events if e.uid == "c")
    assert tentative.busy is True
    assert warnings == []
    assert sources[0].events_total == 3
    assert sources[0].events_in_week == 3


def test_all_day_busy_flag(tmp_path):
    body = calendar(vevent(uid="b", start="20261028", end="20261029", summary="全天", all_day=True))
    cfg = make_config(env={"WEEKGLASS_ALL_DAY_BUSY": "1"})
    _sources, events, _warnings, _d, _c, _t = load(tmp_path, body, cfg=cfg)
    assert events[0].busy is True


def test_cancelled_and_transparent(tmp_path):
    body = calendar(
        vevent(uid="a", start="20261026T100000", end="20261026T110000", summary="取消", extra="STATUS:CANCELLED"),
        vevent(uid="b", start="20261026T120000", end="20261026T130000", summary="透明", extra="TRANSP:TRANSPARENT"),
    )
    sources, events, warnings, duplicates, cancelled, transparent = load(tmp_path, body)
    assert [e.uid for e in events] == ["b"]
    assert events[0].busy is False
    assert cancelled == 1
    assert transparent == 1
    assert sources[0].events_in_week == 1


def test_floating_and_unknown_timezone(tmp_path):
    body = calendar(
        vevent(uid="floating", start="20261026T100000", end="20261026T110000", summary="浮动"),
    ).replace("DTSTART;TZID=Asia/Shanghai:20261026T100000", "DTSTART:20261026T100000").replace(
        "DTEND;TZID=Asia/Shanghai:20261026T110000", "DTEND:20261026T110000"
    )
    _s, events, warnings, _d, _c, _t = load(tmp_path, body)
    assert events[0].start.isoformat() == "2026-10-26T10:00:00+08:00"
    assert any(w.code == "floating_time" for w in warnings)

    unknown = calendar(
        vevent(uid="unknown", start="20261026T100000", end="20261026T110000", summary="未知时区")
    ).replace("Asia/Shanghai", "Mars/Olympus")
    _s, events, warnings, _d, _c, _t = load(tmp_path, unknown, name="unknown.ics")
    assert events[0].start.isoformat() == "2026-10-26T10:00:00+08:00"
    assert any(w.code == "unknown_tzid" for w in warnings)
    assert any("Mars/Olympus" in w.message for w in warnings)


def test_duration_and_utc(tmp_path):
    body = calendar(
        vevent(uid="duration", start="20261026T100000", summary="时长", duration="PT1H30M"),
        """BEGIN:VEVENT
UID:utc
DTSTAMP:20261001T000000Z
DTSTART:20261026T020000Z
DTEND:20261026T030000Z
SUMMARY:UTC
END:VEVENT""",
    )
    _s, events, _w, _d, _c, _t = load(tmp_path, body)
    duration = next(e for e in events if e.uid == "duration")
    assert duration.minutes == 90
    utc = next(e for e in events if e.uid == "utc")
    assert utc.start.isoformat() == "2026-10-26T10:00:00+08:00"


def test_rrule_exdate_and_override(tmp_path):
    body = calendar(
        """BEGIN:VEVENT
UID:series
DTSTAMP:20261001T000000Z
DTSTART;TZID=Asia/Shanghai:20261005T093000
DTEND;TZID=Asia/Shanghai:20261005T094500
RRULE:FREQ=WEEKLY;COUNT=5
EXDATE;TZID=Asia/Shanghai:20261012T093000
SUMMARY:每周站会
END:VEVENT""",
        """BEGIN:VEVENT
UID:series
DTSTAMP:20261001T000000Z
RECURRENCE-ID;TZID=Asia/Shanghai:20261026T093000
DTSTART;TZID=Asia/Shanghai:20261026T140000
DTEND;TZID=Asia/Shanghai:20261026T150000
SUMMARY:改期站会
END:VEVENT""",
    )
    _s, events, _w, _d, _c, _t = load(tmp_path, body)
    assert len(events) == 1
    assert events[0].summary == "改期站会"
    assert events[0].start.isoformat() == "2026-10-26T14:00:00+08:00"
    assert events[0].recurrence_id == "2026-10-26T09:30:00+08:00"


def test_rrule_bad_series_is_skipped(tmp_path):
    body = calendar(
        """BEGIN:VEVENT
UID:bad
DTSTAMP:20261001T000000Z
DTSTART;TZID=Asia/Shanghai:20261026T100000
RRULE:FREQ=BOGUS
SUMMARY:坏规则
END:VEVENT""",
        vevent(uid="ok", start="20261026T120000", end="20261026T130000", summary="正常"),
    )
    _s, events, _w, _d, _c, _t = load(tmp_path, body)
    assert [e.uid for e in events] == ["ok"]


def test_missing_dtstart_and_end_before_start(tmp_path):
    body = calendar(
        """BEGIN:VEVENT
UID:no-start
SUMMARY:没有开始
END:VEVENT""",
        """BEGIN:VEVENT
UID:back
DTSTAMP:20261001T000000Z
DTSTART;TZID=Asia/Shanghai:20261026T110000
DTEND;TZID=Asia/Shanghai:20261026T100000
SUMMARY:倒序
END:VEVENT""",
    )
    _s, events, warnings, _d, _c, _t = load(tmp_path, body)
    codes = {w.code for w in warnings}
    assert "missing_dtstart" in codes
    assert "end_before_start" in codes
    assert len(events) == 1
    assert events[0].start.isoformat() == "2026-10-26T11:00:00+08:00"
    assert events[0].end == events[0].start


def test_duplicate_across_calendars(tmp_path):
    body = vevent(uid="dup", start="20261026T100000", end="20261026T110000", summary="重复")
    first = write_ics(tmp_path, "work.ics", calendar(body, name="WORK"))
    second = write_ics(tmp_path, "personal.ics", calendar(body, name="PERSONAL"))
    sources, events, _w, duplicates, _c, _t = load_events([str(first), str(second)], make_config())
    assert duplicates == 1
    assert len(events) == 1
    assert sorted(events[0].sources) == ["personal.ics", "work.ics"]
    assert [s.name for s in sources] == ["work.ics", "personal.ics"]


def test_week_boundaries(tmp_path):
    body = calendar(
        vevent(uid="sun", start="20261025T233000", end="20261026T003000", summary="跨夜"),
        vevent(uid="fri", start="20261030T230000", end="20261030T233000", summary="周五晚"),
        vevent(uid="sat", start="20261031T100000", end="20261031T110000", summary="周六"),
    )
    _s, events, _w, _d, _c, _t = load(tmp_path, body)
    assert {e.uid for e in events} == {"sun", "fri", "sat"}
    sun = next(e for e in events if e.uid == "sun")
    assert sun.start.isoformat() == "2026-10-25T23:30:00+08:00"
    sat = next(e for e in events if e.uid == "sat")
    assert sat.start.isoformat() == "2026-10-31T10:00:00+08:00"


def test_bad_inputs(tmp_path):
    missing = tmp_path / "missing.ics"
    with pytest.raises(InputError):
        load_events([str(missing)], make_config())

    directory = tmp_path / "dir.ics"
    directory.mkdir()
    with pytest.raises(InputError):
        load_events([str(directory)], make_config())

    bad = write_ics(tmp_path, "bad.ics", "this is not ical")
    with pytest.raises(CalendarError):
        load_events([str(bad)], make_config())

    empty = write_ics(tmp_path, "empty.ics", "")
    with pytest.raises(CalendarError):
        load_events([str(empty)], make_config())


def test_file_size_and_event_limits(tmp_path):
    body = simple_ics(tmp_path, "big.ics", vevent(uid="a", start="20261026T100000", end="20261026T110000"))
    cfg = make_config()
    cfg = replace(cfg, max_file_bytes=10)
    with pytest.raises(CalendarError) as exc:
        load_events([str(body)], cfg)
    assert exc.value.code == "file_too_large"

    many = "\n".join(
        vevent(uid=f"e{i}", start="20261026T100000", end="20261026T110000", summary=f"事件{i}") for i in range(101)
    )
    path = write_ics(tmp_path, "many.ics", calendar(many))
    cfg = make_config()
    cfg = replace(cfg, max_events=100)
    with pytest.raises(CalendarError) as exc:
        load_events([str(path)], cfg)
    assert exc.value.code == "too_many_events"


def test_too_many_calendars(tmp_path):
    paths = []
    for i in range(21):
        paths.append(str(simple_ics(tmp_path, f"{i}.ics", vevent(uid=f"u{i}", start="20261026T100000", end="20261026T110000"))))
    with pytest.raises(InputError):
        load_events(paths, make_config())


def test_secondly_recurrence_is_rejected_before_expansion(tmp_path):
    body = calendar(
        """BEGIN:VEVENT
UID:fast
DTSTAMP:20261001T000000Z
DTSTART;TZID=Asia/Shanghai:20261026T090000
DTEND;TZID=Asia/Shanghai:20261026T091500
RRULE:FREQ=SECONDLY
SUMMARY:每秒
END:VEVENT"""
    )
    path = write_ics(tmp_path, "fast.ics", body)
    cfg = make_config(env={"WEEKGLASS_MAX_EVENTS": "1000"})
    with pytest.raises(CalendarError) as exc:
        load_events([str(path)], cfg)
    assert exc.value.code == "recurrence_limit"


def test_hourly_recurrence_budget_rejects_before_expansion(tmp_path):
    body = calendar(
        """BEGIN:VEVENT
UID:hourly
DTSTAMP:20261001T000000Z
DTSTART;TZID=Asia/Shanghai:20261026T090000
DTEND;TZID=Asia/Shanghai:20261026T091500
RRULE:FREQ=HOURLY
SUMMARY:每小时
END:VEVENT"""
    )
    path = write_ics(tmp_path, "hourly.ics", body)
    cfg = make_config(env={"WEEKGLASS_MAX_EVENTS": "100"})
    with pytest.raises(CalendarError) as exc:
        load_events([str(path)], cfg)
    assert exc.value.code == "recurrence_limit"


def test_unknown_tzid_is_named_in_warning(tmp_path):
    body = calendar(
        """BEGIN:VEVENT
UID:unknown-zone
DTSTAMP:20261001T000000Z
DTSTART;TZID=Mars/Phobos:20261026T100000
DTEND;TZID=Mars/Phobos:20261026T110000
SUMMARY:未知时区
END:VEVENT"""
    )
    _s, events, warnings, _d, _c, _t = load(tmp_path, body)
    assert len(events) == 1
    match = [w for w in warnings if w.code == "unknown_tzid"]
    assert match
    assert "Mars/Phobos" in match[0].message
    assert "Asia/Shanghai" in match[0].message
    assert "没有时区" not in match[0].message


def test_recurrence_id_is_scoped_to_its_own_uid(tmp_path):
    body = calendar(
        """BEGIN:VEVENT
UID:series
DTSTAMP:20261001T000000Z
DTSTART;TZID=Asia/Shanghai:20261026T090000
DTEND;TZID=Asia/Shanghai:20261026T091500
RRULE:FREQ=WEEKLY;COUNT=2
SUMMARY:系列站会
END:VEVENT
BEGIN:VEVENT
UID:series
DTSTAMP:20261001T000000Z
RECURRENCE-ID;TZID=Asia/Shanghai:20261028T090000
DTSTART;TZID=Asia/Shanghai:20261028T100000
DTEND;TZID=Asia/Shanghai:20261028T101500
SUMMARY:系列站会（改期）
END:VEVENT
BEGIN:VEVENT
UID:other
DTSTAMP:20261001T000000Z
DTSTART;TZID=Asia/Shanghai:20261028T090000
DTEND;TZID=Asia/Shanghai:20261028T100000
SUMMARY:同时间别的会
END:VEVENT"""
    )
    _s, events, _w, _d, _c, _t = load(tmp_path, body)
    other = [event for event in events if event.uid == "other"]
    assert len(other) == 1
    assert other[0].recurrence_id is None
    override = [event for event in events if event.summary == "系列站会（改期）"]
    assert len(override) == 1
    assert override[0].recurrence_id == "2026-10-28T09:00:00+08:00"


def test_count_limited_secondly_recurrence_is_allowed(tmp_path):
    body = calendar(
        """BEGIN:VEVENT
UID:twice
DTSTAMP:20261001T000000Z
DTSTART;TZID=Asia/Shanghai:20261026T090000
DTEND;TZID=Asia/Shanghai:20261026T091500
RRULE:FREQ=SECONDLY;COUNT=2
SUMMARY:两次
END:VEVENT"""
    )
    path = write_ics(tmp_path, "twice.ics", body)
    _s, events, _w, _d, _c, _t = load_events([str(path)], make_config(env={"WEEKGLASS_MAX_EVENTS": "100"}))
    assert len(events) == 2


def test_sub_minute_end_keeps_free_busy_invariant(tmp_path):
    from weekglass.metrics import compute_metrics

    body = calendar(
        """BEGIN:VEVENT
UID:seconds
DTSTAMP:20261001T000000Z
DTSTART;TZID=Asia/Shanghai:20261026T090000
DTEND;TZID=Asia/Shanghai:20261026T100030
SUMMARY:带秒结束
END:VEVENT"""
    )
    _s, events, _w, _d, _c, _t = load(tmp_path, body)
    metrics, days = compute_metrics(events, make_config(), duplicates=0, cancelled=0, transparent=0)
    assert days[0].free_minutes == 419
    assert days[0].focus_minutes + days[0].fragmented_minutes == days[0].free_minutes
    assert days[0].busy_minutes + days[0].free_minutes == days[0].available_minutes
    assert metrics.busy_minutes == 61


def test_no_uid_end_before_start_becomes_zero_length(tmp_path):
    body = calendar(
        """BEGIN:VEVENT
DTSTAMP:20261001T000000Z
DTSTART;TZID=Asia/Shanghai:20261026T110000
DTEND;TZID=Asia/Shanghai:20261026T100000
SUMMARY:无 UID 反向
END:VEVENT"""
    )
    _s, events, warnings, _d, _c, _t = load(tmp_path, body)
    assert len(events) == 1
    assert events[0].start.isoformat() == "2026-10-26T11:00:00+08:00"
    assert events[0].end == events[0].start
    assert events[0].minutes == 0
    assert any(w.code == "end_before_start" for w in warnings)


def test_dst_wall_clock_week_keeps_work_window_minutes(tmp_path):
    from weekglass.metrics import compute_metrics

    cfg = load_config(
        {
            "WEEKGLASS_TZ": "America/New_York",
            "WEEKGLASS_WEEK": "2026-03-02",
            "WEEKGLASS_NOW": "2026-03-05T12:00:00-05:00",
            "WEEKGLASS_INCLUDE_WEEKEND": "1",
            "WEEKGLASS_WORK_START": "01:00",
            "WEEKGLASS_WORK_END": "04:00",
            "WEEKGLASS_LUNCH_START": "off",
            "WEEKGLASS_LUNCH_END": "off",
        }
    )
    metrics, days = compute_metrics([], cfg, duplicates=0, cancelled=0, transparent=0)
    assert len(days) == 7
    assert days[6].available_minutes == 120
    assert metrics.available_minutes == 6 * 180 + 120


def test_rrule_until_byday_and_rdate(tmp_path):
    body = calendar(
        """BEGIN:VEVENT
UID:until-byday
DTSTAMP:20261001T000000Z
DTSTART;TZID=Asia/Shanghai:20261026T090000
DTEND;TZID=Asia/Shanghai:20261026T093000
RRULE:FREQ=WEEKLY;BYDAY=MO,WE;UNTIL=20261104T000000Z
SUMMARY:周一三五
END:VEVENT
BEGIN:VEVENT
UID:rdate
DTSTAMP:20261001T000000Z
DTSTART;TZID=Asia/Shanghai:20261030T140000
DTEND;TZID=Asia/Shanghai:20261030T143000
RDATE;TZID=Asia/Shanghai:20261030T160000
SUMMARY:额外时段
END:VEVENT"""
    )
    _s, events, _w, _d, _c, _t = load(tmp_path, body)
    by_uid = {}
    for event in events:
        by_uid.setdefault(event.uid, []).append(event.start.strftime("%Y-%m-%d %H:%M"))
    assert by_uid["until-byday"] == ["2026-10-26 09:00", "2026-10-28 09:00"]
    assert by_uid["rdate"] == ["2026-10-30 14:00", "2026-10-30 16:00"]
