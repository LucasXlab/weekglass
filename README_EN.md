<p align="center"><img src="assets/logo.svg" width="380" alt="Weekglass"></p>

# Weekglass

**For anyone whose week is diced by meetings: turn 1–20 `.ics` calendars into a weekly time-budget report and a calendar-ready focus plan. Everything runs locally.**

English · [简体中文](README.md) · Python 3.11+ · MIT · 0.1.0

![Weekglass report: weekly time budget, timeline and focus suggestions](assets/report-light.png)

<sub>Sample data, 1280px light report. Dark mode and the 375px layout: [assets/report-dark.png](assets/report-dark.png), [assets/report-mobile.png](assets/report-mobile.png).</sub>

## Before you start

- **It reads `.ics` files only.** Weekglass does not connect to Google or Microsoft, does not ask for OAuth, and never moves or deletes a meeting. Export the calendar yourself.
- **It does not edit your calendar.** `focus.ics` is a separate file. Review it before importing.
- **The report contains private data.** Event titles, locations and file names appear in the HTML. The report makes no network requests, but check it before sharing.
- **The numbers depend on the export.** If recurrence rules, cancellation state or time zones are missing from the export, Weekglass cannot reconstruct them. Unknown time zones produce a warning.
- **0.1.0 does one workflow.** No tasks, time tracking, team scheduling, booking links or cloud sync.

## What it answers

You want to know which afternoons next week are actually free, but scrolling through a calendar only gives you a rough feeling. Meetings leave 30–60 minute holes that are too short for deep work, and the week disappears without a trace.

Weekglass turns that into three checkable questions:

1. How much of this week's available time is booked?
2. How fragmented is the free time?
3. Which full blocks could go back on the calendar next week?

It does not predict, score or judge your productivity. It just lays out the time budget.

## Features

### Merge multiple calendars first

Read 1–20 `.ics` files, expand recurrences, merge overlaps and de-duplicate events across calendars. Cancelled events are skipped; transparent events do not block time; tentative events do. Every time is normalized to the configured IANA time zone.

