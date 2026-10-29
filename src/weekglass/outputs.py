"""Atomic file output and stdout handling."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from .errors import OutputExistsError, OutputWriteError, UsageError


def is_stdout(path: str) -> bool:
    return path == "-"


def preflight(paths: list[str], force: bool) -> None:
    stdout_count = sum(1 for path in paths if is_stdout(path))
    if stdout_count > 1:
        raise UsageError("同一时间只能有一个输出写到标准输出（-）。", code="two_stdout_outputs")
    seen: dict[str, str] = {}
    for raw in paths:
        if is_stdout(raw):
            continue
        path = Path(raw).expanduser()
        key = str(path.resolve())
        if key in seen:
            raise UsageError(f"输出路径重复：{seen[key]} 和 {raw} 指向同一个文件。", code="duplicate_output")
        seen[key] = raw
        if path.exists() and not force:
            raise OutputExistsError(f"{path} 已存在；加 --force 覆盖。", code="output_exists")


def write_text(raw_path: str, text: str, *, force: bool = False) -> None:
    if is_stdout(raw_path):
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
        return
    path = Path(raw_path).expanduser()
    if path.exists() and not force:
        raise OutputExistsError(f"{path} 已存在；加 --force 覆盖。", code="output_exists")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OutputWriteError(f"无法创建目录 {path.parent}：{exc.strerror or exc}。", code="write_failed") from None
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except OSError as exc:
        if temp_name:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
        raise OutputWriteError(f"无法写入 {path}：{exc.strerror or exc}。", code="write_failed") from None
