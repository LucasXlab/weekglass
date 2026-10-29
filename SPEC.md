# Weekglass 0.1.0 规格

本文件是唯一契约。命令、字段名、枚举值、默认值、退出码和数字必须与实现一致。开发中任何偏离都记入 [docs/deviations.md](docs/deviations.md)，不在代码里悄悄改。

## 0. 产品说明与范围

Weekglass（周镜）是一个本地优先的命令行工具。它读取用户导出的一个或多个 `.ics` 日历文件，计算指定一周的占用、碎片和完整空闲，给出可导入日历的专注块，并生成单文件 HTML 报告。它不联网、不登录、不调用日历 API、不自动修改日历。

第一版只做这一条核心流程：

1. 用户从 Google Calendar、Outlook 或 Apple 日历导出 1–20 个 `.ics` 文件。
2. 运行 `weekglass audit work.ics personal.ics --week 2026-10-26 --html report.html --plan-out focus.ics`。
3. 终端得到本周摘要；`report.html` 得到按天时间带、指标、建议和数据来源；`focus.ics` 可导入日历。
4. 用户确认 `focus.ics` 与现有安排不冲突后导入。

### 非目标

- 不做 Google/Microsoft OAuth，不调用任何日历 API。
- 不自动移动、删除或修改用户已有事件。
- 不做团队排期、会议室预订、预约链接、多人协作。
- 不做任务清单、时间追踪、应用使用统计、番茄钟、习惯打卡。
- 不做账号、云同步、数据库、服务端、HTTP 接口。
- 不做 LLM、自然语言问答、内容生成；所有输出由确定性计算得到。
- 不支持直接编辑重复事件规则；重复事件只读。
- 不保证识别所有厂商的私有扩展；未知组件按 RFC 5545 忽略。
- 不发布到 PyPI/npm；安装方式是从本地仓库安装。

## 1. 目录、技术栈与安装

```
weekglass/
  SPEC.md
  DESIGN.md
  pyproject.toml
  src/weekglass/
    cli.py config.py errors.py formatting.py ics.py metrics.py model.py
    outputs.py planner.py report.py sample.py
    templates/report.html.j2
  tests/
  docs/
  notes/
  launch/
```

- Python：最低 3.11，CI 覆盖 3.11、3.12、3.13。本地开发使用 3.13.5。
- 构建：hatchling 1.33.0；包名 `weekglass`，版本 `0.1.0`。
- 运行依赖（精确版本）：
  - `icalendar==7.3.0`
  - `recurring-ical-events==3.8.2`
  - `python-dateutil==2.9.0.post0`
  - `Jinja2==3.1.6`
  - `tzdata==2026.6`（Windows 和无系统时区库的环境使用）
- 开发依赖：`pytest==9.2.0`。
- 安装（在仓库根目录）：
  - `python3 -m venv .venv && . .venv/bin/activate`
  - `python -m pip install -e '.[dev]'`
  - 或 `pipx install .` / `uv tool install .`（发布由维护者决定）。
- 运行：`weekglass <command>` 或 `python -m weekglass <command>`。
- 不监听端口，不写数据库，不读取项目目录以外的配置（只读取显式传入的文件和 `WEEKGLASS_*` 环境变量）。
- 一次最多读取 20 个日历文件；单文件默认上限 20 MB；展开后事件默认上限 20,000 个。

## 2. 配置

优先级：命令行参数 > 环境变量 > 内置默认值。环境变量只读取 `WEEKGLASS_` 前缀；不读取 `TZ` 以外的通用名，不读取任何密钥类变量。所有环境变量在读取日历前校验；非法值拒绝执行，退出码 8，错误信息包含变量名、当前值和允许范围。命令行参数的非法值退出码 2。若环境变量非法，即使命令行给了合法覆盖值，也仍然退出 8。

