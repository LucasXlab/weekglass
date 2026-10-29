from __future__ import annotations

from datetime import time

import pytest

from weekglass.config import load_config
from weekglass.errors import ConfigError, UsageError

from .conftest import NOW, make_config


def test_defaults_and_week():
    cfg = make_config()
    assert cfg.tz_name == "Asia/Shanghai"
    assert cfg.work_start == time(9, 0)
    assert cfg.work_end == time(18, 0)
    assert cfg.lunch_start == time(12, 0)
    assert cfg.lunch_end == time(13, 0)
    assert cfg.min_focus_minutes == 90
    assert cfg.max_suggestions == 3
    assert cfg.max_per_day == 1
    assert cfg.buffer_minutes == 0
    assert cfg.include_weekend is False
    assert cfg.all_day_busy is False
    assert cfg.week_start.isoformat() == "2026-10-26"
    assert cfg.week_end.isoformat() == "2026-11-01"
    assert cfg.week_iso == "2026-W44"
    assert [d.isoformat() for d in cfg.days] == [
        "2026-10-26",
        "2026-10-27",
        "2026-10-28",
        "2026-10-29",
        "2026-10-30",
    ]
    assert cfg.now == NOW


def test_week_normalizes_any_day_and_weekend():
    cfg = make_config(cli={"week": "2026-10-28"})
    assert cfg.week_start.isoformat() == "2026-10-26"
    cfg = make_config(cli={"week": "2026-11-01", "include_weekend": True})
    assert cfg.week_start.isoformat() == "2026-10-26"
    assert len(cfg.days) == 7
    assert cfg.days[-1].isoformat() == "2026-11-01"


def test_cli_timezone_converts_generated_now():
    cfg = make_config(env={"WEEKGLASS_NOW": "2026-10-29T10:00:00+00:00"}, cli={"timezone": "Asia/Tokyo"})
    assert cfg.tz_name == "Asia/Tokyo"
    assert cfg.now.isoformat() == "2026-10-29T19:00:00+09:00"
    assert cfg.week_start.isoformat() == "2026-10-26"


def test_cli_now_recomputes_week():
    cfg = make_config(cli={"now": "2026-01-07T12:00:00+08:00"})
    assert cfg.week_start.isoformat() == "2026-01-05"
    assert cfg.week_iso == "2026-W02"


def test_env_overrides_and_lunch_off():
    cfg = make_config(
        env={
            "WEEKGLASS_WORK_START": "10:00",
            "WEEKGLASS_WORK_END": "17:00",
            "WEEKGLASS_LUNCH_START": "off",
            "WEEKGLASS_LUNCH_END": "off",
            "WEEKGLASS_MIN_FOCUS_MINUTES": "60",
            "WEEKGLASS_MAX_SUGGESTIONS": "0",
            "WEEKGLASS_MAX_PER_DAY": "2",
            "WEEKGLASS_BUFFER_MINUTES": "5",
            "WEEKGLASS_INCLUDE_WEEKEND": "1",
            "WEEKGLASS_ALL_DAY_BUSY": "1",
            "WEEKGLASS_NO_COLOR": "1",
        }
    )
    assert cfg.work_start == time(10, 0)
    assert cfg.work_end == time(17, 0)
    assert cfg.lunch_start is None and cfg.lunch_end is None
    assert cfg.available_minutes(cfg.week_start) == 420
    assert cfg.min_focus_minutes == 60
    assert cfg.max_suggestions == 0
    assert cfg.max_per_day == 2
    assert cfg.buffer_minutes == 5
    assert cfg.include_weekend is True
    assert cfg.all_day_busy is True
    assert cfg.no_color is True


def test_cli_lunch_off_and_work_hours():
    cfg = make_config(cli={"work_hours": (time(8, 0), time(16, 0)), "lunch": (None, None), "min_focus": 15})
    assert cfg.available_minutes(cfg.week_start) == 480
    assert cfg.min_focus_minutes == 15


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("WEEKGLASS_TZ", "No/Such_Zone"),
        ("WEEKGLASS_WORK_START", "9:00"),
        ("WEEKGLASS_WORK_END", "08:00"),
        ("WEEKGLASS_LUNCH_START", "off"),
        ("WEEKGLASS_LUNCH_END", "off"),
        ("WEEKGLASS_LUNCH_START", "17:00"),
        ("WEEKGLASS_MIN_FOCUS_MINUTES", "14"),
        ("WEEKGLASS_MIN_FOCUS_MINUTES", "481"),
        ("WEEKGLASS_MIN_FOCUS_MINUTES", "999"),
        ("WEEKGLASS_MAX_SUGGESTIONS", "21"),
        ("WEEKGLASS_MAX_PER_DAY", "0"),
        ("WEEKGLASS_BUFFER_MINUTES", "61"),
        ("WEEKGLASS_INCLUDE_WEEKEND", "2"),
        ("WEEKGLASS_ALL_DAY_BUSY", "yes"),
        ("WEEKGLASS_NO_COLOR", "true"),
        ("WEEKGLASS_MAX_FILE_MB", "0"),
        ("WEEKGLASS_MAX_EVENTS", "99"),
        ("WEEKGLASS_MAX_REPORT_EVENTS", "99"),
        ("WEEKGLASS_NOW", "2026-10-29T18:00:00"),
        ("WEEKGLASS_NOW", "not-a-date"),
    ],
)
def test_invalid_env_exits_config_error(key, value):
    env = {"WEEKGLASS_TZ": "Asia/Shanghai", "WEEKGLASS_NOW": NOW.isoformat(), key: value}
    with pytest.raises(ConfigError) as exc:
        load_config(env)
    assert exc.value.exit_code == 8
    assert key in exc.value.message


def test_invalid_env_is_not_rescued_by_cli():
    env = {"WEEKGLASS_TZ": "Asia/Shanghai", "WEEKGLASS_NOW": NOW.isoformat(), "WEEKGLASS_MIN_FOCUS_MINUTES": "999"}
    with pytest.raises(ConfigError):
        load_config(env, cli={"min_focus": 60})


@pytest.mark.parametrize(
    ("cli", "code"),
    [
        ({"timezone": "No/Such_Zone"}, "bad_timezone"),
        ({"week": "2026-1-1"}, "bad_week"),
        ({"week": "2026-02-30"}, "bad_week"),
        ({"now": "2026-10-29T18:00:00"}, "bad_now"),
        ({"now": "not-a-date"}, "bad_now"),
        ({"work_hours": (time(18, 0), time(9, 0))}, "bad_work_hours"),
        ({"lunch": (None, time(13, 0))}, "bad_lunch"),
        ({"lunch": (time(8, 0), time(13, 0))}, "bad_lunch"),
        ({"min_focus": 481}, "bad_min_focus"),
    ],
)
def test_invalid_cli_usage_error(cli, code):
    if cli.get("work_hours") == (time(18, 0), time(9, 0)):
        # Work hours are normally validated before reaching Config.apply_cli.
        cli = {"work_hours": (time(18, 0), time(9, 0))}
    with pytest.raises(UsageError) as exc:
        make_config(cli=cli)
    assert exc.value.exit_code == 2
    assert exc.value.code == code


def test_local_zone_fallback_and_tz_env(monkeypatch):
    monkeypatch.setenv("TZ", "Asia/Shanghai")
    env = {"WEEKGLASS_NOW": NOW.isoformat()}
    cfg = load_config(env)
    assert cfg.tz_name == "Asia/Shanghai"
