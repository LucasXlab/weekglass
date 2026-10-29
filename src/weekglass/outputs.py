"""Atomic file output and stdout handling."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from .errors import OutputExistsError, OutputWriteError, UsageError


def is_stdout(path: str) -> bool:
    return path == "-"


def _same_path(first: Path, second: Path) -> bool:
    """True when two paths address the same file.

    samefile() covers hard links, symlinks and case-insensitive filesystems
    when both entries exist.  For two not-yet-created paths, parent + casefolded
    name catches the APFS/NTFS case variant before either file is written.
    """
    try:
        if first.exists() and second.exists() and os.path.samefile(first, second):
            return True
    except OSError:
        pass
    try:
        left = first.resolve()
        right = second.resolve()
    except OSError:
        left, right = first.absolute(), second.absolute()
    if left == right:
        return True
    if left.parent == right.parent and left.name.casefold() == right.name.casefold():
        return sys.platform in {"darwin", "win32"}
    return False


def reject_input_collisions(outputs: list[str], inputs: list[str]) -> None:
    """Refuse to write an output over an input calendar, even with --force."""
    input_paths = [Path(raw).expanduser() for raw in inputs]
    for raw in outputs:
        if is_stdout(raw):
            continue
        path = Path(raw).expanduser()
        for input_path in input_paths:
            if _same_path(path, input_path):
                raise UsageError(
                    f"输出路径 {raw} 与输入日历 {input_path} 是同一个文件；拒绝覆盖输入。",
                    code="output_is_input",
                )


def preflight(paths: list[str], force: bool) -> None:
    stdout_count = sum(1 for path in paths if is_stdout(path))
    if stdout_count > 1:
        raise UsageError("同一时间只能有一个输出写到标准输出（-）。", code="two_stdout_outputs")
    seen: list[tuple[Path, str]] = []
    for raw in paths:
        if is_stdout(raw):
            continue
        path = Path(raw).expanduser()
        for existing, existing_raw in seen:
            if _same_path(path, existing):
                raise UsageError(f"输出路径重复：{existing_raw} 和 {raw} 指向同一个文件。", code="duplicate_output")
        seen.append((path, raw))
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