| 变量 | 默认 | 必填 | 合法值 | 非法时 |
|---|---|---|---|---|
| `WEEKGLASS_TZ` | 系统 IANA 时区；无法判断时为 `UTC` | 否 | `ZoneInfo` 能识别的 IANA 名称，例如 `Asia/Shanghai` | 退出 8，提示用 IANA 名称 |
| `WEEKGLASS_WORK_START` | `09:00` | 否 | `HH:MM`，00:00–23:59 | 退出 8 |
| `WEEKGLASS_WORK_END` | `18:00` | 否 | `HH:MM`，必须晚于开始 | 退出 8 |
| `WEEKGLASS_LUNCH_START` | `12:00` | 否 | `HH:MM` 或 `off` | 退出 8 |
| `WEEKGLASS_LUNCH_END` | `13:00` | 否 | `HH:MM` 或 `off`，必须与开始同时为 `off` | 退出 8 |
| `WEEKGLASS_MIN_FOCUS_MINUTES` | `90` | 否 | 15–480 的整数，且不大于每天可用分钟数 | 退出 8 |
| `WEEKGLASS_MAX_SUGGESTIONS` | `3` | 否 | 0–20 的整数 | 退出 8 |
| `WEEKGLASS_MAX_PER_DAY` | `1` | 否 | 1–10 的整数 | 退出 8 |
| `WEEKGLASS_BUFFER_MINUTES` | `0` | 否 | 0–60 的整数 | 退出 8 |
| `WEEKGLASS_INCLUDE_WEEKEND` | `0` | 否 | `1` 或 `0` | 退出 8 |
| `WEEKGLASS_ALL_DAY_BUSY` | `0` | 否 | `1` 或 `0` | 退出 8 |
| `WEEKGLASS_NO_COLOR` | `0` | 否 | `1` 或 `0` | 退出 8 |
| `WEEKGLASS_MAX_FILE_MB` | `20` | 否 | 1–100 的整数 | 退出 8 |
| `WEEKGLASS_MAX_EVENTS` | `20000` | 否 | 100–100000 的整数 | 退出 8 |
| `WEEKGLASS_MAX_REPORT_EVENTS` | `5000` | 否 | 100–20000 的整数 | 退出 8 |
| `WEEKGLASS_NOW` | 空 | 否 | 带时区偏移的 ISO 8601，例如 `2026-10-29T18:00:00+08:00`；空表示当前时间 | 退出 8 |

- 午休必须在工作时间内；开始和结束必须同时为 `off` 或同时为时间。
- 每天可用分钟数 = 工作时间长度 − 午休长度（午休为 `off` 时只减工作时间）。
- 所有时间按 `WEEKGLASS_TZ` 解释。事件自带时区时先转换到该时区；无时区事件按该时区解释并产生 `floating_time` 提示。
- 任何接口和日志都不输出密钥；本工具没有密钥。

## 3. 通用 CLI 约定

- 程序名：`weekglass`。
- 退出码：

| 码 | 含义 |
|---:|---|
| 0 | 成功 |
| 1 | 未预期的内部错误 |
| 2 | 命令行参数错误（含 `--week`、`--now`、数值范围、互斥输出） |
| 3 | 输入文件不存在、不是普通文件、不可读 |
| 4 | 日历内容错误、文件过大、展开后事件过多、重复规则无法展开 |
| 5 | `plan` 找不到任何专注块 |
| 6 | 输出已存在且未加 `--force`，或演示目录非空 |
| 7 | 创建目录或写入输出失败 |
| 8 | 环境变量配置错误 |
| 130 | 用户按 Ctrl-C 中断 |

- 错误输出到 stderr，格式固定：`错误[<code>]：<中文说明>`；有下一步建议时另起一行 `提示：<中文说明>`。默认不打印 Python 堆栈；`--debug` 才打印。
- 成功时人类摘要输出到 stdout；`--quiet` 抑制人类摘要，但不抑制错误。
- 颜色只在 stdout 是终端且未设置 `WEEKGLASS_NO_COLOR=1` / `--no-color` 时使用。管道/重定向时自动关闭。
- 时间在终端和 HTML 中显示为 `HH:MM`；JSON 中为带偏移的 ISO 8601。日期为 `YYYY-MM-DD`。
- 周口径：ISO 周，周一到周日。`--week` 给该周任意一天，内部归一到周一。默认是 `now` 所在周的周一。分析日默认周一到周五；`--include-weekend` 时七天全部纳入可用时间。
- 输出路径：
  - 支持 `-` 表示 stdout；同一命令最多一个输出写 stdout，否则退出 2。
  - 非 stdout 输出先创建父目录；已存在且未加 `--force` 时退出 6；写入用同目录临时文件 + 原子替换。
  - 两个输出参数指向同一路径时退出 2。
  - 所有输出在读取日历前做存在性检查。
- `--force` 只影响输出文件，不改变输入文件。
- 任何命令都不修改输入 `.ics`。

