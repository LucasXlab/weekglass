# 偏离记录

编号规则：`D-01` 起。每条写“原计划/契约 → 实际做法 → 原因 → 影响”。没有记录的偏离视为缺陷。

| 编号 | 原计划/契约 | 实际做法 | 原因 | 影响 |
|---|---|---|---|---|
| D-01 | 在 `/Users/you/NO` 根目录建项目 | 项目在 `weekglass/` 子目录，独立 git 仓库 | 根目录有多个历史候选目录，避免污染 | 安装/README 均以 `weekglass/` 为根 |
| D-02 | 用户环境 Python 3.11+ | 本地 3.13.5；CI 覆盖 3.11–3.13 | 机器默认 3.13；用最低版本声明兼容 | 3.11 未在本机手工跑，依赖 CI |
| D-03 | 用 `uv` 建环境 | `python3 -m venv` + `pip` | `uv` 家目录缓存不可写，报 `Operation not permitted` | 开发命令以 venv 为准；不依赖 uv |
| D-04 | 先完成 SPEC/DESIGN 再写代码 | 先搭了可运行骨架，再补 SPEC/DESIGN | 需要尽早验证解析/指标可行性 | SPEC 现在是唯一契约；代码按 SPEC 回填，未留未记录行为 |
| D-05 | 任务允许 CLI 或 HTTP | 只做 CLI + 静态 HTML，不做 HTTP | 本地优先、无服务端；核心流程更短 | 没有端口、鉴权、CORS、并发请求问题 |
| D-06 | 任务允许使用 LLM（需 mock） | 不使用 LLM | 指标是确定性计算；避免编造和密钥 | 无模型成本、无 mock 开关 |
| D-07 | 环境变量包含 `WEEKGLASS_LOG_LEVEL` | 删除该变量，只保留 `--debug` | 原先没有日志实现，保留会是空开关 | 少一个无效配置；错误仍走 stderr |
| D-08 | `--include-weekend`/`--all-day-busy` 可开可关 | CLI 只有开启开关；关闭靠环境变量默认 0 | argparse 只加一个 flag，避免成对参数 | 环境变量设为 1 时 CLI 不能关；记在这里 |
| D-09 | `audit --plan-out` 没有建议时不写文件 | 仍先检查 `--plan-out` 是否存在；存在且无 `--force` 会先退出 6 | 所有输出在读取前统一 preflight | 没有建议但旧计划文件存在时，需要 `--force` 或换路径 |
| D-10 | `plan` 没有建议时退出 5 | 先 preflight 输出；输出已存在时可能先退出 6 | 避免分析后才发现不能写 | 错误码优先级为“输出存在 > 无建议” |
| D-11 | HTML 显示计划路径 | HTML 只显示 basename；JSON `plan_path` 保留传入路径 | 报告可能被分享，减少绝对路径泄露 | 两处路径表示不同，SPEC 已写明 |
| D-12 | 输出文件权限未规定 | POSIX 上为 0600 | 临时文件默认 0600，经 `os.replace` 保留；日历数据敏感 | 同机其他用户不可读；Windows 不保证 |
| D-13 | 每个展开事件都有 `RECURRENCE-ID` | 只暴露源文件中真实存在的 RECURRENCE-ID | `recurring-ical-events` 给所有 occurrence 加了该属性 | 普通事件 JSON 的 `recurrence_id` 为 `null` |
| D-14 | 结束早于开始按零时长 | 库会把 DTSTART/DTEND 交换；解析器用源文件原始 DTSTART 恢复并置零 | 不绕过库的展开逻辑 | 事件时间取原始开始；有 `end_before_start` 提示 |
| D-15 | 系统时区取 IANA | 依次尝试 `TZ`、`/etc/localtime`、`datetime.now().astimezone()`，最后 `UTC` | macOS/Linux 容器差异 | 极端环境可能是 `UTC`；报告顶部总显示实际时区 |
| D-16 | 全天事件默认占用 | 默认不占用；`--all-day-busy`/环境变量才占用 | 假期/生日不应算忙碌 | 用户需显式开启；报告写明 |
| D-17 | 背靠背统计 | 只统计同一天开始、非全天、间隔 0–5 分钟的事件；重叠不计 | 跨天和不透明事件语义不清 | 跨夜事件不计入背靠背 |
| D-18 | 周末统计仅在包含周末时计算 | `weekend_minutes` 总是计算，即使不分析周末 | 用户想知道周末被占多少，但不希望周末进分母 | JSON 有该字段；不影响主指标 |
| D-19 | 报告事件不设上限 | 超过 `WEEKGLASS_MAX_REPORT_EVENTS` 截断 `events`，指标用全量 | 防止 HTML 过大/浏览器卡顿 | 有 `report_truncated` 提示；`event_count` 仍是全量 |
| D-20 | `demo` 使用当前时区/周 | 固定 `Asia/Shanghai`、`2026-W44` | 截图和文档可复现 | 示例与用户本地周无关 |
| D-21 | JSON `sources.path` 用绝对路径 | 保留传入路径（展开 `~` 后），HTML 只用文件名 | 便于脚本定位；报告减少泄露 | 两处语义不同，SPEC 已写明 |
| D-22 | 生成 `.ics` 带 VTIMEZONE | 用 UTC DTSTART/DTEND，不写 VTIMEZONE | 更少组件、跨客户端更稳 | 极旧客户端可能不识别本地时区显示 |
| D-23 | 许可证待定 | MIT | 本地 CLI 工具，最大化采用；无网络服务，MIT 足够 | 见 `notes/决定.md` |
| D-24 | 对闭源竞品读“最近 50 个 issue” | Reclaim/Clockwise/Morningstar/Passiv 无公开 issue；改读官方定价/停服公告和 HN 公开反馈 | 闭源产品没有 issue 列表 | `docs/选题.md` 已注明；开源竞品用 GitHub issue |
| D-25 | 所有候选都有 5 条“痛点” | 部分候选的第 5 条是相邻需求/产品发布，不完全是痛点 | 公开证据有限，不伪造 | 已在该候选结论里标注淘汰原因 |
| D-26 | DESIGN 要求所有尺寸 token 化 | `line-height`、轨道高度、表格列宽仍有 px/数字 | 它们属于布局/排版细节，不是颜色/字号/间距 token 的核心 | 颜色、字号、间距、圆角、动效已 token 化；测试覆盖颜色/字号 |
| D-27 | `audit`/`plan` 的 `--json` 都输出完整报告 | `plan --json` 只输出周信息 + 建议列表 | 只生成计划时不需要重复整周指标 | SPEC §4.2 已定义独立 schema |
| D-28 | 输出父目录不存在时由用户创建 | 自动创建父目录 | 减少一次失败 | 权限不足时退出 7 |
| D-29 | 错误信息带链接/文档 | 只带中文说明和下一步提示，不带 URL | 离线可用，避免死链 | 文档在 README/docs 索引 |
| D-30 | 发布到 PyPI | 不发布；只本地安装/打标签 | 用户要求不发布 | README 写明本地安装 |

## 未记录的“看起来像偏离”的事项

- 周末默认不分析：SPEC 第 2、3 节明确，不是偏离。
- 午休默认 12:00–13:00：SPEC 配置表明确。
- 建议默认 3 个、每天 1 个：SPEC §6.5 明确。
- HTML 无 JS：DESIGN §1、§9 明确。
- 报告 0600：D-12 记录。
