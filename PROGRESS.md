# 进度

最后更新：2026-10-29。中断后从这里恢复。

## 阶段状态

| 阶段 | 状态 | 产物 |
|---|---|---|
| 0 初始化 | 完成 | 独立仓库、`reference/inkdove`、`.gitignore`、`notes/参照.md` |
| 1 选题 | 完成 | `docs/选题.md`（8 候选、证据、竞品、评分、适用/不适用） |
| 2 规格/设计 | 完成，待独立评审 | `SPEC.md`、`DESIGN.md`、`docs/external-apis.md` |
| 3 实现 | 基本完成 | `src/weekglass/*`、模板、113 个测试、示例 |
| 4 真实安装/复查 | 未完成 | 待做干净环境安装、10 次真实运行、5 类异常、3 个独立评审 |
| 5 文档/发布材料 | 进行中 | 待写 README/README_EN、features/development 已写、LICENSE/CHANGELOG/CI/assets/launch |

## 当前可运行

```bash
cd /Users/you/NO/weekglass
. .venv/bin/activate
weekglass demo --out /tmp/wgdemo --force
weekglass audit /tmp/wgdemo/work.ics /tmp/wgdemo/personal.ics \
  --week 2026-10-26 --timezone Asia/Shanghai \
  --now 2026-10-29T18:00:00+08:00 \
  --html /tmp/wgdemo/report.html --json /tmp/wgdemo/report.json \
  --plan-out /tmp/wgdemo/focus.ics --force
```

## 最近验证

- `pytest -q`：113 passed（2026-10-29，Python 3.13.5，Asia/Shanghai fixture）。
- `weekglass demo`：生成 5 个文件；报告 1280px 浅色/深色、375px 浅色/深色均无水平滚动；`h1` 52px/32px；无 JS/外链/图片。
- wheel：`weekglass-0.1.0-py3-none-any.whl` 包含 `weekglass/templates/report.html.j2`。

## 待办（按顺序）

1. 写 `README.md`、`README_EN.md`、`LICENSE`、`CHANGELOG.md`、`.env.example`。
2. 生成并放入真实截图 `assets/report-light.png`、`assets/report-dark.png`、`assets/report-mobile.png`；写 `assets/logo.svg`。
3. 写 `.github/workflows/ci.yml`、`release.yml`；本地只验证 YAML，不 push。
4. 写 `launch/show-hn.md`、`launch/reddit.md`、`launch/v2ex.md`，只写不发。
5. 干净目录重新 clone/安装，记录 `notes/安装实录.md`；失败则修复并重来。
6. 10 次真实运行 + 5 类异常（断网/坏配置/超大输入/重复运行/中断）；修复不顺手处。
7. 3 个独立评审（正确性、安全/数据、新用户体验）；逐条复现、修复、加回归测试；记录误报。
8. 术语统一（UI/错误/日志/文档）；最终 `pytest` 连续 3 次；本地 `git tag v0.1.0`。
9. 最终总结：测试数、最后输出、已知问题、偏离数、发布前人工任务。
