"""JSON and single-file HTML report rendering."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from . import __version__
from .config import Config
from .formatting import clock, compact_duration, date_label, date_range_label, duration, generated_label, percent, span_minutes
from .metrics import _available_intervals, _clip, _event_intervals, _merge, _merge_available
from .model import Event, Report


def render_json(report: Report) -> str:
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n"


def _timeline(day: date, events: list[Event], cfg: Config) -> list[dict]:
    """Segments positioned on the 09:00–18:00 track."""
    track_start, track_end = cfg.day_window(day)
    total = span_minutes(track_start, track_end)
    available = _available_intervals(day, cfg)
    clipped_busy: list[tuple[datetime, datetime]] = []
    for interval in _event_intervals(events, day, cfg, include_buffer=True):
        for a_start, a_end in available:
            piece = _clip(interval, (a_start, a_end))
            if piece is not None:
                clipped_busy.append(piece)
    busy = _merge(clipped_busy)
    free = _merge(_merge_available(available, busy))

    segments: list[dict] = []
    lunch = cfg.lunch_window(day)
    if lunch:
        segments.append(
            {
                "kind": "lunch",
                "left": round(span_minutes(track_start, lunch[0]) * 100 / total, 3),
                "width": round(span_minutes(lunch[0], lunch[1]) * 100 / total, 3),
                "label": "午休",
            }
        )
    for start, end in free:
        minutes = span_minutes(start, end)
        segments.append(
            {
                "kind": "focus" if minutes >= cfg.min_focus_minutes else "fragment",
                "left": round(span_minutes(track_start, start) * 100 / total, 3),
                "width": round(minutes * 100 / total, 3),
                "label": compact_duration(minutes) if minutes >= 30 else "",
            }
        )
    for start, end in busy:
        minutes = span_minutes(start, end)
        segments.append(
            {
                "kind": "busy",
                "left": round(span_minutes(track_start, start) * 100 / total, 3),
                "width": round(minutes * 100 / total, 3),
                "label": compact_duration(minutes) if minutes >= 30 else "",
            }
        )
    return sorted(segments, key=lambda item: item["left"])


def _events_for_day(day: date, events: list[Event]) -> list[dict]:
    result = []
    for event in events:
        if event.status == "CANCELLED":
            continue
        ends = event.end - timedelta(seconds=1)
        first_day = event.start.date()
        last_day = max(first_day, ends.date())
        if first_day <= day <= last_day:
            result.append(
                {
                    "time": "全天" if event.all_day else f"{clock(event.start)}–{clock(event.end)}",
                    "summary": event.summary,
                    "source": "、".join(event.sources),
                    "busy": event.busy,
                    "all_day": event.all_day,
                    "location": event.location,
                }
            )
    return result


def build_view(report: Report, cfg: Config, plan_file: str | None) -> dict:
    timeline_events = report.events_full or report.events
    days = []
    examined = report.week_start
    last_day = report.days[-1].date if report.days else report.week_start
    for day_metrics in report.days:
        days.append(
            {
                "date": day_metrics.date.isoformat(),
                "weekday": day_metrics.weekday,
                "date_label": date_label(day_metrics.date),
                "busy": duration(day_metrics.busy_minutes),
                "focus": duration(day_metrics.focus_minutes),
                "fragmented": duration(day_metrics.fragmented_minutes),
                "longest": duration(day_metrics.longest_focus_minutes),
                "busy_pct": percent(day_metrics.busy_pct),
                "focus_blocks": day_metrics.focus_blocks,
                "fragments": day_metrics.fragments,
                "segments": _timeline(day_metrics.date, timeline_events, cfg),
                "events": _events_for_day(day_metrics.date, report.events),
            }
        )
    metrics = report.metrics
    conclusion = (
        f"{'这 %d 天' % len(report.days) if cfg.include_weekend else '这 %d 个工作日' % len(report.days)}里，{percent(metrics.busy_pct)} 的可用时间被占用；"
        f"空闲时间有 {percent(metrics.fragmentation_pct)} 短于 {cfg.min_focus_minutes} 分钟。"
    )
    if metrics.focus_blocks:
        conclusion += f" 完整专注块共 {duration(metrics.focus_minutes)}，最长 {duration(metrics.longest_focus_minutes)}。"
    else:
        conclusion += " 这一周没有完整专注块。"

    sources = []
    for source in report.sources:
        sources.append(
            {
                "name": source.name,
                "path": source.path,
                "events": source.events_in_week,
                "bytes": source.bytes,
            }
        )
    warnings = [{"code": w.code, "message": w.message, "source": w.source} for w in report.warnings]
    analyzed_dates = {day_metrics.date for day_metrics in report.days}
    hidden = [event for event in timeline_events if event.start.date() not in analyzed_dates]
    details_count = sum(len(day["events"]) for day in days)
    suggestions = []
    for suggestion in report.suggestions:
        suggestions.append(
            {
                "rank": suggestion.rank,
                "weekday": suggestion.weekday,
                "date_label": date_label(suggestion.date),
                "time": f"{clock(suggestion.start)}–{clock(suggestion.end)}",
                "duration": duration(suggestion.minutes),
                "reason": suggestion.reason,
            }
        )
    return {
        "title": f"{report.week_iso} · Weekglass",
        "version": __version__,
        "week_iso": report.week_iso,
        "range_label": date_range_label(report.week_start, last_day),
        "timezone": report.timezone,
        "generated": generated_label(report.generated_at),
        "days_count": len(report.days),
        "details_count": details_count,
        "hidden_events": len(hidden),
        "hidden_minutes": sum(event.minutes for event in hidden),
        "days_label": f"{len(report.days)} 天（含周末）" if cfg.include_weekend else f"{len(report.days)} 个工作日",
        "max_per_day": cfg.max_per_day,
        "metrics": {
            "busy": duration(metrics.busy_minutes),
            "available": duration(metrics.available_minutes),
            "busy_pct": percent(metrics.busy_pct),
            "focus": duration(metrics.focus_minutes),
            "focus_blocks": metrics.focus_blocks,
            "fragmented": duration(metrics.fragmented_minutes),
            "fragmentation_pct": percent(metrics.fragmentation_pct),
            "longest": duration(metrics.longest_focus_minutes),
            "event_count": metrics.event_count,
            "after_hours": duration(metrics.after_hours_minutes),
            "back_to_back": metrics.back_to_back_pairs,
            "duplicates": metrics.duplicate_events,
        },
        "conclusion": conclusion,
        "days": days,
        "suggestions": suggestions,
        "plan_file": plan_file,
        "sources": sources,
        "warnings": warnings,
        "min_focus": cfg.min_focus_minutes,
        "work_start": cfg.work_start.strftime("%H:%M"),
        "work_end": cfg.work_end.strftime("%H:%M"),
        "lunch": f"{cfg.lunch_start:%H:%M}–{cfg.lunch_end:%H:%M}" if cfg.lunch_start and cfg.lunch_end else "不计",
        "buffer": cfg.buffer_minutes,
        "include_weekend": cfg.include_weekend,
        "all_day_busy": cfg.all_day_busy,
    }


def render_html(report: Report, cfg: Config, plan_file: str | None) -> str:
    env = Environment(
        loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
        autoescape=True,
    )
    env.filters["duration"] = duration
    return env.get_template("report.html.j2").render(view=build_view(report, cfg, plan_file))
