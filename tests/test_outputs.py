from __future__ import annotations

import os

import stat

import pytest

from weekglass.errors import OutputExistsError, OutputWriteError, UsageError
from weekglass.outputs import is_stdout, preflight, write_text


def test_stdout_helpers():
    assert is_stdout("-") is True
    assert is_stdout("x") is False


def test_preflight_rejects_two_stdout():
    with pytest.raises(UsageError) as exc:
        preflight(["-", "-"], False)
    assert exc.value.code == "two_stdout_outputs"


def test_preflight_rejects_duplicate_resolved_paths(tmp_path):
    path = tmp_path / "a.txt"
    with pytest.raises(UsageError) as exc:
        preflight([str(path), str(path)], False)
    assert exc.value.code == "duplicate_output"


def test_preflight_existing_and_force(tmp_path):
    path = tmp_path / "a.txt"
    path.write_text("old")
    with pytest.raises(OutputExistsError):
        preflight([str(path)], False)
    preflight([str(path)], True)


def test_write_text_creates_parent_and_file(tmp_path):
    path = tmp_path / "nested" / "deep" / "out.txt"
    write_text(str(path), "hello")
    assert path.read_text() == "hello"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_write_text_refuses_existing_without_force(tmp_path):
    path = tmp_path / "a.txt"
    path.write_text("old")
    with pytest.raises(OutputExistsError):
        write_text(str(path), "new")
    assert path.read_text() == "old"
    write_text(str(path), "new", force=True)
    assert path.read_text() == "new"


def test_write_text_stdout(capsys):
    write_text("-", "hello")
    captured = capsys.readouterr()
    assert captured.out == "hello\n"
    write_text("-", "with newline\n")
    captured = capsys.readouterr()
    assert captured.out == "with newline\n"


def test_write_text_replace_failure_leaves_no_temp_file(tmp_path, monkeypatch):
    import weekglass.outputs as outputs

    path = tmp_path / "a.txt"

    def fail(*_args, **_kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(outputs.os, "replace", fail)
    with pytest.raises(OutputWriteError) as exc:
        write_text(str(path), "data")
    assert exc.value.exit_code == 7
    assert not list(tmp_path.glob(".*.tmp"))
    assert not path.exists()


def test_write_text_directory_failure(tmp_path):
    directory = tmp_path / "dir"
    directory.mkdir()
    with pytest.raises(OutputWriteError):
        write_text(str(directory), "data", force=True)


def test_duplicate_outputs_via_hard_link_are_rejected(tmp_path):
    first = tmp_path / "first.json"
    first.write_text("{}")
    second = tmp_path / "second.json"
    os.link(first, second)
    with pytest.raises(UsageError) as exc:
        preflight([str(first), str(second)], force=True)
    assert exc.value.code == "duplicate_output"
