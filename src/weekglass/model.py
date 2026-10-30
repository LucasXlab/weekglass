"""Plain data objects shared by parsing, metrics, planning and reporting."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from .formatting import round1


@dataclass
class Warning:
    code: str
    message: str
    source: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "source": self.source}


@dataclass
class SourceInfo:
    path: str
    name: str
    bytes: int
    events_total: int
    events_in_week: int
    warnings: list[Warning] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "bytes": self.bytes,
            "events_total": self.events_total,
            "events_in_week": self.events_in_week,
            "warnings": [w.to_dict() for w in self.warnings],
        }


@dataclass
class Event:
    uid: str
    recurrence_id: str | None
    sources: list[str]
    summary: str
    start: datetime
    end: datetime
    all_day: bool
    status: str
    transparency: str
    busy: bool
    location: str = ""
    categories: list[str] = field(default_factory=list)
    attendee_count: int = 0
    is_focus: bool = False

    @property
    def minutes(self) -> int:
        return max(0, int((self.end - self.start).total_seconds() // 60))

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "recurrence_id": self.recurrence_id,
            "sources": self.sources,
            "summary": self.summary,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "minutes": self.minutes,
            "all_day": self.all_day,
            "busy": self.busy,
            "status": self.status.lower(),
            "transparency": self.transparency.lower(),
            "location": self.location,
            "categories": self.categories,
            "attendee_count": self.attendee_count,
            "is_focus": self.is_focus,
        }


@dataclass
class DayMetrics:
    date: date
    weekday: str
    available_minutes: int = 0
    busy_minutes: int = 0
    free_minutes: int = 0
    focus_minutes: int = 0
    fragmented_minutes: int = 0
    focus_blocks: int = 0
    fragments: int = 0
    longest_focus_minutes: int = 0
    busy_blocks: int = 0
    after_hours_minutes: int = 0
    all_day_events: int = 0

    @property
    def busy_pct(self) -> float:
        return round1(self.busy_minutes * 100 / self.available_minutes) if self.available_minutes else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date.isoformat(),
            "weekday": self.weekday,
            "available_minutes": self.available_minutes,
            "busy_minutes": self.busy_minutes,
            "free_minutes": self.free_minutes,
            "focus_minutes": self.focus_minutes,
            "fragmented_minutes": self.fragmented_minutes,
            "focus_blocks": self.focus_blocks,
            "fragments": self.fragments,
            "longest_focus_minutes": self.longest_focus_minutes,
            "busy_blocks": self.busy_blocks,
            "after_hours_minutes": self.after_hours_minutes,
            "all_day_events": self.all_day_events,
            "busy_pct": self.busy_pct,
        }


@dataclass
class Metrics:
    available_minutes: int = 0
    busy_minutes: int = 0
    free_minutes: int = 0
    focus_minutes: int = 0
    fragmented_minutes: int = 0
    focus_blocks: int = 0
    fragments: int = 0
    longest_focus_minutes: int = 0
    busy_blocks: int = 0
    back_to_back_pairs: int = 0
    event_count: int = 0
    all_day_events: int = 0
    after_hours_minutes: int = 0
    weekend_minutes: int = 0
    duplicate_events: int = 0
    cancelled_events: int = 0
    transparent_events: int = 0

    @property
    def busy_pct(self) -> float:
        return round1(self.busy_minutes * 100 / self.available_minutes) if self.available_minutes else 0.0

    @property
    def fragmentation_pct(self) -> float:
        return round1(self.fragmented_minutes * 100 / self.free_minutes) if self.free_minutes else 0.0

    @property
    def focus_pct(self) -> float:
        return round1(self.focus_minutes * 100 / self.available_minutes) if self.available_minutes else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "available_minutes": self.available_minutes,
            "busy_minutes": self.busy_minutes,
            "free_minutes": self.free_minutes,
            "focus_minutes": self.focus_minutes,
            "fragmented_minutes": self.fragmented_minutes,
            "focus_blocks": self.focus_blocks,
            "fragments": self.fragments,
            "longest_focus_minutes": self.longest_focus_minutes,
            "busy_blocks": self.busy_blocks,
            "back_to_back_pairs": self.back_to_back_pairs,
            "event_count": self.event_count,
            "all_day_events": self.all_day_events,
            "after_hours_minutes": self.after_hours_minutes,
            "weekend_minutes": self.weekend_minutes,
            "duplicate_events": self.duplicate_events,
            "cancelled_events": self.cancelled_events,
            "transparent_events": self.transparent_events,
            "busy_pct": self.busy_pct,
            "fragmentation_pct": self.fragmentation_pct,
            "focus_pct": self.focus_pct,
        }


@dataclass
class Suggestion:
    rank: int
    date: date
    weekday: str
    start: datetime
    end: datetime
    minutes: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "date": self.date.isoformat(),
            "weekday": self.weekday,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "minutes": self.minutes,
            "reason": self.reason,
        }


@dataclass
class Report:
    schema_version: int
    tool_name: str
    tool_version: str
    generated_at: datetime
    week_iso: str
    week_start: date
    week_end: date
    timezone: str
    settings: dict[str, Any]
    sources: list[SourceInfo]
    metrics: Metrics
    days: list[DayMetrics]
    events: list[Event]
    suggestions: list[Suggestion]
    warnings: list[Warning]
    plan_path: str | None = None
    events_full: list[Event] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "tool": {"name": self.tool_name, "version": self.tool_version},
            "generated_at": self.generated_at.isoformat(),
            "week": {
                "iso": self.week_iso,
                "start": self.week_start.isoformat(),
                "end": self.week_end.isoformat(),
                "analyzed_days": len(self.days),
                "timezone": self.timezone,
            },
            "settings": self.settings,
            "sources": [s.to_dict() for s in self.sources],
            "metrics": self.metrics.to_dict(),
            "days": [d.to_dict() for d in self.days],
            "events": [e.to_dict() for e in self.events],
            "suggestions": [s.to_dict() for s in self.suggestions],
            "warnings": [w.to_dict() for w in self.warnings],
            "plan_path": self.plan_path,
        }
