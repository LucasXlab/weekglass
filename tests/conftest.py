from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from weekglass.config import Config, load_config
from weekglass.model import Event

SHANGHAI = ZoneInfo("Asia/Shanghai")
NOW = datetime(2026, 10, 29, 18, 0, tzinfo=SHANGHAI)


@pytest.fixture(autouse=True)
def clean_weekglass_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("WEEKGLASS_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("WEEKGLASS_TZ", "Asia/Shanghai")
    monkeypatch.setenv("WEEKGLASS_NOW", NOW.isoformat())


def make_config(env: dict[str, str] | None = None, cli: dict | None = None) -> Config:
    base = {"WEEKGLASS_TZ": "Asia/Shanghai", "WEEKGLASS_NOW": NOW.isoformat()}
    if env:
        base.update(env)
    return load_config(base, cli=cli)


def make_event(
    start: datetime,
    end: datetime,
    *,
    summary: str = "事件",
    uid: str | None = None,
    busy: bool = True,
    all_day: bool = False,
    status: str = "CONFIRMED",
    transparency: str = "OPAQUE",
    sources: list[str] | None = None,
) -> Event:
    return Event(
        uid=uid or f"uid-{summary}-{start.isoformat()}",
        recurrence_id=None,
        sources=sources or ["test.ics"],
        summary=summary,
        start=start,
        end=end,
        all_day=all_day,
        status=status,
        transparency=transparency,
        busy=busy,
    )


def at(day: int, hour: int, minute: int = 0, *, month: int = 10, year: int = 2026) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=SHANGHAI)


def write_ics(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def vevent(
    *,
    uid: str,
    start: str,
    end: str | None = None,
    summary: str = "事件",
    extra: str = "",
    all_day: bool = False,
    duration: str | None = None,
) -> str:
    lines = ["BEGIN:VEVENT", f"UID:{uid}", "DTSTAMP:20261001T000000Z"]
    if all_day:
        lines += [f"DTSTART;VALUE=DATE:{start}"]
        if end:
            lines += [f"DTEND;VALUE=DATE:{end}"]
    else:
        lines += [f"DTSTART;TZID=Asia/Shanghai:{start}"]
        if end:
            lines += [f"DTEND;TZID=Asia/Shanghai:{end}"]
        if duration:
            lines += [f"DURATION:{duration}"]
    lines += [f"SUMMARY:{summary}"]
    if extra:
        lines += [line for line in extra.strip().splitlines() if line]
    lines += ["END:VEVENT"]
    return "\n".join(lines)


def calendar(*events: str, name: str = "TEST") -> str:
    return "\n".join(
        ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:-//Weekglass Test//{name}//ZH", *events, "END:VCALENDAR", ""]
    )


def simple_ics(tmp_path: Path, name: str = "one.ics", *events: str) -> Path:
    return write_ics(tmp_path, name, calendar(*events))
