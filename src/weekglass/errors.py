"""Errors with stable codes and exit codes.

Every user-facing failure has a machine code, a Chinese message and an exit
code.  The CLI catches WeekglassError and prints the message without a
traceback unless --debug is set.
"""

from __future__ import annotations


class WeekglassError(Exception):
    """Base class for expected failures."""

    code = "internal"
    exit_code = 1

    def __init__(self, message: str, *, code: str | None = None, exit_code: int | None = None, hint: str | None = None):
        super().__init__(message)
        self.message = message
        self.hint = hint
        if code is not None:
            self.code = code
        if exit_code is not None:
            self.exit_code = exit_code


class UsageError(WeekglassError):
    code = "usage"
    exit_code = 2


class InputError(WeekglassError):
    code = "input_error"
    exit_code = 3


class CalendarError(WeekglassError):
    code = "invalid_calendar"
    exit_code = 4


class NoSuggestionsError(WeekglassError):
    code = "no_suggestions"
    exit_code = 5


class OutputExistsError(WeekglassError):
    code = "output_exists"
    exit_code = 6


class OutputWriteError(WeekglassError):
    code = "output_write_error"
    exit_code = 7


class ConfigError(WeekglassError):
    code = "config_error"
    exit_code = 8
