# 功能说明

本文按用户可见行为说明 0.1.0；字段、退出码和算法的唯一契约是 [SPEC.md](../SPEC.md)。

## 1. 读多个 `.ics`，合并成一周

```bash
weekglass audit work.ics personal.ics --week 2026-10-26 --html report.html
```

- 一次 1–20 个文件，单文件默认 20 MB，展开后默认 20,000 个事件。
- 自动展开 RRULE、RDATE、EXDATE、RECURRENCE-ID；取消事件不进入报告，透明事件不占用，暂定事件按占用。
- 同一 UID、同一时间、同一标题的事件跨日历合并，`sources` 保留所有来源。
- 所有时间统一到 `WEEKGLASS_TZ`；无时区事件产生 `floating_time`，带未知 TZID 的产生 `unknown_tzid` 并写明实际解释时区。
- 契约：[SPEC §5.3、§6.2](../SPEC.md#53-sources)、[SPEC §6.2](../SPEC.md#62-展开时区与去重)。

## 2. 一周时间预算

`audit` 输出：

- 可用时间 = 工作时间 − 午休；
- 占用 = 合并后的忙碌区间（可加前后缓冲）；
- 完整专注 = 连续空闲 ≥ `--min-focus`（默认 90 分钟）；
- 碎片 = 短于阈值的空闲；
- 碎片率 = 碎片 / 空闲；
- 最长空闲、背靠背事件、工时外、周末、重复/取消/透明计数。
- 空周会加 `empty_week` 提示；默认不分析周末；周末事件在终端/报告里单独说明，不被静默算进可用时间。

终端示例（示例数据）：

```
占用        16 小时 45 分 / 40 小时（42%）
完整专注    10 小时 30 分（5 块）
碎片空闲    12 小时 45 分（占空闲 55%）
最长空闲    3 小时
```

- 契约：[SPEC §5.4、§6.3、§6.4](../SPEC.md#54-metrics)。

## 3. 专注块建议

- 从空闲区间按 15 分钟网格对齐；
- 单块最多 180 分钟；`--min-focus` 大于 180 时按 `--min-focus`；
- 评分偏向更长、上午、周二至周四；
- 默认每天最多 1 个、总共 3 个；
- 不覆盖已有占用，不跨午休。
- 输出不会覆盖输入 `.ics`；默认拒绝已存在的输出，`--force` 才覆盖（`demo` 只覆盖示例文件）。

```bash
weekglass plan work.ics personal.ics --week 2026-10-26 --out focus.ics
```

没有建议时 `plan` 退出 5；`audit --plan-out` 不写文件但退出 0。

- 契约：[SPEC §4.1、§4.2、§6.5](../SPEC.md#65-专注建议)。

## 4. 可导入的 `.ics`

- 每个建议一个 VEVENT；
- 摘要固定 `专注块 · Weekglass`；
- `DTSTART`/`DTEND` 用 UTC，`DTSTAMP` 取 `now`；
- UID 由周次、起止和序号哈希得到，同输入同 `now` 可复现；
- `TRANSP:OPAQUE`、`STATUS:CONFIRMED`、`CATEGORIES:专注`、`X-WEEKGLASS-TZ`；
- 导入前需用户自己确认不冲突。

- 契约：[SPEC §4.1、§4.2、§7](../SPEC.md#41-weekglass-audit-calendar-options)。

## 5. 单文件 HTML 报告

```bash
weekglass audit work.ics --week 2026-10-26 --html report.html --plan-out focus.ics
```

- 一个文件，内联 CSS，无 JS、无外部字体/图片/网络请求；
- 跟随系统浅色/深色；
- 375px 单列；时间带、按天表格、建议、算法说明、来源、可折叠事件明细；
- 事件标题/地点/来源文件名经 HTML 转义；CSP 禁止脚本与外部资源；
- 报告只显示来源文件名，不显示绝对路径；分享前仍需检查标题隐私。

- 契约：[SPEC §7](../SPEC.md#7-报告)、[DESIGN.md](../DESIGN.md)。

## 6. 确定性、隐私与错误

- 无网络、无账号、无遥测；只读输入文件。
- `WEEKGLASS_NOW` / `--now` 注入时钟；同输入同时间可复现 JSON/HTML/ICS。
- 输出默认拒绝覆盖，`--force` 才覆盖；写入用临时文件 + 原子替换。
- 统一中文错误：`错误[code]：说明`，必要时附 `提示：下一步`；退出码 2/3/4/5/6/7/8 区分参数、输入、日历、无建议、已存在、写入、配置。
- 契约：[SPEC §3、§4、§8](../SPEC.md#3-通用-cli-约定)。

## 7. 示例模式

```bash
weekglass demo --out weekglass-demo
```

固定 `2026-W44`、`Asia/Shanghai`，生成 `work.ics`、`personal.ics`、`focus.ics`、`report.json`、`report.html`；重复运行需要 `--force`。用于第一次体验和截图复现，不读取用户数据。

- 契约：[SPEC §4.3](../SPEC.md#43-weekglass-demo---out-dir---force---quiet---now-iso)。
