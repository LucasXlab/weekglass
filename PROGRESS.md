# 进度

最后更新：2026-10-29。中断后从这里恢复。

## 阶段状态

| 阶段 | 状态 | 产物 |
|---|---|---|
| 0 初始化 | 完成 | 独立仓库、`reference/inkdove`、`.gitignore`、`notes/参照.md` |
| 1 选题 | 完成 | `docs/选题.md`（8 候选、证据、竞品、评分、适用/不适用） |
| 2 规格/设计 | 完成，已过独立评审 | `SPEC.md`、`DESIGN.md`、`docs/external-apis.md` |
| 3 实现 | 完成 | `src/weekglass/*`、模板、137 个测试、示例 |
| 4 真实安装/复查 | 完成 | 10 次运行 + 5 类异常 + 3 个独立评审；见 `notes/真实运行.md`、`notes/评审记录.md` |
| 5 文档/发布材料 | 完成，待最终标签 | README/README_EN、features/development、LICENSE/CHANGELOG/CI/assets/launch 已就绪 |

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

- `pytest -q`：137 passed（2026-10-29，Python 3.13.5，Asia/Shanghai fixture；最终连续 3 次见交付）。
- `weekglass demo`：生成 5 个文件；占用 16h45/40h（42%）、完整专注 10h30（5 块）、碎片 12h45（55%）。报告 1280/375/320px 无水平滚动；`h1` 52/32/32px；无 JS/外链/图片。
- wheel：`weekglass-0.1.0-py3-none-any.whl` 包含 `weekglass/templates/report.html.j2`。

## 待办（按顺序）

1. 最终 3 次 `pytest -q` 全绿，记录最后输出。
2. 全新目录 clone + 按 README 安装，记录 `notes/安装实录.md`。
3. 本地 `git tag v0.1.0`（不 push、不发布）。
4. 最终总结：测试数、最后输出、已知问题、偏离数、发布前人工任务。
