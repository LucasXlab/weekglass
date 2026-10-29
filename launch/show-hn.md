# Show HN: Weekglass – audit calendar fragmentation from .ics files, locally

I am a developer who kept ending each week unsure where the time went. My calendar had plenty of free gaps, but they were 30–60 minutes long, and I could not tell how fragmented the week actually was.

Weekglass is a small local CLI. You export one or more `.ics` files, run `weekglass audit`, and get:

- a weekly time budget: available, busy, full focus blocks, fragments, longest free block;
- a single-file HTML report with a timeline and per-day table;
- a `focus.ics` with suggested focus blocks that you can import yourself.

It does not use OAuth, call a calendar API, or move meetings. It reads the exported files, computes everything locally, and writes local outputs. There is no account, server or telemetry.

A demo is one command:

```
pip install -e .
weekglass demo --out weekglass-demo
```

Then open `weekglass-demo/report.html`.

A few deliberate choices:

- No LLM. The numbers are deterministic arithmetic so you can check them.
- No auto-scheduling. The tool suggests; you decide what to import.
- Defaults: 09:00–18:00 work window, 12:00–13:00 lunch, 90-minute minimum focus block. All configurable.
- Known limits: unknown `TZID` values may become floating times; DST fall-back can merge identical wall-clock events; generated `.ics` uses UTC.

I would appreciate feedback on the metric definitions, the HTML report, and whether the 90-minute default matches how you actually plan deep work. Repository: (add the repository URL when publishing).

## First comment

The report is a static HTML file with no JavaScript. The demo is pinned to 2026-W44 and Asia/Shanghai so screenshots and numbers are reproducible. The test suite runs offline and replaces socket calls with failures, so a network request would break the tests.
