from __future__ import annotations

import socket

from weekglass.cli import main

from .conftest import simple_ics, vevent


def test_no_network_is_used(tmp_path, capsys, monkeypatch):
    def fail(*_args, **_kwargs):
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket, "socket", fail)
    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.setattr(socket, "getaddrinfo", fail)

    work = simple_ics(tmp_path, "work.ics", vevent(uid="a", start="20261026T100000", end="20261026T110000"))
    code = main(["audit", str(work), "--week", "2026-10-26", "--json", "-", "--quiet"])
    assert code == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out.startswith("{")
