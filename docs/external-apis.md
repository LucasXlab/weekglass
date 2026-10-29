# 外部接口核对

核对日期：2026-10-29。核对方式：在本仓库的 `.venv`（Python 3.13.5）里读取已安装版本，运行对应测试；同时对照下列官方文档/源码。0.1.0 不发起任何网络请求，因此没有 API key、OAuth、配额、429、5xx 或重试路径。

## 1. 运行时网络接口

**没有。** Weekglass 只读取命令行传入的 `.ics` 文件，写本地文件。测试 `tests/test_no_network.py` 把 `socket.socket`、`socket.create_connection`、`socket.getaddrinfo` 替换为抛错函数，`audit` 仍成功。

因此：

- 不需要 `*_MOCK` 环境变量；SPEC 第 9 节记录了“未来新增外部服务才要求 mock”的规则。
- 没有 SSRF 面：代码不接受 URL，只接受本地路径。
- 没有密钥、token、cookie 或账号。
- 没有远程数据源；ETF/财务类候选未入选，因此也没有行情/基金 API。

## 2. 依赖与核对结果

| 依赖 | 版本 | 用途 | 官方文档/源码 | 本地核对 |
|---|---|---|---|---|
| `icalendar` | 7.3.0 | 解析/生成 RFC 5545 `.ics` | https://icalendar.readthedocs.io/ · https://github.com/collective/icalendar | `tests/test_ics.py`、`tests/test_planner.py` 通过 |
| `recurring-ical-events` | 3.8.2 | 展开 RRULE/RDATE/EXDATE/RECURRENCE-ID | https://github.com/niccokunzmann/python-recurring-ical-events | `tests/test_ics.py::test_rrule_exdate_and_override` 等通过 |
| `python-dateutil` | 2.9.0.post0 | 递归展开的传递依赖 | https://dateutil.readthedocs.io/ | 通过 `pip show recurring-ical-events` 确认依赖；本仓库不直接 import |
| `Jinja2` | 3.1.6 | 单文件 HTML 模板，开启 autoescape | https://jinja.palletsprojects.com/ | `tests/test_report.py`、`tests/test_design.py` 通过 |
| `tzdata` | 2026.6 | Windows/无系统 tzdata 时的 IANA 时区数据 | https://pypi.org/project/tzdata/ · https://www.iana.org/time-zones | `tests/test_config.py` 的 `Asia/Shanghai` 用例通过 |

版本核对命令（2026-10-29 执行）：

```
python -c "import importlib.metadata as m; print(m.version('icalendar'), m.version('recurring-ical-events'), m.version('Jinja2'), m.version('tzdata'))"
# 7.3.0 3.8.2 3.1.6 2026.6
```

## 3. 用到的协议/标准

| 标准 | 链接 | 本项目的使用边界 |
|---|---|---|
| RFC 5545（iCalendar） | https://www.rfc-editor.org/rfc/rfc5545 | 读取 VEVENT、RRULE、RDATE、EXDATE、RECURRENCE-ID、STATUS、TRANSP、DURATION；只写最小 VEVENT 集 |
| RFC 5545 §3.3.5（DURATION） | https://www.rfc-editor.org/rfc/rfc5545#section-3.3.5 | 无 DTEND 时用 DURATION 计算结束 |
| RFC 5545 §3.8.4.1（RECURRENCE-ID） | https://www.rfc-editor.org/rfc/rfc5545#section-3.8.4.1 | 只把源文件中真实存在的 RECURRENCE-ID 暴露到 JSON |
| IANA Time Zone Database | https://www.iana.org/time-zones | 所有 `TZID` 与 `ZoneInfo` 解析；未知 TZID 产生 `floating_time` 提示 |
| ISO 8601 | https://www.iso.org/iso-8601-date-and-time-format.html | JSON 时间、`--now`、周次 |

## 4. 明确未使用的接口

- Google Calendar API / Microsoft Graph：未使用，避免 OAuth 和云端授权。
- 任何 LLM/embedding API：未使用；报告数字全部由本地确定性代码计算。
- 行情/基金/券商 API：未使用；相关候选没有入选。
- 遥测、崩溃上报、CDN、外部字体：未使用；HTML 报告 CSP 为 `default-src 'none'`。

## 5. 已知限制（与接口无关，但影响数据正确性）

- `.ics` 导出本身可能丢失时区、重复规则或取消状态；Weekglass 只能按文件内容计算。
- 未知 `TZID` 在 `icalendar` 中退化为浮动时间，Weekglass 按 `WEEKGLASS_TZ` 解释并提示，不能还原厂商私有规则。
- 夏令时回拨的重复本地时间没有唯一标记；`.ics` 中相同 wall clock 的两个事件可能被合并。
- 生成 `.ics` 使用 UTC 时间戳，不写 VTIMEZONE；主流日历可导入，但极旧的客户端可能需要时区支持。