## 4. 命令

### 4.1 `weekglass audit CALENDAR... [options]`

读取 1–20 个 `.ics`，输出摘要，可选 JSON/HTML/专注块。

参数：

| 参数 | 必填 | 说明 |
|---|---|---|
| `CALENDAR...` | 是 | 1–20 个 `.ics` 路径；支持 `~` 展开；shell 负责通配符展开 |
| `--week YYYY-MM-DD` | 否 | 默认今天所在周 |
| `--timezone TZ` | 否 | 覆盖 `WEEKGLASS_TZ` |
| `--work-hours HH:MM-HH:MM` | 否 | 覆盖工作开始/结束 |
| `--lunch HH:MM-HH:MM\|off` | 否 | 覆盖午休 |
| `--min-focus MIN` | 否 | 15–480，覆盖最短专注 |
| `--buffer MIN` | 否 | 0–60，事件前后缓冲 |
| `--max-suggestions N` | 否 | 0–20，默认 3 |
| `--max-per-day N` | 否 | 1–10，默认 1 |
| `--include-weekend` | 否 | 周六、周日纳入可用时间 |
| `--all-day-busy` | 否 | 全天事件按整天占用 |
| `--json PATH\|-` | 否 | 写 JSON 报告 |
| `--html PATH\|-` | 否 | 写单文件 HTML 报告 |
| `--plan-out PATH\|-` | 否 | 写专注块 `.ics`；没有建议时不写，命令仍成功 |
| `--force` | 否 | 覆盖已有输出 |
| `--quiet` | 否 | 不打印人类摘要 |
| `--now ISO` | 否 | 覆盖当前时间，必须带偏移；用于复现 |
| `--no-color` | 否 | 关闭颜色 |
| `--debug` | 否 | 内部错误时打印堆栈 |

行为：

1. 校验配置和输出路径。
2. 读取每个文件；解析失败、超过大小/事件上限时按第 3 节退出。
3. 展开重复事件，转换时区，过滤取消事件，合并跨日历重复事件。
4. 计算指标和建议。
5. 若给了 `--json`、`--html`、`--plan-out`，按顺序写入；`--plan-out` 只在有建议时写。
6. 没有 stdout 输出且未 `--quiet` 时打印摘要。
7. 没有专注块时：摘要打印“没有 ≥ N 分钟的连续空闲”；`--plan-out` 不写文件；退出 0。

JSON 输出时 stdout 只包含 JSON，不混入摘要；HTML/ICS 同理。

### 4.2 `weekglass plan CALENDAR... --out PATH [options]`

与 `audit` 共用分析参数，只生成专注块。

| 参数 | 必填 | 说明 |
|---|---|---|
| `CALENDAR...` | 是 | 1–20 个 `.ics` |
| `--out PATH\|-` | 是 | 写 `.ics` |
| `--json PATH\|-` | 否 | 写建议列表 JSON |
| `--force` | 否 | 覆盖 |
| `--quiet` | 否 | 不打印人类摘要 |

- 没有任何建议时：退出 5，不写 `.ics`，错误码 `no_suggestions`，提示降低 `--min-focus`、换一周或减少会议。
- 有建议时：写 ICS；若给 `--json`，写 `{schema_version, week:{iso,start,end,timezone}, suggestions:[...]}`。
- `--out` 与 `--json` 不能同时为 `-`；退出 2。
- 人类摘要列出每个建议的星期、起止和分钟数，最后一行 `已写入：<path>`。
- 写 stdout 时不打印人类摘要。

### 4.3 `weekglass demo [--out DIR] [--force] [--quiet] [--now ISO]`

在目录中生成可复现的示例：

- 固定周 `2026-W44`（周一开始 2026-10-26），固定时区 `Asia/Shanghai`。
- 写入 `work.ics`、`personal.ics`、`focus.ics`、`report.json`、`report.html`。
- `--out` 默认 `./weekglass-demo`。
- 目录不存在时创建；存在且非空且没有 `--force` 时退出 6；存在但不是目录时退出 6。
- `--now` 只影响生成的 `generated_at` 和 `DTSTAMP`；不给时用当前时间。
- 输出人类提示：示例目录、报告路径、专注计划路径；`--quiet` 时不打印。

### 4.4 `weekglass version [--json]`

- 默认：`weekglass 0.1.0`。
- `--json`：`{"name":"weekglass","version":"0.1.0","schema_version":1}`。
- 退出 0。