[Details and fields →](docs/features.md#1-读多个-ics合并成一周)

### A weekly time budget

Per day: available time, busy time, full focus, fragments, longest free block, back-to-back pairs, after-hours and weekend time. Defaults are 09:00–18:00, lunch 12:00–13:00, and a 90-minute focus threshold; all are configurable.

The CLI prints Chinese labels; the shape is:

```
占用        16 小时 45 分 / 40 小时（42%）
完整专注    10 小时 30 分（5 块）
碎片空闲    12 小时 45 分（占空闲 55%）
最长空闲    3 小时
```

[Metric definitions →](docs/features.md#2-一周时间预算) · [Formulas →](SPEC.md#63-每天指标)

### Focus suggestions

Free intervals are aligned to a 15-minute grid and capped at 180 minutes. Longer, morning and midweek blocks score higher; by default you get one per day and three in total. Suggestions never overlap a meeting or cross lunch.

```bash
weekglass plan work.ics personal.ics --week 2026-10-26 --out focus.ics
```

[Selection rules →](docs/features.md#3-专注块建议)

### A calendar-ready `.ics`

Each suggestion becomes an independent event with UTC timestamps, a deterministic UID, `TRANSP:OPAQUE` and `CATEGORIES:专注`. Import it into Google, Outlook or Apple Calendar; you can still move it afterwards.

[Output rules →](docs/features.md#4-可导入的-ics)

### A single-file HTML report

One local HTML file: timeline, daily table, suggestions, method, sources and a collapsible event list. No JavaScript, external fonts, images or requests. It follows the system light/dark preference and stays readable at 375px.

[Report guide →](docs/features.md#5-单文件-html-报告) · [Design rules →](DESIGN.md)

### Reproducible and inspectable

- No network, accounts or telemetry; inputs are opened read-only.
- `WEEKGLASS_NOW` or `--now` freezes the clock; the same input and time produce the same output.
- Existing outputs are refused unless `--force` is passed; files are written through a temp file and an atomic replace.
- Chinese errors with stable exit codes 2/3/4/5/6/7/8: what failed, where, and what to try next.

[Determinism and errors →](docs/features.md#6-确定性隐私与错误) · [Full contract →](SPEC.md)

## Who it is for — and who it is not

**Good fit:**

- Knowledge workers, graduate students and independent developers who can export `.ics` from Google, Outlook or Apple Calendar;
- people with five or more meetings a week who want to consolidate them and protect full blocks for deep work;
- people who care about privacy and do not want to hand a full calendar to a cloud scheduler, or who need an archival report.

**Poor fit:**

- teams that need automatic meeting moves, scheduling links or booking pages — use the calendar's booking page or a Reclaim/Clockwise-style tool;
- people looking for tasks, time tracking, a pomodoro timer or habit streaks — Weekglass only reads calendars;
- people with one quiet calendar and no meetings, or anyone unwilling to export `.ics` — manual blocking is faster.

## Quick start

### Requirements

- Python 3.11 or newer;
- a calendar that can export `.ics` (Google Calendar, Outlook, Apple Calendar, etc.);
- no account, API key, server or network.

### Install

```bash
python3 --version
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

On Windows, activate with `.venv\Scripts\activate`.

### See the demo first

```bash
weekglass demo --out weekglass-demo
```

This writes `work.ics`, `personal.ics`, `focus.ics`, `report.json` and `report.html`. Open `weekglass-demo/report.html` in a browser. The demo is pinned to `2026-W44` and `Asia/Shanghai`; it never reads your calendars.

Re-running requires `--force`:

```bash
weekglass demo --out weekglass-demo --force
```

### Use your own calendars

1. Export `.ics` from each calendar. Google Calendar: Settings → Import & export → Export. Outlook: Settings → Calendar → Shared calendars → Publish/download. Apple Calendar: select a calendar → File → Export → Export as `.ics`. Menus vary by version; look for the `.ics` extension.
2. Run:

```bash
weekglass audit work.ics personal.ics \
  --week 2026-10-26 \
  --timezone Asia/Shanghai \
  --html report.html \
  --plan-out focus.ics
```

3. Open `report.html`; review the suggestions; import `focus.ics`.

`--week` accepts any day in the target week and normalizes to Monday. The default is the current week.

### Minimal configuration

Everything is optional. The most useful variables are below; the full list, defaults and invalid-value behavior are in [SPEC §2](SPEC.md#2-配置).

| Variable | Default | Meaning |
|---|---|---|
| `WEEKGLASS_TZ` | system zone | IANA zone, e.g. `Asia/Shanghai` |
| `WEEKGLASS_WORK_START` / `WEEKGLASS_WORK_END` | `09:00` / `18:00` | Work window |
| `WEEKGLASS_LUNCH_START` / `WEEKGLASS_LUNCH_END` | `12:00` / `13:00` | Lunch must fall inside the work window; set both to `off` to disable |
| `WEEKGLASS_MIN_FOCUS_MINUTES` | `90` | Minimum full-focus block |
| `WEEKGLASS_NOW` | current time | Offset-aware ISO time; for reproduction, not daily use |

See [.env.example](.env.example). Weekglass does not load `.env` automatically; export the variables or pass CLI flags.

## Commands

| Command | Purpose |
|---|---|
| `weekglass audit CALENDAR...` | Analyze a week, print a summary, optionally write JSON/HTML/plan |
| `weekglass plan CALENDAR... --out PATH` | Write only the focus `.ics` |
| `weekglass demo --out DIR` | Generate the fixed demo |
| `weekglass version` | Print the version; `--json` for machines |
| `weekglass --help` | List commands |

Every flag, exit code and JSON field is in [SPEC §3–§5](SPEC.md#3-通用-cli-约定).

## Upgrade

Replace the code directory, reinstall, and check the version:

```bash
python -m pip install -e .
weekglass --version
```

There is no database, migration or background state; old reports are never rewritten.

## Documentation

- [SPEC.md](SPEC.md) — the single contract (commands, fields, algorithms, errors, tests)
- [DESIGN.md](DESIGN.md) — report design, tokens, 375px rules
- [docs/features.md](docs/features.md) — user-visible features
- [docs/development.md](docs/development.md) — environment, layout, tests, packaging
- [docs/deviations.md](docs/deviations.md) — documented deviations
- [docs/external-apis.md](docs/external-apis.md) — external API review (0.1.0 has no runtime network API)
- [docs/选题.md](docs/选题.md) — why this project, competitors and evidence
- [notes/决定.md](notes/决定.md) — key decisions
- [CHANGELOG.md](CHANGELOG.md) — release notes

## Development

```bash
python -m pip install -e '.[dev]'
pytest -q
```

Tests run offline, in temporary directories, with a frozen clock. They do not read real calendars and are never skipped. Design tokens and the 375px layout have their own tests.

## Known limitations

- An unknown `TZID` is interpreted in the configured zone and named in the warning; a genuinely unknown zone can still shift times.
- Two events with the same wall-clock time during a DST fall-back cannot be distinguished; they may be merged.
- Generated `.ics` uses UTC and no VTIMEZONE. Mainstream clients import it; very old clients may not display the local zone.
- The HTML report shows source file names, not absolute paths; the JSON keeps the passed path, so check it before sharing.
- Files written directly with `--html`/`--json` use mode 0600 on POSIX; shell `>` redirection follows shell/umask (commonly 0644). Windows permissions are not guaranteed to match.

## License

MIT. See [LICENSE](LICENSE).
