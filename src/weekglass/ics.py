"""Read .ics files, expand recurrences and normalise events.

No network access happens here.  recurring-ical-events expands RRULE, RDATE,
EXDATE and RECURRENCE-ID overrides; this module then converts every occurrence
to the configured timezone, filters cancelled/transparent events and merges
duplicates that appear in more than one exported calendar.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, time, timedelta
from pathlib import Path

import recurring_ical_events
from icalendar import Calendar

from .config import Config
from .errors import CalendarError, InputError
from .model import Event, SourceInfo, Warning

MAX_WARNINGS = 200
MAX_CALENDARS = 20


def _warning(bucket: list[Warning], code: str, message: str, source: str) -> None:
    item = Warning(code=code, message=message, source=source)
    if item not in bucket and len(bucket) < MAX_WARNINGS:
        bucket.append(item)


def _text(value) -> str:
    return str(value) if value is not None else ""


def _tzid(prop) -> str | None:
    try:
        value = prop.params.get("TZID")
    except Exception:
        return None
    return str(value) if value is not None else None


def _categories(component) -> list[str]:
    raw = component.get("CATEGORIES")
    if raw is None:
        return []
    values = raw if isinstance(raw, list) else [raw]
    result: list[str] = []
    for item in values:
        cats = getattr(item, "cats", None)
        if cats is not None:
            result.extend(str(cat) for cat in cats)
        else:
            result.extend(part.strip() for part in str(item).split(",") if part.strip())
    return list(dict.fromkeys(result))


def _attendee_count(component) -> int:
    raw = component.get("ATTENDEE")
    if raw is None:
        return 0
    return len(raw) if isinstance(raw, list) else 1


def _is_focus(summary: str, categories: list[str]) -> bool:
    haystack = " ".join([summary, *categories]).casefold()
    return "focus" in haystack or "专注" in haystack


def _first(value):
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def _rdate_count(value) -> int:
    if value is None:
        return 0
    items = value if isinstance(value, list) else [value]
    total = 0
    for item in items:
        dates = getattr(item, "dts", None)
        total += len(dates) if dates is not None else 1
    return total


def _check_recurrence_budget(raw_events, start: datetime, end: datetime, limit: int, path: Path) -> None:
    """Reject rules that would materialise far more than ``limit`` occurrences.

    recurring-ical-events returns a full list, so a tiny SECONDLY rule can use
    gigabytes before the post-expansion max-events check is reached.  Estimate
    from FREQ and the expansion window first.
    """
    total = len(raw_events)
    seconds = max(0.0, (end - start).total_seconds())
    for component in raw_events:
        try:
            rule = component.get("RRULE")
        except Exception:  # broken RRULE property; skip_bad_series will handle it
            rule = None
        if rule is not None:
            rules = rule if isinstance(rule, list) else [rule]
            for item in rules:
                try:
                    frequency = _first(item.get("FREQ"))
                    if frequency is None:
                        continue
                    name = str(frequency).upper()
                    if name in {"SECONDLY", "MINUTELY"}:
                        count_raw = _first(item.get("COUNT"))
                        if count_raw is not None:
                            try:
                                count = int(count_raw)
                            except (TypeError, ValueError):
                                count = limit + 1
                            total += max(0, count)
                            if total > limit:
                                raise CalendarError(
                                    f"{path} 的 {name} 重复规则 COUNT={count_raw} 超过 {limit} 个事件上限，已拒绝。",
                                    code="recurrence_limit",
                                )
                            continue
                        unit = 1 if name == "SECONDLY" else 60
                        interval_raw = _first(item.get("INTERVAL")) or 1
                        try:
                            interval = max(1, int(interval_raw))
                        except (TypeError, ValueError):
                            interval = 1
                        units = int((seconds + unit - 1) // unit)
                        total += units // interval + 1
                        if total > limit:
                            raise CalendarError(
                                f"{path} 含 {name} 重复规则；展开会超过 {limit} 个事件上限，已拒绝。",
                                code="recurrence_limit",
                            )
                        continue
                    interval_raw = _first(item.get("INTERVAL")) or 1
                    try:
                        interval = max(1, int(interval_raw))
                    except (TypeError, ValueError):
                        interval = 1
                    if name == "HOURLY":
                        units = int((seconds + 3599) // 3600)
                    elif name == "DAILY":
                        units = int((seconds + 86399) // 86400)
                    elif name == "WEEKLY":
                        units = int((seconds + 7 * 86400 - 1) // (7 * 86400))
                    elif name == "MONTHLY":
                        units = int((seconds + 30 * 86400 - 1) // (30 * 86400))
                    elif name == "YEARLY":
                        units = int((seconds + 365 * 86400 - 1) // (365 * 86400))
                    else:
                        continue
                    count = units // interval + 1
                    count_raw = _first(item.get("COUNT"))
                    if count_raw is not None:
                        try:
                            count = min(count, int(count_raw))
                        except (TypeError, ValueError):
                            pass
                    total += count
                except CalendarError:
                    raise
                except Exception:
                    continue
        try:
            total += _rdate_count(component.get("RDATE"))
        except Exception:
            pass
        if total > limit:
            raise CalendarError(
                f"{path} 的重复规则在展开窗口内可能超过 {limit} 个事件，已拒绝；请缩小日历或修正重复规则。",
                code="recurrence_limit",
            )


def _localize(
    value: datetime,
    cfg: Config,
    source: str,
    warnings: list[Warning],
    tzid: str | None = None,
) -> datetime:
    """Attach the configured timezone to a floating datetime."""
    if value.tzinfo is None:
        if tzid:
            _warning(
                warnings,
                "unknown_tzid",
                f"事件时区 {tzid!r} 无法识别，已按 {cfg.tz_name} 解释；请确认导出时区或改用 UTC 导出。",
                source,
            )
        else:
            _warning(
                warnings,
                "floating_time",
                "事件没有时区，已按配置时区解释；请在日历设置中开启时区，避免跨时区错误。",
                source,
            )
        return value.replace(tzinfo=cfg.tz)
    return value.astimezone(cfg.tz)


def _parse_one_file(path: Path, cfg: Config, warnings: list[Warning]) -> tuple[SourceInfo, list[Event]]:
    try:
        stat = path.stat()
    except OSError as exc:
        raise InputError(
            f"无法读取日历文件 {path}：{exc.strerror or exc}",
            code="file_unreadable",
            hint="确认路径、权限和文件是否存在。",
        ) from None
    if not path.is_file():
        raise InputError(f"{path} 不是普通文件。", code="not_a_file", hint="请传入一个 .ics 文件，而不是目录或设备。")
    if stat.st_size > cfg.max_file_bytes:
        limit = cfg.max_file_bytes // (1024 * 1024)
        raise CalendarError(f"{path} 有 {stat.st_size} 字节，超过 {limit} MB 上限。", code="file_too_large")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise InputError(
            f"无法读取日历文件 {path}：{exc.strerror or exc}",
            code="file_unreadable",
            hint="确认路径、权限和文件是否存在。",
        ) from None

    source_name = path.name
    try:
        calendar = Calendar.from_ical(raw)
    except Exception as exc:  # icalendar raises several parser exception types
        raise CalendarError(
            f"无法解析 {path}：不是有效的 iCalendar 文件。",
            code="invalid_ics",
            hint="请从日历重新导出，确认文件以 BEGIN:VCALENDAR 开头。",
        ) from None
    if not isinstance(calendar, Calendar):
        raise CalendarError(
            f"无法解析 {path}：文件中没有 VCALENDAR。",
            code="invalid_ics",
            hint="请从日历重新导出，确认文件以 BEGIN:VCALENDAR 开头。",
        )

    raw_events = [item for item in calendar.walk("VEVENT")]
    source_tzids: dict[str, str] = {}
    for raw_event in raw_events:
        raw_uid = _text(raw_event.get("UID"))
        raw_start_prop = raw_event.get("DTSTART")
        if raw_uid and raw_start_prop is not None:
            tzid = _tzid(raw_start_prop)
            if tzid:
                source_tzids[raw_uid] = tzid

    override_ids: set[tuple[str, str]] = set()
    zero_start_by_uid: dict[str, datetime] = {}
    zero_no_uid: list[tuple[str, datetime, datetime, datetime]] = []
    for raw_event in raw_events:
        recurrence_prop = raw_event.get("RECURRENCE-ID")
        if recurrence_prop is None or getattr(recurrence_prop, "dt", None) is None:
            continue
        rid = recurrence_prop.dt
        if isinstance(rid, datetime):
            rid = _localize(rid, cfg, source_name, warnings, _tzid(recurrence_prop))
        override_ids.add((_text(raw_event.get("UID")), rid.isoformat()))

    for raw_event in raw_events:
        raw_start_prop = raw_event.get("DTSTART")
        raw_end_prop = raw_event.get("DTEND")
        if raw_start_prop is None or raw_end_prop is None:
            continue
        raw_start_value = raw_start_prop.dt
        raw_end_value = raw_end_prop.dt
        invalid_range = (
            isinstance(raw_start_value, datetime)
            and isinstance(raw_end_value, datetime)
            and raw_end_value < raw_start_value
        ) or (
            isinstance(raw_start_value, date)
            and not isinstance(raw_start_value, datetime)
            and isinstance(raw_end_value, date)
            and not isinstance(raw_end_value, datetime)
            and raw_end_value < raw_start_value
        )
        if not invalid_range:
            continue
        _warning(warnings, "end_before_start", "有事件的结束时间早于开始时间，已按零时长处理。", source_name)
        raw_uid = _text(raw_event.get("UID"))
        if isinstance(raw_start_value, datetime):
            local_start = _localize(
                raw_start_value, cfg, source_name, warnings, _tzid(raw_start_prop)
            )
            local_end = _localize(raw_end_value, cfg, source_name, warnings, _tzid(raw_end_prop))
        else:
            local_start = datetime.combine(raw_start_value, time(0, 0), tzinfo=cfg.tz)
            local_end = datetime.combine(raw_end_value, time(0, 0), tzinfo=cfg.tz)
        if raw_uid:
            zero_start_by_uid[raw_uid] = local_start
        else:
            zero_no_uid.append(
                (_text(raw_event.get("SUMMARY")) or "（无标题）", local_start, local_end, local_start)
            )

    if len(raw_events) > cfg.max_events:
        raise CalendarError(f"{path} 有 {len(raw_events)} 个 VEVENT，超过 {cfg.max_events} 个上限。", code="too_many_events")

    # recurring-ical-events raises KeyError on a VEVENT without DTSTART, even
    # with skip_bad_series.  Remove those components from a sanitized copy so
    # one malformed event cannot fail the whole calendar.
    missing_start = [component for component in raw_events if component.get("DTSTART") is None]
    if missing_start:
        _warning(warnings, "missing_dtstart", "有事件缺少 DTSTART，已跳过。", source_name)
        clean = Calendar()
        for key, value in calendar.property_items():
            if key in {"BEGIN", "END"}:
                continue
            clean.add(key, value)
        for component in calendar.subcomponents:
            if component.name == "VEVENT" and component.get("DTSTART") is None:
                continue
            clean.add_component(component)
        calendar = clean

    start_local, end_local = cfg.week_bounds()
    # Expand two days either side so overnight events and recurrence windows are
    # not lost at the edges.  Metrics clip to the actual work window later.
    expand_start = start_local - timedelta(days=2)
    expand_end = end_local + timedelta(days=2)
    _check_recurrence_budget(raw_events, expand_start, expand_end, cfg.max_events, path)
    try:
        occurrences = recurring_ical_events.of(calendar, skip_bad_series=True).between(expand_start, expand_end)
    except Exception as exc:
        raise CalendarError(f"无法展开 {path} 中的重复事件：{exc}。", code="recurrence_error") from None

    events: list[Event] = []
    total_seen = 0
    for comp in occurrences:
        total_seen += 1
        if total_seen > cfg.max_events:
            raise CalendarError(
                f"{path} 展开后超过 {cfg.max_events} 个事件，请先缩小日历或删除异常的重复规则。",
                code="too_many_events",
            )
        dtstart_prop = comp.get("DTSTART")
        if dtstart_prop is None:
            _warning(warnings, "missing_dtstart", "有事件缺少 DTSTART，已跳过。", source_name)
            continue
        raw_start = dtstart_prop.dt
        all_day = isinstance(raw_start, date) and not isinstance(raw_start, datetime)
        uid_hint = _text(comp.get("UID"))
        tzid_hint = _tzid(dtstart_prop) or source_tzids.get(uid_hint)

        status = _text(comp.get("STATUS") or "CONFIRMED").upper()
        if status not in {"CONFIRMED", "TENTATIVE", "CANCELLED"}:
            status = "CONFIRMED"
        transparency = _text(comp.get("TRANSP") or "OPAQUE").upper()
        if transparency not in {"OPAQUE", "TRANSPARENT"}:
            transparency = "OPAQUE"

        if all_day:
            start = datetime.combine(raw_start, time(0, 0), tzinfo=cfg.tz)
            dtend_prop = comp.get("DTEND")
            end_date = dtend_prop.dt if dtend_prop is not None else raw_start + timedelta(days=1)
            if not isinstance(end_date, date) or isinstance(end_date, datetime):
                end_date = raw_start + timedelta(days=1)
            if end_date <= raw_start:
                end_date = raw_start + timedelta(days=1)
            end = datetime.combine(end_date, time(0, 0), tzinfo=cfg.tz)
        else:
            start = _localize(raw_start, cfg, source_name, warnings, tzid_hint)
            end = start
            dtend_prop = comp.get("DTEND")
            if dtend_prop is not None:
                raw_end = dtend_prop.dt
                if isinstance(raw_end, datetime):
                    end = _localize(
                        raw_end, cfg, source_name, warnings, _tzid(dtend_prop) or tzid_hint
                    )
                else:
                    end = datetime.combine(raw_end, time(0, 0), tzinfo=cfg.tz)
            elif comp.get("DURATION") is not None:
                duration = comp.get("DURATION").dt
                end = start + duration
            if end < start:
                _warning(warnings, "end_before_start", "有事件的结束时间早于开始时间，已按零时长处理。", source_name)
                end = start

        if end <= start_local or start >= end_local:
            continue

        uid = _text(comp.get("UID"))
        if uid and uid in zero_start_by_uid:
            # recurring-ical-events swaps a backwards DTSTART/DTEND; restore
            # the original start and make the occurrence zero-length.
            start = zero_start_by_uid[uid]
            end = start
        elif not uid:
            candidate_summary = _text(comp.get("SUMMARY")) or "（无标题）"
            for summary_hint, raw_start_hint, raw_end_hint, original_start in zero_no_uid:
                if (
                    summary_hint == candidate_summary
                    and start == raw_end_hint
                    and end == raw_start_hint
                ):
                    start = original_start
                    end = start
                    break
        summary = _text(comp.get("SUMMARY")) or "（无标题）"
        categories = _categories(comp)
        recurrence_prop = comp.get("RECURRENCE-ID")
        recurrence_id = None
        if recurrence_prop is not None and getattr(recurrence_prop, "dt", None) is not None:
            rid = recurrence_prop.dt
            if isinstance(rid, datetime):
                rid = _localize(
                    rid, cfg, source_name, warnings, _tzid(recurrence_prop) or source_tzids.get(uid)
                )
                candidate = rid.isoformat()
            else:
                candidate = rid.isoformat()
            if (uid, candidate) in override_ids:
                recurrence_id = candidate
        if not uid:
            digest = hashlib.sha1(f"{summary}|{start.isoformat()}|{end.isoformat()}".encode()).hexdigest()[:16]
            uid = f"no-uid-{digest}"

        event = Event(
            uid=uid,
            recurrence_id=recurrence_id,
            sources=[source_name],
            summary=summary,
            start=start,
            end=end,
            all_day=all_day,
            status=status,
            transparency=transparency,
            busy=(status != "CANCELLED" and transparency != "TRANSPARENT" and (not all_day or cfg.all_day_busy)),
            location=_text(comp.get("LOCATION")),
            categories=categories,
            attendee_count=_attendee_count(comp),
            is_focus=_is_focus(summary, categories),
        )
        if status == "CANCELLED":
            # Keep cancelled events out of the report but count them in metrics.
            event.busy = False
        events.append(event)

    source = SourceInfo(
        path=str(path),
        name=source_name,
        bytes=stat.st_size,
        events_total=len(raw_events),
        events_in_week=len([e for e in events if e.status != "CANCELLED"]),
        warnings=[],
    )
    return source, events


def load_events(paths: list[str], cfg: Config) -> tuple[list[SourceInfo], list[Event], list[Warning], int, int, int]:
    """Load all calendars.

    Returns sources, de-duplicated events, warnings, duplicate count,
    cancelled count and transparent count.
    """
    if not paths:
        raise InputError("至少需要一个 .ics 文件。", code="no_input")
    if len(paths) > MAX_CALENDARS:
        raise InputError(
            f"一次最多读取 {MAX_CALENDARS} 个日历文件。",
            code="too_many_calendars",
            hint="先合并为较少的 .ics，或分多次运行。",
        )

    sources: list[SourceInfo] = []
    warnings: list[Warning] = []
    all_events: list[Event] = []
    duplicates = 0
    cancelled = 0
    transparent = 0

    for raw_path in paths:
        path = Path(raw_path).expanduser()
        source, events = _parse_one_file(path, cfg, warnings)
        sources.append(source)
        for event in events:
            if event.status == "CANCELLED":
                cancelled += 1
                continue
            if event.transparency == "TRANSPARENT":
                transparent += 1
            all_events.append(event)

    # Merge exact duplicate occurrences that appear in more than one export.
    by_key: dict[tuple, Event] = {}
    merged: list[Event] = []
    for event in all_events:
        key = (
            event.uid,
            event.recurrence_id or "",
            event.start.isoformat(),
            event.end.isoformat(),
            event.summary,
        )
        if key in by_key:
            existing = by_key[key]
            for source_name in event.sources:
                if source_name not in existing.sources:
                    existing.sources.append(source_name)
            duplicates += 1
            continue
        by_key[key] = event
        merged.append(event)

    merged.sort(key=lambda e: (e.start, e.end, e.summary.casefold(), e.uid))
    for source in sources:
        source.warnings = [w for w in warnings if w.source == source.name]
    return sources, merged, warnings, duplicates, cancelled, transparent