### 4.5 `weekglass --version`

输出 `weekglass 0.1.0`，退出 0。

## 5. 数据模型

### 5.1 JSON 顶层

```json
{
  "schema_version": 1,
  "tool": {"name": "weekglass", "version": "0.1.0"},
  "generated_at": "2026-10-29T18:00:00+08:00",
  "week": {
    "iso": "2026-W44",
    "start": "2026-10-26",
    "end": "2026-11-01",
    "analyzed_days": 5,
    "timezone": "Asia/Shanghai"
  },
  "settings": {},
  "sources": [],
  "metrics": {},
  "days": [],
  "events": [],
  "suggestions": [],
  "warnings": [],
  "plan_path": null
}
```

字段：

| 字段 | 类型 | 取值/说明 |
|---|---|---|
| `schema_version` | integer | 固定 `1` |
| `tool.name` | string | 固定 `weekglass` |
| `tool.version` | string | `0.1.0` |
| `generated_at` | string | 带偏移的 ISO 8601，取 `now` |
| `week.iso` | string | `YYYY-Www`，ISO 周 |
| `week.start` | string | 周一 `YYYY-MM-DD` |
| `week.end` | string | 周日 `YYYY-MM-DD` |
| `week.analyzed_days` | integer | 5 或 7 |
| `week.timezone` | string | IANA 名称 |
| `settings` | object | 见 5.2 |
| `sources` | array | 见 5.3 |
| `metrics` | object | 见 5.4 |
| `days` | array | 见 5.5，长度等于 `analyzed_days`，按日期升序 |
| `events` | array | 见 5.6，按开始时间、结束时间、标题、UID 升序；最多 `WEEKGLASS_MAX_REPORT_EVENTS` 条 |
| `suggestions` | array | 见 5.7，按 `rank` 升序 |
| `warnings` | array | 见 5.8，按产生顺序；最多 200 条 |
| `plan_path` | string\|null | 实际写入的专注块路径；stdout 时为 `标准输出`；没有写时为 `null` |

### 5.2 `settings`

```json
{"timezone":"Asia/Shanghai","work_start":"09:00","work_end":"18:00","lunch_start":"12:00","lunch_end":"13:00","min_focus_minutes":90,"max_suggestions":3,"max_per_day":1,"buffer_minutes":0,"include_weekend":false,"all_day_busy":false}
```

`lunch_start`/`lunch_end` 为 `off` 或 `HH:MM`。其余类型：整数或布尔。值为本次实际生效值。

### 5.3 `sources[]`

