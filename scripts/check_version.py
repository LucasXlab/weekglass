"""Check that a vX.Y.Z git tag matches pyproject and __init__."""

from __future__ import annotations

import os
import pathlib
import re
import sys
import tomllib


def main() -> int:
    tag = os.environ.get("TAG") or (sys.argv[1] if len(sys.argv) > 1 else "")
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        print(f"tag {tag!r} is not vX.Y.Z", file=sys.stderr)
        return 1
    project = tomllib.loads(pathlib.Path("pyproject.toml").read_text(encoding="utf-8"))
    version = project["project"]["version"]
    init = pathlib.Path("src/weekglass/__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', init)
    if not match:
        print("__version__ not found", file=sys.stderr)
        return 1
    if tag != f"v{version}":
        print(f"tag {tag} != v{version}", file=sys.stderr)
        return 1
    if match.group(1) != version:
        print(f"__init__ {match.group(1)} != {version}", file=sys.stderr)
        return 1
    print(f"version OK: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
