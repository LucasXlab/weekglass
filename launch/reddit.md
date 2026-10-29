# Reddit draft

Suggested communities: r/productivity, r/opensource. Read each community's self-promotion rules first; do not cross-post the same text on the same day.

## Title

I built a local CLI that audits calendar fragmentation from .ics exports

## Body

I have a calendar full of 30–60 minute gaps and no good way to see whether the week was actually fragmented or just busy. Cloud schedulers can move meetings for me, but I did not want to hand over a full calendar or let a tool edit events.

Weekglass takes one or more `.ics` exports and produces:

- a weekly budget: available time, busy time, full focus blocks, fragments, longest free block;
- a static HTML report with a timeline and daily table;
- an optional `focus.ics` with suggested focus blocks.

It runs locally, has no account or network calls, and does not modify the input files.

```
pip install -e .
weekglass demo --out weekglass-demo
```

What I am unsure about:

- Is the “fragmentation rate” (fragments ÷ free time) useful, or is “longest free block” enough?
- The default focus threshold is 90 minutes. Is that too long for your calendar?
- Would you rather import a plan file or copy blocks manually?

Known limitations: unknown time zones in the export can become floating times; DST fall-back can merge events with the same wall-clock time; generated `.ics` uses UTC.

Repository: (add the repository URL when publishing). Feedback on the metric definitions is more useful to me than stars.