```json
{"path":"work.ics","name":"work.ics","bytes":3623,"events_total":18,"events_in_week":12,"warnings":[]}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `path` | string | 传给命令的路径（展开 `~` 后），不解析为绝对路径 |
| `name` | string | 文件名 |
| `bytes` | integer | 文件字节数 |
| `events_total` | integer | 文件内 VEVENT 总数（不展开） |
| `events_in_week` | integer | 展开后落在本周窗口内且未取消的事件数（去重前） |
| `warnings` | array | 该文件的 warning，格式同 5.8 |

### 5.4 `metrics`

| 字段 | 类型 | 说明 |
|---|---|---|
| `available_minutes` | integer | 所有分析日的可用分钟数之和 |
| `busy_minutes` | integer | 合并后的占用分钟数 |
| `free_minutes` | integer | `available_minutes - busy_minutes` |
| `focus_minutes` | integer | 完整空闲块分钟数之和 |
| `fragmented_minutes` | integer | 短于 `min_focus_minutes` 的空闲分钟数之和 |
| `focus_blocks` | integer | 完整空闲块数 |
| `fragments` | integer | 碎片空闲段数 |
| `longest_focus_minutes` | integer | 最长完整空闲块；没有时为 0 |
| `busy_blocks` | integer | 合并后占用区间数之和 |
| `back_to_back_pairs` | integer | 背靠背事件对数 |
| `event_count` | integer | 去重后未取消事件数（不受报告截断影响） |
| `all_day_events` | integer | 去重后未取消的全天事件数 |
| `after_hours_minutes` | integer | 分析日内、工作时间外的定时占用分钟数；不含全天事件 |
| `weekend_minutes` | integer | 周六、周日的定时占用分钟数；不含全天事件；即使不分析周末也计算 |
| `duplicate_events` | integer | 跨日历合并掉的事件数 |
| `cancelled_events` | integer | 状态为 CANCELLED 的事件数（展开后） |
| `transparent_events` | integer | `TRANSP:TRANSPARENT` 的事件数（未被取消） |
| `busy_pct` | number | `busy_minutes / available_minutes × 100`，四舍五入 1 位；分母 0 时为 0.0 |
| `fragmentation_pct` | number | `fragmented_minutes / free_minutes × 100`，四舍五入 1 位；分母 0 时为 0.0 |
| `focus_pct` | number | `focus_minutes / available_minutes × 100`，四舍五入 1 位；分母 0 时为 0.0 |

### 5.5 `days[]`

```json
{"date":"2026-10-26","weekday":"周一","available_minutes":480,"busy_minutes":135,"free_minutes":345,"focus_minutes":180,"fragmented_minutes":165,"focus_blocks":1,"fragments":4,"longest_focus_minutes":180,"busy_blocks":3,"after_hours_minutes":60,"all_day_events":0,"busy_pct":28.1}
```

`weekday` 只取 `周一`…`周日`。`date` 为 `YYYY-MM-DD`。数值字段均为整数，`busy_pct` 为 1 位小数。每天 `focus_minutes + fragmented_minutes = free_minutes`。

### 5.6 `events[]`

```json
{
  "uid":"standup@weekglass.demo",
  "recurrence_id":null,
  "sources":["work.ics"],
  "summary":"每日站会",
  "start":"2026-10-26T09:30:00+08:00",
  "end":"2026-10-26T09:45:00+08:00",
  "minutes":15,
  "all_day":false,
  "busy":true,
  "status":"confirmed",
  "transparency":"opaque",
  "location":"会议室 A",
  "categories":[],
  "attendee_count":0,
  "is_focus":false
}
```

| 字段 | 类型 | 取值/说明 |
|---|---|---|
| `uid` | string | ICS UID；缺失时用 `no-uid-<sha1前16位>` |
| `recurrence_id` | string\|null | `RECURRENCE-ID` 的 ISO 值；无则 `null` |
| `sources` | array[string] | 出现该事件的日历文件名，去重、保持首次出现顺序 |
| `summary` | string | 标题；缺失为 `（无标题）` |
| `start` / `end` | string | 带偏移 ISO 8601；全天事件为当天 00:00 到结束日 00:00 |
| `minutes` | integer | `floor((end-start)/60s)`，最小 0；全天事件为 1440×天数 |
| `all_day` | boolean | `DTSTART` 是 DATE 而非 DATE-TIME |
| `busy` | boolean | 见 6.1 |
| `status` | enum | `confirmed` / `tentative`（取消事件计数但不进入 `events`） |
| `transparency` | enum | `opaque` / `transparent` |
| `location` | string | 原样；缺失为空字符串 |
| `categories` | array[string] | 展开后的分类，去重 |
| `attendee_count` | integer | ATTENDEE 数量 |
| `is_focus` | boolean | 标题或分类（不区分大小写）含 `focus` 或 `专注` |

`events` 最多 `WEEKGLASS_MAX_REPORT_EVENTS` 条；超出时指标仍用全部事件，并在 `warnings` 加 `report_truncated`。

### 5.7 `suggestions[]`

```json
{"rank":1,"date":"2026-10-26","weekday":"周一","start":"2026-10-26T15:00:00+08:00","end":"2026-10-26T18:00:00+08:00","minutes":180,"reason":"周一下午连续空闲 180 分钟，当前没有占用。"}
```

`rank` 从 1 连续编号；`minutes` 为整数；`start`/`end` 为本地时区带偏移。没有建议时数组为空。

### 5.8 `warnings[]`

```json
{"code":"floating_time","message":"事件没有时区，已按配置时区解释；请在日历设置中开启时区，避免跨时区错误。","source":"work.ics"}
```

已实现的 `code`：

| code | 触发条件 |
|---|---|
| `floating_time` | 事件 DTSTART/DTEND/RECURRENCE-ID 无时区 |
| `missing_dtstart` | 展开后的事件缺少 DTSTART，跳过 |
| `end_before_start` | 结束早于开始，按零时长处理 |
| `report_truncated` | 事件数超过 `WEEKGLASS_MAX_REPORT_EVENTS`，报告只列前 N 条 |

相同 `(code, message, source)` 只保留一条；最多 200 条。

## 6. 计算规则

### 6.1 事件是否占用

- `STATUS:CANCELLED`：不进入 `events`，计入 `cancelled_events`，不占用。
- `TRANSP:TRANSPARENT`：进入 `events` 且 `busy=false`，不占用，计入 `transparent_events`。
- `STATUS:TENTATIVE`：按占用处理。
- 全天事件：`busy=false`；`--all-day-busy` 时为 `true`，占用整个分析日。
- 其余定时事件：`busy=true`。
- 事件按开始/结束半开区间 `[start, end)` 处理。

### 6.2 展开、时区与去重

- 用 `recurring-ical-events` 展开 RRULE、RDATE、EXDATE、RECURRENCE-ID；展开窗口为本周一 00:00 前 2 天到本周日 24:00 后 2 天，再按实际重叠过滤。
- 单个文件的 RRULE 无法展开时跳过该规则（库的 `skip_bad_series=True`），不使整次命令失败；文件完全没有可解析事件时仍生成空周报告。
- 事件时间：有 `TZID` 的按该时区；`Z` 按 UTC；无时区的按 `WEEKGLASS_TZ` 并产生 `floating_time`；统一转换为 `WEEKGLASS_TZ` 后计算。
- 去重键：`(uid, recurrence_id or "", start ISO, end ISO, summary)`。相同键的跨文件事件合并 `sources`，`duplicate_events` 加 1。
- 排序：开始时间、结束时间、标题（`casefold`）、UID。

### 6.3 每天指标

- 工作窗口：`work_start` 到 `work_end`。午休不为 `off` 时，从可用时间中减去 `[lunch_start, lunch_end)`。
- 占用区间：所有 `busy=true` 事件与当天可用区间的交集；`buffer_minutes > 0` 时，定时事件先向前后各扩 N 分钟，再与可用区间求交。全天事件不加 buffer。
- 合并规则：两个区间重叠或首尾相接（间隔 ≤ 0 分钟）合并。
- `available_minutes`：可用区间分钟数之和。
- `busy_minutes`：合并后占用区间与可用区间交集的分钟数之和。
- `free_minutes = available_minutes - busy_minutes`（不小于 0）。
- 空闲区间：可用区间减去占用区间。长度 `≥ min_focus_minutes` 为完整专注块；长度 `> 0` 且 `< min_focus_minutes` 为碎片。长度 0 不计。
- `longest_focus_minutes`：完整专注块的最大长度；没有为 0。
- `busy_blocks`：合并后占用区间数。
- `after_hours_minutes`：当天定时 `busy=true` 事件与 `[00:00, work_start)` 和 `[work_end, 24:00)` 的交集，合并后求和；不含全天事件。
- `all_day_events`：覆盖当天的全天事件数。
- 分钟数一律向下取整。

### 6.4 整周指标

- 对 `days` 求和；`longest_focus_minutes` 取各天最大值。
- `back_to_back_pairs`：对每个分析日，取当天开始、`busy=true`、非全天的事件，按开始排序；相邻两个事件间隔 `0–5` 分钟（含 0 和 5）计 1 对；重叠（负间隔）不计。
- `weekend_minutes`：周六、周日所有定时 `busy=true` 事件的并集分钟数，不含全天事件；即使 `include_weekend=false` 也计算。
- `cancelled_events`、`transparent_events` 在去重前按展开后事件计数；`duplicate_events` 按合并次数计数。
- 百分比四舍五入到 1 位小数；分母为 0 时为 0.0。

### 6.5 专注建议

- 候选来源：每个分析日的空闲区间。
- 对齐：开始向上取到 15 分钟网格，结束向下取到 15 分钟网格；对齐后长度 `< min_focus_minutes` 的候选丢弃。
- 单块长度：`min(对齐后长度, max(180, min_focus_minutes))`。
- 评分：`min(单块分钟数, 180)`；开始时间早于 12:00 加 20；周二、周三、周四加 10。
- 选择：按评分降序、日期升序、开始时间升序；同一天最多 `max_per_day` 个；总数最多 `max_suggestions`；`max_suggestions=0` 时为空。
- 输出按选择顺序编号 `rank`，不按时间重排。
- `reason` 固定格式：`<星期><上午|下午>连续空闲 <分钟> 分钟，当前没有占用。`
- 建议只基于空闲区间，不会与已有占用重叠；已有“专注”事件仍按占用处理，因此不会在其上重复建议。

## 7. 报告

### 7.1 HTML

- 单文件，UTF-8，内联 CSS，无 JavaScript、无外部字体、无图片、无网络请求。
- `Content-Security-Policy` 为 `default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'`。
- 结构：品牌行、本周数字、结论句、一周时间带、按天表格、专注建议、算法说明、数据来源、可折叠事件明细、页脚。
- 所有用户可控文本（标题、地点、文件名、警告）经 HTML 转义；任何 `<script>` 都不得成为可执行标签。
- 视觉规则见 [DESIGN.md](DESIGN.md)：只用 token 颜色/字号，浅色/深色跟随 `prefers-color-scheme`，375px 单列，不使用渐变、卡片堆叠、emoji、彩色图标块。
- 报告中只显示来源文件名，不显示完整路径；JSON 保留 `path` 字段。
- 页脚写明版本、生成时间和“报告不发起网络请求；分享前检查事件标题”。

