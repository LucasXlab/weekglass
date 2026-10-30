"""Configuration: defaults, environment variables and CLI overrides.

Only variables beginning with WEEKGLASS_ are read.  Invalid values stop the
command with exit code 8 and a message that names the variable and the
accepted range; nothing is silently repaired.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import ConfigError, UsageError
from .formatting import span_minutes

CLOCK_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
WEEK_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

DEFAULTS = {
    "WEEKGLASS_TZ": "",
    "WEEKGLASS_WORK_START": "09:00",
    "WEEKGLASS_WORK_END": "18:00",
    "WEEKGLASS_LUNCH_START": "12:00",
    "WEEKGLASS_LUNCH_END": "13:00",
    "WEEKGLASS_MIN_FOCUS_MINUTES": "90",
    "WEEKGLASS_MAX_SUGGESTIONS": "3",
    "WEEKGLASS_MAX_PER_DAY": "1",
    "WEEKGLASS_BUFFER_MINUTES": "0",
    "WEEKGLASS_INCLUDE_WEEKEND": "0",
    "WEEKGLASS_ALL_DAY_BUSY": "0",
    "WEEKGLASS_NO_COLOR": "0",
    "WEEKGLASS_MAX_FILE_MB": "20",
    "WEEKGLASS_MAX_EVENTS": "20000",
    "WEEKGLASS_MAX_REPORT_EVENTS": "5000",
    "WEEKGLASS_NOW": "",
}

WEEKDAY_NAMES = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def _local_zone_name() -> str:
    """Best-effort IANA zone for the current machine."""
    env_tz = os.environ.get("TZ", "").strip()
    if env_tz:
        return env_tz
    localtime = Path("/etc/localtime")
    try:
        target = str(localtime.resolve())
    except OSError:
        target = ""
    marker = "zoneinfo/"
    if marker in target:
        candidate = target.split(marker, 1)[1]
        try:
            ZoneInfo(candidate)
            return candidate
        except ZoneInfoNotFoundError:
            pass
    fixed = datetime.now().astimezone().tzinfo
    return getattr(fixed, "key", None) or "UTC"


def parse_clock(value: str, variable: str) -> time:
    if not CLOCK_RE.match(value):
        raise ConfigError(f"{variable}={value!r} 不是 HH:MM（00:00–23:59）。", code="bad_config")
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def parse_bool(value: str, variable: str) -> bool:
    if value == "1":
        return True
    if value == "0":
        return False
    raise ConfigError(f"{variable}={value!r} 只能是 1 或 0。", code="bad_config")


def parse_int(value: str, variable: str, minimum: int, maximum: int) -> int:
    try:
        number = int(value, 10)
    except ValueError:
        raise ConfigError(f"{variable}={value!r} 不是整数。", code="bad_config") from None
    if not minimum <= number <= maximum:
        raise ConfigError(f"{variable}={value!r} 超出范围，应为 {minimum}–{maximum} 的整数。", code="bad_config")
    return number


def parse_now(value: str, variable: str, tz: ZoneInfo) -> datetime:
    if not value:
        return datetime.now(tz).replace(microsecond=0)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ConfigError(f"{variable}={value!r} 不是 ISO 8601 时间，例如 2026-10-29T18:00:00+08:00。", code="bad_config") from None
    if parsed.tzinfo is None:
        raise ConfigError(f"{variable}={value!r} 必须带时区偏移，例如 +08:00 或 Z。", code="bad_config")
    return parsed.astimezone(tz).replace(microsecond=0)


def parse_week(value: str, tz: ZoneInfo) -> date:
    """Return the Monday of the ISO week containing value."""
    if not WEEK_RE.match(value):
        raise UsageError(f"--week={value!r} 不是 YYYY-MM-DD 日期。", code="bad_week")
    try:
        chosen = date.fromisoformat(value)
    except ValueError:
        raise UsageError(f"--week={value!r} 不是有效日期。", code="bad_week") from None
    return chosen - timedelta(days=chosen.weekday())


@dataclass(frozen=True)
class Config:
    tz_name: str
    tz: ZoneInfo
    work_start: time
    work_end: time
    lunch_start: time | None
    lunch_end: time | None
    min_focus_minutes: int
    max_suggestions: int
    max_per_day: int
    buffer_minutes: int
    include_weekend: bool
    all_day_busy: bool
    no_color: bool
    max_file_bytes: int
    max_events: int
    max_report_events: int
    now: datetime
    week_start: date

    @property
    def week_end(self) -> date:
        return self.week_start + timedelta(days=6)

    @property
    def days(self) -> tuple[date, ...]:
        count = 7 if self.include_weekend else 5
        return tuple(self.week_start + timedelta(days=i) for i in range(count))

    @property
    def week_iso(self) -> str:
        year, week, _ = self.week_start.isocalendar()
        return f"{year}-W{week:02d}"

    def day_window(self, day: date) -> tuple[datetime, datetime]:
        """Local start/end of the work window, before lunch is removed."""
        return (
            datetime.combine(day, self.work_start, tzinfo=self.tz),
            datetime.combine(day, self.work_end, tzinfo=self.tz),
        )

    def lunch_window(self, day: date) -> tuple[datetime, datetime] | None:
        if self.lunch_start is None or self.lunch_end is None:
            return None
        return (
            datetime.combine(day, self.lunch_start, tzinfo=self.tz),
            datetime.combine(day, self.lunch_end, tzinfo=self.tz),
        )

    def available_minutes(self, day: date) -> int:
        start, end = self.day_window(day)
        total = span_minutes(start, end)
        lunch = self.lunch_window(day)
        if lunch:
            total -= span_minutes(lunch[0], lunch[1])
        return total

    def week_bounds(self) -> tuple[datetime, datetime]:
        start = datetime.combine(self.week_start, time(0, 0), tzinfo=self.tz)
        end = start + timedelta(days=7)
        return start, end


def load_config(env: dict[str, str] | None = None, *, cli: dict | None = None) -> Config:
    """Build a Config from defaults, environment and already-parsed CLI values."""
    source = os.environ if env is None else env
    values = dict(DEFAULTS)
    for key in DEFAULTS:
        if key in source:
            values[key] = source[key]

    def fail(key: str, message: str, hint: str | None = None) -> ConfigError:
        return ConfigError(f"配置错误：{key}={values.get(key)!r}；{message}", code="bad_config", hint=hint)

    # Timezone first: it affects NOW and the week.
    tz_name = values["WEEKGLASS_TZ"].strip() or _local_zone_name()
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        raise fail("WEEKGLASS_TZ", f"找不到时区 {tz_name!r}，请使用 IANA 名称，例如 Asia/Shanghai。") from None

    work_start = parse_clock(values["WEEKGLASS_WORK_START"], "WEEKGLASS_WORK_START")
    work_end = parse_clock(values["WEEKGLASS_WORK_END"], "WEEKGLASS_WORK_END")
    if work_end <= work_start:
        raise fail("WEEKGLASS_WORK_END", "下班时间必须晚于上班时间。")

    lunch_start_s = values["WEEKGLASS_LUNCH_START"].strip().lower()
    lunch_end_s = values["WEEKGLASS_LUNCH_END"].strip().lower()
    if lunch_start_s == "off" or lunch_end_s == "off":
        if lunch_start_s != "off" or lunch_end_s != "off":
            raise ConfigError(
                f"配置错误：WEEKGLASS_LUNCH_START={values['WEEKGLASS_LUNCH_START']!r}，"
                f"WEEKGLASS_LUNCH_END={values['WEEKGLASS_LUNCH_END']!r}；午休开始和结束必须同时设为 off。",
                code="bad_config",
            )
        lunch_start = lunch_end = None
    else:
        lunch_start = parse_clock(values["WEEKGLASS_LUNCH_START"], "WEEKGLASS_LUNCH_START")
        lunch_end = parse_clock(values["WEEKGLASS_LUNCH_END"], "WEEKGLASS_LUNCH_END")
        if lunch_end <= lunch_start:
            raise ConfigError(
                f"配置错误：WEEKGLASS_LUNCH_START={values['WEEKGLASS_LUNCH_START']!r}，"
                f"WEEKGLASS_LUNCH_END={values['WEEKGLASS_LUNCH_END']!r}；午休结束必须晚于开始。",
                code="bad_config",
            )
        if lunch_start < work_start or lunch_end > work_end:
            raise fail(
                "WEEKGLASS_LUNCH_START",
                "午休必须落在工作时间内。",
                "把午休设进工作时段，或把 WEEKGLASS_LUNCH_START/END 都设为 off。",
            )

    min_focus = parse_int(values["WEEKGLASS_MIN_FOCUS_MINUTES"], "WEEKGLASS_MIN_FOCUS_MINUTES", 15, 480)
    max_suggestions = parse_int(values["WEEKGLASS_MAX_SUGGESTIONS"], "WEEKGLASS_MAX_SUGGESTIONS", 0, 20)
    max_per_day = parse_int(values["WEEKGLASS_MAX_PER_DAY"], "WEEKGLASS_MAX_PER_DAY", 1, 10)
    buffer = parse_int(values["WEEKGLASS_BUFFER_MINUTES"], "WEEKGLASS_BUFFER_MINUTES", 0, 60)
    max_file_mb = parse_int(values["WEEKGLASS_MAX_FILE_MB"], "WEEKGLASS_MAX_FILE_MB", 1, 100)
    max_events = parse_int(values["WEEKGLASS_MAX_EVENTS"], "WEEKGLASS_MAX_EVENTS", 100, 100000)
    max_report_events = parse_int(values["WEEKGLASS_MAX_REPORT_EVENTS"], "WEEKGLASS_MAX_REPORT_EVENTS", 100, 20000)
    include_weekend = parse_bool(values["WEEKGLASS_INCLUDE_WEEKEND"], "WEEKGLASS_INCLUDE_WEEKEND")
    all_day_busy = parse_bool(values["WEEKGLASS_ALL_DAY_BUSY"], "WEEKGLASS_ALL_DAY_BUSY")
    no_color = parse_bool(values["WEEKGLASS_NO_COLOR"], "WEEKGLASS_NO_COLOR")

    now = parse_now(values["WEEKGLASS_NOW"], "WEEKGLASS_NOW", tz)
    week_start = parse_week(now.date().isoformat(), tz)

    available = (work_end.hour * 60 + work_end.minute) - (work_start.hour * 60 + work_start.minute)
    if lunch_start and lunch_end:
        available -= (lunch_end.hour * 60 + lunch_end.minute) - (lunch_start.hour * 60 + lunch_start.minute)
    if min_focus > available:
        raise fail("WEEKGLASS_MIN_FOCUS_MINUTES", f"不能大于每天可用时间 {available} 分钟。")

    config = Config(
        tz_name=tz_name,
        tz=tz,
        work_start=work_start,
        work_end=work_end,
        lunch_start=lunch_start,
        lunch_end=lunch_end,
        min_focus_minutes=min_focus,
        max_suggestions=max_suggestions,
        max_per_day=max_per_day,
        buffer_minutes=buffer,
        include_weekend=include_weekend,
        all_day_busy=all_day_busy,
        no_color=no_color,
        max_file_bytes=max_file_mb * 1024 * 1024,
        max_events=max_events,
        max_report_events=max_report_events,
        now=now,
        week_start=week_start,
    )
    if cli:
        config = apply_cli(config, cli)
    return config


def apply_cli(config: Config, cli: dict) -> Config:
    """Apply CLI overrides.  Values are already parsed by argparse handlers."""
    changes: dict = {}
    if cli.get("timezone"):
        name = cli["timezone"]
        try:
            tz = ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            raise UsageError(f"--timezone={name!r} 找不到，请使用 IANA 名称，例如 Asia/Shanghai。", code="bad_timezone") from None
        changes["tz_name"] = name
        changes["tz"] = tz
        if not cli.get("now"):
            changes["now"] = config.now.astimezone(tz)
    if cli.get("work_hours"):
        start, end = cli["work_hours"]
        changes["work_start"] = start
        changes["work_end"] = end
    if cli.get("lunch"):
        changes["lunch_start"] = cli["lunch"][0]
        changes["lunch_end"] = cli["lunch"][1]
    if cli.get("min_focus") is not None:
        changes["min_focus_minutes"] = cli["min_focus"]
    if cli.get("max_suggestions") is not None:
        changes["max_suggestions"] = cli["max_suggestions"]
    if cli.get("max_per_day") is not None:
        changes["max_per_day"] = cli["max_per_day"]
    if cli.get("buffer") is not None:
        changes["buffer_minutes"] = cli["buffer"]
    if cli.get("include_weekend") is not None:
        changes["include_weekend"] = cli["include_weekend"]
    if cli.get("all_day_busy") is not None:
        changes["all_day_busy"] = cli["all_day_busy"]
    if cli.get("no_color") is not None:
        changes["no_color"] = cli["no_color"]
    if cli.get("now"):
        try:
            changes["now"] = parse_now(cli["now"], "--now", changes.get("tz", config.tz))
        except ConfigError as exc:
            raise UsageError(exc.message, code="bad_now") from None
    if changes:
        config = replace(config, **changes)
    if cli.get("week"):
        config = replace(config, week_start=parse_week(cli["week"], config.tz))
    elif "tz" in changes or "now" in changes:
        config = replace(config, week_start=parse_week(config.now.astimezone(config.tz).date().isoformat(), config.tz))
    # Re-validate combinations that CLI overrides can break.
    if config.work_end <= config.work_start:
        raise UsageError("--work-hours 的下班时间必须晚于上班时间。", code="bad_work_hours")
    if (config.lunch_start is None) != (config.lunch_end is None):
        raise UsageError("--lunch 必须同时给出开始和结束，或写 off。", code="bad_lunch")
    if config.lunch_start and (config.lunch_start < config.work_start or config.lunch_end > config.work_end):
        raise UsageError(
            "--lunch 必须落在工作时间内。",
            code="bad_lunch",
            hint="加 --lunch off，或把午休时间设进 --work-hours 的范围。",
        )
    if config.lunch_start and config.lunch_end <= config.lunch_start:
        raise UsageError("--lunch 的结束必须晚于开始。", code="bad_lunch")
    available = (config.work_end.hour * 60 + config.work_end.minute) - (config.work_start.hour * 60 + config.work_start.minute)
    if config.lunch_start and config.lunch_end:
        available -= (config.lunch_end.hour * 60 + config.lunch_end.minute) - (config.lunch_start.hour * 60 + config.lunch_start.minute)
    if config.min_focus_minutes > available:
        raise UsageError(f"--min-focus={config.min_focus_minutes} 大于每天可用时间 {available} 分钟。", code="bad_min_focus")
    return config
