"""Command line interface for Weekglass."""

from __future__ import annotations

import argparse
import os
import re
import sys
import traceback
from datetime import date, datetime, time
from pathlib import Path

from . import SCHEMA_VERSION, __version__
from .config import Config, load_config
from .errors import (
    CalendarError,
    ConfigError,
    InputError,
    NoSuggestionsError,
    OutputExistsError,
    OutputWriteError,
    UsageError,
    WeekglassError,
)
from .formatting import clock, date_range_label, duration, percent
from .ics import load_events
from .metrics import compute_metrics, suggest_focus_blocks
from .model import Report, Suggestion, Warning
from .outputs import is_stdout, preflight, reject_input_collisions, write_text
from .planner import build_plan
from .report import render_html, render_json
from .sample import DEMO_WEEK, PERSONAL_ICS, WORK_ICS

CLOCK_RANGE_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)-([01]\d|2[0-3]):([0-5]\d)$")
ANSI = {"bold": "\033[1m", "dim": "\033[2m", "green": "\033[32m", "reset": "\033[0m"}


class Parser(argparse.ArgumentParser):
    def error(self, message: str):  # pragma: no cover - argparse calls it
        raise UsageError(message, code="usage")


def _parse_clock_range(value: str, flag: str) -> tuple[time, time]:
    match = CLOCK_RANGE_RE.match(value)
    if not match:
        raise UsageError(f"{flag}={value!r} 不是 HH:MM-HH:MM 时间范围。", code="bad_time_range")
    start = time(int(match.group(1)), int(match.group(2)))
    end = time(int(match.group(3)), int(match.group(4)))
    if end <= start:
        raise UsageError(f"{flag}={value!r} 的结束时间必须晚于开始时间。", code="bad_time_range")
    return start, end


def _parse_lunch(value: str) -> tuple[time | None, time | None]:
    if value.strip().lower() == "off":
        return None, None
    return _parse_clock_range(value, "--lunch")


def _bounded_int(value: str, flag: str, minimum: int, maximum: int) -> int:
    try:
        number = int(value, 10)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{flag} 需要整数") from None
    if not minimum <= number <= maximum:
        raise argparse.ArgumentTypeError(f"{flag} 需要在 {minimum}–{maximum} 之间")
    return number


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--week", metavar="YYYY-MM-DD", help="一周中的任意一天；默认今天所在周（周一至周日）")
    parser.add_argument("--timezone", metavar="TZ", help="IANA 时区，例如 Asia/Shanghai；默认系统时区")
    parser.add_argument("--work-hours", metavar="HH:MM-HH:MM", help="工作时间，默认 09:00-18:00")
    parser.add_argument("--lunch", metavar="HH:MM-HH:MM|off", help="午休，默认 12:00-13:00；写 off 表示不计午休")
    parser.add_argument("--min-focus", type=lambda v: _bounded_int(v, "--min-focus", 15, 480), metavar="MIN", help="完整专注的最短分钟数，默认 90")
    parser.add_argument("--buffer", type=lambda v: _bounded_int(v, "--buffer", 0, 60), metavar="MIN", help="事件前后缓冲分钟数，默认 0")
    parser.add_argument("--max-suggestions", type=lambda v: _bounded_int(v, "--max-suggestions", 0, 20), metavar="N", help="最多建议几个专注块，默认 3")
    parser.add_argument("--max-per-day", type=lambda v: _bounded_int(v, "--max-per-day", 1, 10), metavar="N", help="每天最多建议几个，默认 1")
    parser.add_argument("--include-weekend", action="store_true", default=None, help="把周六、周日也计入可用时间")
    parser.add_argument("--all-day-busy", action="store_true", default=None, help="把全天事件当作整天占用")
    parser.add_argument("--no-color", action="store_true", default=None, help="不使用终端颜色")
    parser.add_argument("--now", metavar="ISO", help="仅用于复现：覆盖当前时间，需带时区偏移")
    parser.add_argument("--debug", action="store_true", help="显示调试信息和内部错误的堆栈")


