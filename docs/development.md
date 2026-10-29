# 开发与测试

## 环境

- Python 3.11+（CI 覆盖 3.11、3.12、3.13；本地为 3.13.5）。
- 依赖版本固定在 `pyproject.toml`，不跟随 `latest`。
- 安装：

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

`uv` 在部分机器上因家目录缓存不可写会失败；本项目不依赖 `uv`。

## 目录

```
src/weekglass/
  config.py     环境变量、CLI 覆盖、时区、周窗口
  ics.py        读取、展开重复、去重、过滤
  metrics.py    按天/整周指标、专注建议
  planner.py    生成可导入 .ics
  report.py     JSON/HTML 视图
  cli.py        argparse、退出码、终端摘要、demo
  outputs.py    原子写、stdout、存在性检查
  sample.py     固定示例日历
  templates/report.html.j2
tests/
  conftest.py   固定时钟、时区、ICS 构造器
  test_*.py     解析、指标、建议、报告、CLI、输出、设计
```

数据流：`cli.analyze` → `ics.load_events` → `metrics.compute_metrics` → `metrics.suggest_focus_blocks` → `planner.build_plan` / `report.render_*`。

## 测试

```bash
pytest              # 全量
pytest -q           # 简洁
pytest tests/test_ics.py -q
```

约束：

- 全部使用 `tmp_path`，不读取真实日历。
- 时钟由 `WEEKGLASS_NOW` 或 `--now` 固定；不使用 `sleep` 等时序。
- `tests/test_no_network.py` 把 socket 函数替换为抛错；任何网络访问都会失败。
- 不使用 `pytest.mark.skip`；没有条件跳过。
- `filterwarnings = ["error"]`：第三方库警告也会让测试失败，升级依赖时要先处理。

新增 fixture 的写法：

- 需要原始 ICS 边界行为：用 `tests/conftest.py` 的 `calendar()` / `vevent()` 手写。
- 需要直接测指标：用 `make_event()` 构造 aware `Event`，避免解析层干扰。
- 需要固定“现在”：`make_config()` 默认 `2026-10-29T18:00+08:00`，周为 `2026-W44`。

## 设计约束

- HTML 只用 token 颜色/字号；`tests/test_design.py` 会检查根 token 之外的十六进制颜色和硬编码字号。
- 报告无 JS、无外链、无图片；CSP 为 `default-src 'none'`。
- Jinja2 显式 `autoescape=True`；禁止 `|safe`。
- 375px 下不允许水平滚动；用 Chrome headless 的 `document.documentElement.scrollWidth` 核对。

## 打包

```bash
python -m pip wheel . --no-deps -w dist
python -m build            # 需要 build 包；CI 使用
```

- wheel 必须包含 `weekglass/templates/report.html.j2`；构建后可用 `unzip -l` 检查。
- `pyproject.toml` 的 `license` 与 `LICENSE` 一致（MIT）。
- 本地标签 `v0.1.0`；不 push、不发布。

## 已知工程限制

- 不处理 Google/Microsoft 的私有扩展；未知组件忽略。
- 未知 TZID 会退化为浮动时间，只能按配置时区解释。
- 夏令时回拨的重复 wall clock 没有唯一标记；同一 wall clock 的两个事件可能合并。
- 生成 `.ics` 用 UTC，不写 VTIMEZONE；主流客户端可导入。
- 输出文件在 POSIX 上为 0600（临时文件默认权限经 `os.replace` 保留），这是隐私默认值。
- 没有服务端、数据库、迁移或后台任务。