### 7.2 终端摘要

固定顺序：

```
Weekglass 0.1.0 · 2026-W44 · Asia/Shanghai
10 月 26 日–10 月 30 日 · 5 个工作日

占用        16 小时 15 分 / 40 小时（41%）
完整专注    10 小时 30 分（5 块）
碎片空闲    13 小时 15 分（占空闲 56%）
最长空闲    3 小时

周一   2 小时 15 分 占用 · 1 块专注 · 最长 3 小时
...
建议：
  1. 周一 15:00–18:00（3 小时）

报告：/path/report.html
JSON：/path/report.json
专注计划：/path/focus.ics
```

没有建议时用 `这一周没有 ≥ 90 分钟的连续空闲。`；有 warning 时最多显示 5 条，再显示 `另有 N 条提示，见报告。`

## 8. 风险与防护

| 风险 | 防护 | 测试 |
|---|---|---|
| 覆盖用户已有报告/计划 | 默认拒绝已存在输出，`--force` 才覆盖；同路径重复检测；先检查后读取 | `test_cli.py::test_refuses_overwrite`、`test_duplicate_outputs` |
| 写到一半留下损坏文件 | 同目录临时文件 + `os.replace` 原子替换；失败清理临时文件 | `test_outputs.py::test_atomic_replace` |
| 修改/删除输入日历 | 代码只以 `read_bytes()` 读取输入，不打开写模式 | `test_cli.py::test_input_never_modified` |
| 报告泄露隐私 | 不联网；HTML/终端只显示文件名；README 提醒分享前检查；JSON 含路径需自行检查 | `test_report.py::test_html_escapes_and_hides_absolute_path` |
| 事件标题注入 HTML/脚本 | Jinja2 autoescape；CSP；无 JS | `test_report.py::test_xss_payload_is_escaped` |
| 时区错误 | 所有时间显式带时区；无时区产生 warning；HTML/终端显示时区；ICS 用 UTC | `test_ics.py::test_floating_time_warning`、`test_dst_wall_clock` |
| 重复事件无限展开 | 单文件 20 MB、展开事件 20,000、最多 20 个文件、只展开本周前后 2 天；坏 RRULE 跳过 | `test_ics.py::test_too_many_events`、`test_bad_rrule_is_skipped` |
| 全天事件误算 | 默认不计入占用；`--all-day-busy` 才计入；文档/报告写明 | `test_metrics.py::test_all_day_default_and_flag` |
| 输出路径写失败 | 捕获 `OSError`，退出 7，中文说明路径和系统错误 | `test_outputs.py::test_write_error` |
| 误用为自动排程 | 不提供写日历 API；只生成独立 `.ics`；README 说明导入前确认 | `test_cli.py::test_plan_is_separate_file` |
| 模型编造内容 | 不使用 LLM；所有数字由本地计算 | `test_no_network.py::test_socket_is_never_used` |
| 进程中断后状态不一致 | 无持久状态；每次运行从输入重算；输出原子替换 | `test_cli.py::test_rerun_is_deterministic` |