def build_parser() -> Parser:
    parser = Parser(prog="weekglass", description="本地优先的日历碎片审计与专注计划。", add_help=True)
    parser.add_argument("--version", action="version", version=f"weekglass {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="命令")

    audit = sub.add_parser("audit", help="分析一周并生成报告", description="读取一个或多个 .ics 日历，输出本周时间预算、碎片和专注建议。")
    _common(audit)
    audit.add_argument("calendars", nargs="+", metavar="CALENDAR.ics", help="一个或多个 .ics 文件")
    audit.add_argument("--json", metavar="PATH", help="写入 JSON 报告；写 - 输出到标准输出")
    audit.add_argument("--html", metavar="PATH", help="写入单文件 HTML 报告；写 - 输出到标准输出")
    audit.add_argument("--plan-out", metavar="PATH", help="把专注建议写成可导入的 .ics；写 - 输出到标准输出")
    audit.add_argument("--force", action="store_true", help="覆盖已存在的输出文件")
    audit.add_argument("--quiet", action="store_true", help="不打印终端摘要")

    plan = sub.add_parser("plan", help="只生成专注块 .ics", description="分析日历并只输出可导入的专注块，不生成 HTML。")
    _common(plan)
    plan.add_argument("calendars", nargs="+", metavar="CALENDAR.ics", help="一个或多个 .ics 文件")
    plan.add_argument("--out", required=True, metavar="PATH", help="写入 .ics；写 - 输出到标准输出")
    plan.add_argument("--json", metavar="PATH", help="写入建议列表 JSON；写 - 输出到标准输出")
    plan.add_argument("--force", action="store_true", help="覆盖已存在的输出文件")
    plan.add_argument("--quiet", action="store_true", help="不打印终端摘要")

    demo = sub.add_parser("demo", help="生成示例日历和示例报告", description="在空目录中生成示例 .ics、HTML 报告、JSON 和专注块，不需要准备数据。")
    demo.add_argument("--out", default="weekglass-demo", metavar="DIR", help="输出目录，默认 ./weekglass-demo")
    demo.add_argument("--force", action="store_true", help="覆盖输出目录中已有的同名文件")
    demo.add_argument("--quiet", action="store_true", help="不打印终端提示")
    demo.add_argument("--now", metavar="ISO", help="仅用于复现：覆盖当前时间，需带时区偏移")

    version = sub.add_parser("version", help="显示版本")
    version.add_argument("--json", action="store_true", help="输出 JSON")
    return parser


def _overrides(args: argparse.Namespace) -> dict:
    result: dict = {}
    if getattr(args, "week", None):
        result["week"] = args.week
    if getattr(args, "timezone", None):
        result["timezone"] = args.timezone
    if getattr(args, "work_hours", None):
        result["work_hours"] = _parse_clock_range(args.work_hours, "--work-hours")
    if getattr(args, "lunch", None):
        result["lunch"] = _parse_lunch(args.lunch)
    for attr, key in (
        ("min_focus", "min_focus"),
        ("max_suggestions", "max_suggestions"),
        ("max_per_day", "max_per_day"),
        ("buffer", "buffer"),
    ):
        value = getattr(args, attr, None)
        if value is not None:
            result[key] = value
    if getattr(args, "include_weekend", None):
        result["include_weekend"] = True
    if getattr(args, "all_day_busy", None):
        result["all_day_busy"] = True
    if getattr(args, "no_color", None):
        result["no_color"] = True
    if getattr(args, "now", None):
        result["now"] = args.now
    return result


def _config(args: argparse.Namespace, extra: dict | None = None) -> Config:
    overrides = _overrides(args)
    if extra:
        overrides.update(extra)
    return load_config(os.environ, cli=overrides)


def _settings(cfg: Config) -> dict:
    return {
        "timezone": cfg.tz_name,
        "work_start": cfg.work_start.strftime("%H:%M"),
        "work_end": cfg.work_end.strftime("%H:%M"),
        "lunch_start": cfg.lunch_start.strftime("%H:%M") if cfg.lunch_start else "off",
        "lunch_end": cfg.lunch_end.strftime("%H:%M") if cfg.lunch_end else "off",
        "min_focus_minutes": cfg.min_focus_minutes,
        "max_suggestions": cfg.max_suggestions,
        "max_per_day": cfg.max_per_day,
        "buffer_minutes": cfg.buffer_minutes,
        "include_weekend": cfg.include_weekend,
        "all_day_busy": cfg.all_day_busy,
    }


def analyze(paths: list[str], cfg: Config, plan_path: str | None = None) -> tuple[Report, list[Suggestion], str | None]:
    sources, events, warnings, duplicates, cancelled, transparent = load_events(paths, cfg)
    metrics, days = compute_metrics(events, cfg, duplicates=duplicates, cancelled=cancelled, transparent=transparent)
    suggestions = suggest_focus_blocks(days, events, cfg)
    plan_text = build_plan(suggestions, cfg) if plan_path and suggestions else None
    report_events = events
    if len(events) > cfg.max_report_events:
        report_events = events[: cfg.max_report_events]
        if len(warnings) < 200:
            warnings.append(
                Warning(
                    code="report_truncated",
                    message=f"报告只列出前 {cfg.max_report_events} 个事件；统计仍使用全部 {len(events)} 个事件。",
                    source="",
                )
            )
    report = Report(
        schema_version=SCHEMA_VERSION,
        tool_name="weekglass",
        tool_version=__version__,
        generated_at=cfg.now,
        week_iso=cfg.week_iso,
        week_start=cfg.week_start,
        week_end=cfg.week_end,
        timezone=cfg.tz_name,
        settings=_settings(cfg),
        sources=sources,
        metrics=metrics,
        days=days,
        events=report_events,
        suggestions=suggestions,
        warnings=warnings,
        plan_path=(plan_path if plan_text else None),
    )
    return report, suggestions, plan_text


def _style(text: str, code: str) -> str:
    return f"{ANSI[code]}{text}{ANSI['reset']}"


def _print_error(exc: WeekglassError) -> None:
    print(f"错误[{exc.code}]：{exc.message}", file=sys.stderr)
    if exc.hint:
        print(f"提示：{exc.hint}", file=sys.stderr)


def _human_audit(report: Report, cfg: Config, json_path: str | None, html_path: str | None, plan_path: str | None) -> None:
    color = sys.stdout.isatty() and not cfg.no_color
    def bold(text: str) -> str:
        return _style(text, "bold") if color else text
    def dim(text: str) -> str:
        return _style(text, "dim") if color else text
    def green(text: str) -> str:
        return _style(text, "green") if color else text

    print(f"{bold('Weekglass')} {__version__} · {report.week_iso} · {report.timezone}")
    last_day = report.days[-1].date if report.days else report.week_start
    day_unit = "天" if cfg.include_weekend else "个工作日"
    print(f"{date_range_label(report.week_start, last_day)} · {len(report.days)} {day_unit}")
    print()
    m = report.metrics
    print(f"占用        {duration(m.busy_minutes)} / {duration(m.available_minutes)}（{percent(m.busy_pct)}）")
    print(f"{green('完整专注')}    {duration(m.focus_minutes)}（{m.focus_blocks} 块）")
    print(f"碎片空闲    {duration(m.fragmented_minutes)}（占空闲 {percent(m.fragmentation_pct)}）")
    print(f"最长空闲    {duration(m.longest_focus_minutes)}")
    print()
    for day in report.days:
        print(
            f"{day.weekday}  {duration(day.busy_minutes):>10} 占用 · "
            f"{day.focus_blocks} 块专注 · 最长 {duration(day.longest_focus_minutes)}"
        )
    print()
    if report.suggestions:
        print("建议：")
        for suggestion in report.suggestions:
            print(f"  {suggestion.rank}. {suggestion.weekday} {clock(suggestion.start)}–{clock(suggestion.end)}（{duration(suggestion.minutes)}）")
    else:
        print(f"这一周没有 ≥ {cfg.min_focus_minutes} 分钟的连续空闲。")
    outputs = []
    if html_path:
        outputs.append(("报告", html_path))
    if json_path:
        outputs.append(("JSON", json_path))
    if plan_path and report.plan_path:
        outputs.append(("专注计划", plan_path))
    if outputs:
        print()
        for label, path in outputs:
            print(f"{label}：{path}")
    if report.warnings:
        print()
        for warning in report.warnings[:5]:
            print(dim(f"提示：{warning.message}" + (f"（{warning.source}）" if warning.source else "")))
        if len(report.warnings) > 5:
            print(dim(f"另有 {len(report.warnings) - 5} 条提示，见报告。"))


def _write_outputs(args: argparse.Namespace, report: Report, cfg: Config, suggestions: list[Suggestion], plan_text: str | None) -> None:
    json_path = getattr(args, "json", None)
    html_path = getattr(args, "html", None)
    plan_path = getattr(args, "plan_out", None) or getattr(args, "out", None)
    paths = [path for path in (json_path, html_path, plan_path) if path]
    preflight(paths, args.force)

    plan_label = None
    html_plan_label = None
    if plan_path and plan_text:
        plan_label = "标准输出" if is_stdout(plan_path) else str(Path(plan_path).expanduser())
        html_plan_label = "标准输出" if is_stdout(plan_path) else Path(plan_path).expanduser().name
        report.plan_path = plan_label
    if json_path:
        write_text(json_path, render_json(report), force=args.force)
    if html_path:
        write_text(html_path, render_html(report, cfg, html_plan_label), force=args.force)
    if plan_path and plan_text:
        write_text(plan_path, plan_text, force=args.force)


def _stdout_used(args: argparse.Namespace) -> bool:
    return any(
        value == "-"
        for value in (getattr(args, "json", None), getattr(args, "html", None), getattr(args, "plan_out", None), getattr(args, "out", None))
    )


def run_audit(args: argparse.Namespace) -> int:
    cfg = _config(args)
    plan_path = args.plan_out
    paths = [path for path in (args.json, args.html, plan_path) if path]
    if paths:
        reject_input_collisions(paths, args.calendars)
        preflight(paths, args.force)
    report, suggestions, plan_text = analyze(args.calendars, cfg, plan_path)
    _write_outputs(args, report, cfg, suggestions, plan_text)
    if not args.quiet and not _stdout_used(args):
        _human_audit(report, cfg, args.json, args.html, plan_path if plan_text else None)
    elif args.plan_out and not suggestions:
        print(f"提示：本周没有 ≥ {cfg.min_focus_minutes} 分钟的连续空闲，未生成专注计划。", file=sys.stderr)
    return 0


def run_plan(args: argparse.Namespace) -> int:
    cfg = _config(args)
    if args.out == "-" and args.json == "-":
        raise UsageError("--out 和 --json 不能同时写标准输出。", code="two_stdout_outputs")
    paths = [path for path in (args.out, args.json) if path]
    reject_input_collisions(paths, args.calendars)
    preflight(paths, args.force)
    report, suggestions, plan_text = analyze(args.calendars, cfg, args.out if args.out != "-" else "-")
    if not suggestions:
        raise NoSuggestionsError(
            f"本周没有可放入日历的专注块（最短 {cfg.min_focus_minutes} 分钟）。",
            code="no_suggestions",
            hint="可以减少会议、换一周，或把 --min-focus 调低后重试。",
        )
    assert plan_text is not None
    write_text(args.out, plan_text, force=args.force)
    if args.json:
        import json

        payload = {
            "schema_version": SCHEMA_VERSION,
            "week": {"iso": report.week_iso, "start": report.week_start.isoformat(), "end": report.week_end.isoformat(), "timezone": report.timezone},
            "suggestions": [s.to_dict() for s in suggestions],
        }
        write_text(args.json, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", force=args.force)
    if not args.quiet and not _stdout_used(args):
        color = sys.stdout.isatty() and not cfg.no_color
        print(f"{_style('Weekglass', 'bold') if color else 'Weekglass'} {__version__} · {report.week_iso} · {report.timezone}")
        print("可放入日历的专注块：")
        for suggestion in suggestions:
            print(f"  {suggestion.rank}. {suggestion.weekday} {clock(suggestion.start)}–{clock(suggestion.end)}（{duration(suggestion.minutes)}）")
        print()
        print(f"已写入：{args.out}")
    return 0


def _ensure_demo_dir(path: Path, force: bool) -> None:
    if path.exists():
        if not path.is_dir():
            raise OutputExistsError(f"{path} 已存在且不是目录；换一个 --out。", code="output_exists")
        entries = list(path.iterdir())
        if entries and not force:
            raise OutputExistsError(f"{path} 不是空目录；加 --force 覆盖，或换一个 --out。", code="output_exists")
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OutputWriteError(f"无法创建目录 {path}：{exc.strerror or exc}。", code="write_failed") from None


def _check_demo_existing(path: Path, force: bool) -> None:
    """With --force, only overwrite the demo's own sample calendars.

    A real work.ics in the target directory must never be silently replaced;
    unknown files are also refused so --out $HOME cannot sweep a home directory.
    """
    if not force:
        return
    allowed = {"work.ics", "personal.ics", "report.html", "report.json", "focus.ics"}
    for entry in path.iterdir():
        if entry.name not in allowed:
            raise OutputExistsError(
                f"{path} 含非示例文件 {entry.name}；拒绝 --force 覆盖。换一个空目录。",
                code="output_exists",
            )
        if not entry.is_file():
            raise OutputExistsError(
                f"{path} 含同名目录 {entry.name}；换一个空目录。",
                code="output_exists",
            )
    for name, expected in (("work.ics", WORK_ICS), ("personal.ics", PERSONAL_ICS)):
        candidate = path / name
        if not candidate.exists():
            continue
        try:
            actual = candidate.read_text(encoding="utf-8")
        except OSError as exc:
            raise OutputExistsError(f"无法检查 {candidate}：{exc.strerror or exc}。", code="output_exists") from None
        if actual != expected:
            raise OutputExistsError(
                f"{candidate} 存在但不是示例文件；拒绝覆盖真实日历。换一个空目录，或先移走它。",
                code="output_exists",
            )


def run_demo(args: argparse.Namespace) -> int:
    if args.out == "-":
        raise UsageError("--out 需要一个目录，不能是 -。", code="bad_output")
    out = Path(args.out).expanduser()
    _ensure_demo_dir(out, args.force)
    cfg = _config(
        args,
        {
            "timezone": "Asia/Shanghai",
            "week": DEMO_WEEK,
        },
    )
    _check_demo_existing(out, args.force)
    work = out / "work.ics"
    personal = out / "personal.ics"
    report_path = out / "report.html"
    json_path = out / "report.json"
    plan_path = out / "focus.ics"
    preflight([str(report_path), str(json_path), str(plan_path)], args.force)
    for path, content in ((work, WORK_ICS), (personal, PERSONAL_ICS)):
        write_text(str(path), content, force=True)
    report, suggestions, plan_text = analyze([str(work), str(personal)], cfg, str(plan_path))
    _write_outputs(
        argparse.Namespace(
            json=str(json_path),
            html=str(report_path),
            plan_out=str(plan_path),
            out=None,
            force=args.force,
        ),
        report,
        cfg,
        suggestions,
        plan_text,
    )
    if not args.quiet:
        print(f"示例文件：{out.resolve()}")
        print(f"报告：{report_path}")
        print(f"专注计划：{plan_path}" + ("" if suggestions else "（本周没有可用专注块）"))
        print("用浏览器打开 report.html 查看；数据来自示例日历，可替换成你自己的 .ics。")
    return 0


def run_version(args: argparse.Namespace) -> int:
    if args.json:
        import json

        print(json.dumps({"name": "weekglass", "version": __version__, "schema_version": SCHEMA_VERSION}, ensure_ascii=False))
    else:
        print(f"weekglass {__version__}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if args.command == "audit":
            return run_audit(args)
        if args.command == "plan":
            return run_plan(args)
        if args.command == "demo":
            return run_demo(args)
        if args.command == "version":
            return run_version(args)
        raise UsageError("未知命令。", code="unknown_command")
    except WeekglassError as exc:
        _print_error(exc)
        return exc.exit_code
    except BrokenPipeError:
        return 0
    except KeyboardInterrupt:
        print("已中断。", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001 - last-resort friendly message
        debug = "--debug" in (argv if argv is not None else sys.argv[1:])
        print(f"错误[internal]：发生未预期的错误：{exc}", file=sys.stderr)
        if debug:
            traceback.print_exc()
        else:
            print("提示：加 --debug 重试可看到堆栈。", file=sys.stderr)
        return 1
