"""Turn focus suggestions into a portable .ics file."""

from __future__ import annotations

import hashlib
from datetime import timezone

from icalendar import Calendar, Event as IcalEvent

from .config import Config
from .errors import NoSuggestionsError
from .model import Suggestion
from . import __version__


def build_plan(suggestions: list[Suggestion], cfg: Config) -> str:
    if not suggestions:
        raise NoSuggestionsError(
            f"本周没有可放入日历的专注块（最短 {cfg.min_focus_minutes} 分钟）。",
            code="no_suggestions",
            hint="可以减少会议、换一周，或把 --min-focus 调低后重试。",
        )
    calendar = Calendar()
    calendar.add("prodid", f"-//Weekglass//Focus Plan {__version__}//ZH")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("x-wr-calname", f"Weekglass 专注计划 {cfg.week_iso}")
    stamp = cfg.now.astimezone(timezone.utc)
    for suggestion in suggestions:
        digest = hashlib.sha1(
            f"{cfg.week_iso}|{suggestion.start.isoformat()}|{suggestion.end.isoformat()}|{suggestion.rank}".encode()
        ).hexdigest()[:16]
        event = IcalEvent()
        event.add("uid", f"weekglass-{digest}@weekglass.local")
        event.add("dtstamp", stamp)
        event.add("dtstart", suggestion.start.astimezone(timezone.utc))
        event.add("dtend", suggestion.end.astimezone(timezone.utc))
        event.add("summary", "专注块 · Weekglass")
        event.add(
            "description",
            (
                f"{suggestion.weekday} {suggestion.start:%H:%M}–{suggestion.end:%H:%M}"
                f"（{suggestion.minutes} 分钟）。{suggestion.reason}\n"
                f"由 Weekglass {__version__} 生成；导入前请确认与你的日历不冲突。"
            ),
        )
        event.add("transp", "OPAQUE")
        event.add("status", "CONFIRMED")
        event.add("categories", ["专注"])
        event.add("x-weekglass-tz", cfg.tz_name)
        calendar.add_component(event)
    return calendar.to_ical().decode("utf-8")
