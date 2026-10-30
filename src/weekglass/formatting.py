"""Chinese human-readable formatting shared by the CLI and the report."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP


def span_minutes(start: datetime, end: datetime) -> int:
    """Actual elapsed whole minutes, including DST transitions."""
    if start.tzinfo is None or end.tzinfo is None:
        return max(0, int((end - start).total_seconds() // 60))
    return max(0, int((end.astimezone(timezone.utc) - start.astimezone(timezone.utc)).total_seconds() // 60))


def round1(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def duration(minutes: int) -> str:
    minutes = max(0, int(minutes))
    hours, rest = divmod(minutes, 60)
    if hours and rest:
        return f"{hours} 小时 {rest} 分"
    if hours:
        return f"{hours} 小时"
    return f"{rest} 分"


def compact_duration(minutes: int) -> str:
    minutes = max(0, int(minutes))
    hours, rest = divmod(minutes, 60)
    if hours and rest:
        return f"{hours}h{rest:02d}m"
    if hours:
        return f"{hours}h"
    return f"{rest}m"


def percent(value: float) -> str:
    return f"{value:.0f}%"


def clock(moment: datetime) -> str:
    return moment.strftime("%H:%M")


def date_label(day: date) -> str:
    return f"{day.month} 月 {day.day} 日"


def date_range_label(start: date, end: date) -> str:
    if start.month == end.month:
        return f"{start.month} 月 {start.day} 日–{end.day} 日"
    return f"{start.month} 月 {start.day} 日–{end.month} 月 {end.day} 日"


def generated_label(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M")
