"""Deterministic weekly metrics and focus suggestions.

All intervals are half-open [start, end).  Minutes are floored to whole
minutes.  Lunch is removed from available time, so a meeting during lunch does
not inflate busy time and a free block never crosses lunch.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from .config import Config, WEEKDAY_NAMES
from .formatting import round1
from .model import DayMetrics, Event, Metrics, Suggestion

GRID_MINUTES = 15
MAX_SUGGESTION_MINUTES = 180
BACK_TO_BACK_MINUTES = 5


def _minutes(delta: timedelta) -> int:
    return max(0, int(delta.total_seconds() // 60))


def _merge(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    if not intervals:
        return []
    ordered = sorted(intervals)
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _clip(interval: tuple[datetime, datetime], bounds: tuple[datetime, datetime]) -> tuple[datetime, datetime] | None:
    start = max(interval[0], bounds[0])
    end = min(interval[1], bounds[1])
    return (start, end) if end > start else None


def _available_intervals(day: date, cfg: Config) -> list[tuple[datetime, datetime]]:
    start, end = cfg.day_window(day)
    lunch = cfg.lunch_window(day)
    if lunch is None:
        return [(start, end)]
    return [(start, lunch[0]), (lunch[1], end)]


def _merge_available(available: list[tuple[datetime, datetime]], busy: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    free: list[tuple[datetime, datetime]] = []
    for a_start, a_end in available:
        cursor = a_start
        for b_start, b_end in busy:
            if b_end <= cursor or b_start >= a_end:
                continue
            if b_start > cursor:
                free.append((cursor, min(b_start, a_end)))
            cursor = max(cursor, b_end)
            if cursor >= a_end:
                break
        if cursor < a_end:
            free.append((cursor, a_end))
    return free


def _event_intervals(events: list[Event], day: date, cfg: Config, *, include_buffer: bool) -> list[tuple[datetime, datetime]]:
    start_of_day = datetime.combine(day, time(0, 0), tzinfo=cfg.tz)
    end_of_day = start_of_day + timedelta(days=1)
    result: list[tuple[datetime, datetime]] = []
    for event in events:
        if not event.busy and not (event.all_day and cfg.all_day_busy):
            continue
        if event.all_day:
            interval = _clip((event.start, event.end), (start_of_day, end_of_day))
            if interval is None:
                continue
        else:
            interval = (event.start, event.end)
        clipped = _clip(interval, (start_of_day, end_of_day))
        if clipped is None:
            continue
        if include_buffer and cfg.buffer_minutes and not event.all_day:
            clipped = (
                clipped[0] - timedelta(minutes=cfg.buffer_minutes),
                clipped[1] + timedelta(minutes=cfg.buffer_minutes),
            )
            clipped = _clip(clipped, (start_of_day, end_of_day))
            if clipped is None:
                continue
        result.append(clipped)
    return result


def compute_day(day: date, events: list[Event], cfg: Config) -> DayMetrics:
    available = _available_intervals(day, cfg)
    busy_raw = _event_intervals(events, day, cfg, include_buffer=True)
    clipped_busy: list[tuple[datetime, datetime]] = []
    for interval in busy_raw:
        for a_start, a_end in available:
            piece = _clip(interval, (a_start, a_end))
            if piece is not None:
                clipped_busy.append(piece)
    busy = _merge(clipped_busy)
    free = _merge(_merge_available(available, busy))

    available_minutes = sum(_minutes(end - start) for start, end in available)
    busy_minutes = sum(_minutes(end - start) for start, end in busy)
    free_minutes = max(0, available_minutes - busy_minutes)

    focus_blocks = [interval for interval in free if _minutes(interval[1] - interval[0]) >= cfg.min_focus_minutes]
    fragmented = [interval for interval in free if _minutes(interval[1] - interval[0]) < cfg.min_focus_minutes]
    focus_minutes = sum(_minutes(end - start) for start, end in focus_blocks)
    fragmented_minutes = sum(_minutes(end - start) for start, end in fragmented)

    after_hours = 0
    work_start, work_end = cfg.day_window(day)
    outside = [(datetime.combine(day, time(0, 0), tzinfo=cfg.tz), work_start), (work_end, datetime.combine(day, time(0, 0), tzinfo=cfg.tz) + timedelta(days=1))]
    outside_busy: list[tuple[datetime, datetime]] = []
    for event in events:
        if not event.busy or event.all_day:
            continue
        for bound in outside:
            piece = _clip((event.start, event.end), bound)
            if piece is not None:
                outside_busy.append(piece)
    for start, end in _merge(outside_busy):
        after_hours += _minutes(end - start)

    all_day = sum(1 for event in events if event.all_day and event.start.date() <= day <= (event.end - timedelta(seconds=1)).date())
    return DayMetrics(
        date=day,
        weekday=WEEKDAY_NAMES[day.weekday()],
        available_minutes=available_minutes,
        busy_minutes=busy_minutes,
        free_minutes=free_minutes,
        focus_minutes=focus_minutes,
        fragmented_minutes=fragmented_minutes,
        focus_blocks=len(focus_blocks),
        fragments=len(fragmented),
        longest_focus_minutes=max((_minutes(end - start) for start, end in focus_blocks), default=0),
        busy_blocks=len(busy),
        after_hours_minutes=after_hours,
        all_day_events=all_day,
    )


def _back_to_back(events: list[Event], days: tuple[date, ...]) -> int:
    count = 0
    for day in days:
        timed = sorted(
            [e for e in events if e.busy and not e.all_day and e.start.date() == day],
            key=lambda e: (e.start, e.end),
        )
        for left, right in zip(timed, timed[1:]):
            gap = (right.start - left.end).total_seconds() / 60
            if 0 <= gap <= BACK_TO_BACK_MINUTES:
                count += 1
    return count


def _weekend_minutes(events: list[Event], cfg: Config) -> int:
    total = 0
    for offset in range(5, 7):
        day = cfg.week_start + timedelta(days=offset)
        day_start = datetime.combine(day, time(0, 0), tzinfo=cfg.tz)
        timed: list[tuple[datetime, datetime]] = []
        for event in events:
            if not event.busy or event.all_day:
                continue
            piece = _clip((event.start, event.end), (day_start, day_start + timedelta(days=1)))
            if piece is not None:
                timed.append(piece)
        for start, end in _merge(timed):
            total += _minutes(end - start)
    return total


def compute_metrics(events: list[Event], cfg: Config, *, duplicates: int, cancelled: int, transparent: int) -> tuple[Metrics, list[DayMetrics]]:
    days = [compute_day(day, events, cfg) for day in cfg.days]
    metrics = Metrics(
        available_minutes=sum(d.available_minutes for d in days),
        busy_minutes=sum(d.busy_minutes for d in days),
        free_minutes=sum(d.free_minutes for d in days),
        focus_minutes=sum(d.focus_minutes for d in days),
        fragmented_minutes=sum(d.fragmented_minutes for d in days),
        focus_blocks=sum(d.focus_blocks for d in days),
        fragments=sum(d.fragments for d in days),
        longest_focus_minutes=max((d.longest_focus_minutes for d in days), default=0),
        busy_blocks=sum(d.busy_blocks for d in days),
        back_to_back_pairs=_back_to_back(events, cfg.days),
        event_count=len([e for e in events if e.status != "CANCELLED"]),
        all_day_events=sum(1 for e in events if e.all_day and e.status != "CANCELLED"),
        after_hours_minutes=sum(d.after_hours_minutes for d in days),
        weekend_minutes=_weekend_minutes(events, cfg),
        duplicate_events=duplicates,
        cancelled_events=cancelled,
        transparent_events=transparent,
    )
    return metrics, days


def _ceil_to_grid(moment: datetime) -> datetime:
    discard = timedelta(
        minutes=moment.minute % GRID_MINUTES,
        seconds=moment.second,
        microseconds=moment.microsecond,
    )
    if discard:
        moment = moment - discard + timedelta(minutes=GRID_MINUTES)
    return moment.replace(second=0, microsecond=0)


def _floor_to_grid(moment: datetime) -> datetime:
    return moment.replace(minute=moment.minute - (moment.minute % GRID_MINUTES), second=0, microsecond=0)


def _reason(day: date, start: datetime, minutes: int) -> str:
    period = "上午" if start.hour < 12 else "下午"
    return f"{WEEKDAY_NAMES[day.weekday()]}{period}连续空闲 {minutes} 分钟，当前没有占用。"


def suggest_focus_blocks(days: list[DayMetrics], events: list[Event], cfg: Config) -> list[Suggestion]:
    if cfg.max_suggestions == 0:
        return []
    candidates: list[tuple[float, date, datetime, datetime, int]] = []
    for day in cfg.days:
        available = _available_intervals(day, cfg)
        busy_raw = _event_intervals(events, day, cfg, include_buffer=True)
        clipped_busy: list[tuple[datetime, datetime]] = []
        for interval in busy_raw:
            for a_start, a_end in available:
                piece = _clip(interval, (a_start, a_end))
                if piece is not None:
                    clipped_busy.append(piece)
        free = _merge(_merge_available(available, _merge(clipped_busy)))
        for start, end in free:
            aligned_start = _ceil_to_grid(start)
            aligned_end = _floor_to_grid(end)
            raw_minutes = _minutes(aligned_end - aligned_start)
            if raw_minutes < cfg.min_focus_minutes:
                continue
            block_minutes = min(raw_minutes, max(MAX_SUGGESTION_MINUTES, cfg.min_focus_minutes))
            # Do not suggest a block that crosses into the next event: end is
            # aligned_start + block_minutes, already <= aligned_end.
            score = min(block_minutes, MAX_SUGGESTION_MINUTES)
            if aligned_start.hour < 12:
                score += 20
            if day.weekday() in (1, 2, 3):
                score += 10
            candidates.append((float(score), day, aligned_start, aligned_start + timedelta(minutes=block_minutes), block_minutes))

    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    selected: list[Suggestion] = []
    per_day: dict[date, int] = {}
    for score, day, start, end, minutes in candidates:
        if len(selected) >= cfg.max_suggestions:
            break
        if per_day.get(day, 0) >= cfg.max_per_day:
            continue
        per_day[day] = per_day.get(day, 0) + 1
        selected.append(
            Suggestion(
                rank=len(selected) + 1,
                date=day,
                weekday=WEEKDAY_NAMES[day.weekday()],
                start=start,
                end=end,
                minutes=minutes,
                reason=_reason(day, start, minutes),
            )
        )
    return selected