## 9. 外部服务与 mock

- 0.1.0 **不调用任何外部 HTTP/API、模型或第三方数据服务**，因此没有网络超时、429、5xx、鉴权或重试路径。
- 测试和演示的确定性来自：
  - 本地 fixture `.ics`；
  - `WEEKGLASS_NOW` / `--now` 注入时钟；
  - `demo` 固定周 `2026-W44`、固定时区 `Asia/Shanghai`。
- 测试把 `socket.socket`、`socket.create_connection` 替换为抛错，若代码发起网络请求则测试失败。
- 未来若增加外部服务，必须新增 `WEEKGLASS_<SERVICE>_MOCK` 开关和确定性假实现；0.1.0 不预留空开关。

## 10. 测试要求

全部测试在临时目录运行，不联网，不读取用户真实日历。`pytest` 一次运行必须覆盖以下条目；每个条目至少一个测试函数，失败路径必须有断言。

### 10.1 解析

- 定时事件、全天事件、UTC 事件、`TZID` 事件、浮动事件、`DURATION` 事件。
- 取消事件不进入 `events`、计入 `cancelled_events`；透明事件进入但 `busy=false`、计入 `transparent_events`；暂定事件占用。
- 缺少 `DTSTART` 跳过并产生 `missing_dtstart`；结束早于开始产生 `end_before_start` 且零时长。
- RRULE 的 `COUNT`、`UNTIL`、`BYDAY`、`EXDATE`、`RDATE`、`RECURRENCE-ID` 改期。
- 同一 UID/时间/标题跨两个文件合并，`sources` 含两个文件名，`duplicate_events=1`。
- 无效 ICS、文件不存在、目录、不可读、超过大小、超过事件数、坏 RRULE。
- 无时区事件产生 `floating_time`；未知 TZID 不崩溃。
- 周窗口边界：周日 23:30 跨到周一、周五 23:00 跨到周六、跨时区事件。

### 10.2 指标

- 空周、全天空闲、全天占用、午休被会议占用、午休关闭、`buffer=0/10/60`。
- 相邻事件合并、重叠事件合并、首尾相接、间隔 1 分钟、间隔 5 分钟、间隔 6 分钟。
- 完整专注 89/90/91 分钟；碎片段计数；最长专注；碎片率分母为 0。
- 背靠背 0/5/6 分钟；重叠不算背靠背。
- 工时外事件、周末事件、`include_weekend` 开/关、`all_day_busy` 开/关。
- 重复/取消/透明计数；`focus_minutes + fragmented_minutes = free_minutes`。
- 百分比四舍五入 1 位。

### 10.3 建议

- 89 分钟不产生、90 分钟产生。
- 15 分钟对齐：09:07 开始 → 09:15；10:59 结束 → 10:45。
- 单块超过 180 分钟截到 180；`min_focus>180` 时用 `min_focus`。
- `max_suggestions=0`、`max_per_day=1/2`、候选不足、全部被过滤。
- 评分顺序、同分按日期/时间、rank 连续。
- 建议不与占用重叠、不跨午休。
- `plan` 无建议退出 5；`audit --plan-out` 无建议退出 0 且不写文件。

### 10.4 CLI 与输出

- `--help`、`version`、`version --json`、`--version`。
- 人类摘要字段、无建议提示、`--quiet`、颜色在非 TTY 关闭。
- JSON schema 顶层键、字段类型、排序、`plan_path`。
- HTML 包含关键数字、无 `<script>` 注入、无外部 URL、无绝对路径。
- 已存在输出退出 6；`--force` 覆盖；重复路径退出 2；两个 stdout 退出 2。
- 输出父目录自动创建；写失败退出 7；stdout 输出不混入摘要。
- 环境变量非法退出 8；CLI 非法退出 2；输入缺失退出 3；日历非法退出 4；无建议退出 5；内部错误退出 1。
- `demo` 生成 5 个文件、重复运行无 `--force` 退出 6、`--now` 固定 `generated_at`。
- 同一输入 + 同一 `--now` 连续两次输出字节一致（HTML/JSON/ICS）。
- 原子替换后文件完整；两个线程/进程写同一路径，最终文件可解析。
- 输入文件在运行前后哈希不变。
- 禁止网络：socket 替换为抛错后所有命令仍成功。

## 11. 版本与发布

- 版本号 `0.1.0`，`pyproject.toml`、`src/weekglass/__init__.py`、`CHANGELOG.md` 一致。
- 本地标签 `v0.1.0`；不创建远程、不 push、不发 Release。
- CI 在 push/PR 跑测试；推 `vX.Y.Z` 标签时校验标签与 `pyproject.toml` 版本一致，再跑测试、构建 sdist/wheel、创建 GitHub Release。
- 发布材料只写不发的放 `launch/`，不执行发布。
