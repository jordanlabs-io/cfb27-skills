#!/usr/bin/env python3
"""Preflight interpreter/tool check for film-room scripts.

Run BEFORE any script that imports numpy/PIL/pytesseract (frames.py,
snap_times.py, segment.py, etc). Exits non-zero with the fix if this
interpreter is missing a required import or a required system binary
is not on PATH.

Usage:
    ~/CFB27-film/.venv/bin/python3 "$SK/film-room/scripts/preflight_env.py"

If you ran this with plain `python3` and it failed, that IS the bug —
this repo's scripts require the venv at ~/CFB27-film/.venv (see
SKILL.md "Environment"), not system python3.
"""
import shutil
import subprocess
import sys

FIX = (
    "Run every film-room script with ~/CFB27-film/.venv/bin/python3, not "
    "system python3. If the venv itself is missing the package, recreate it: "
    "~/CFB27-film/.venv/bin/pip install numpy pillow pytesseract"
)


def main() -> int:
    problems = []

    for mod in ("numpy", "PIL", "pytesseract"):
        try:
            __import__(mod)
        except ImportError as e:
            problems.append(f"missing python import: {mod} ({e})")

    for binary in ("tesseract", "ffmpeg"):
        if shutil.which(binary) is None:
            problems.append(f"missing system binary on PATH: {binary}")

    if problems:
        sys.stderr.write("preflight_env: FAIL\n")
        for p in problems:
            sys.stderr.write(f"  - {p}\n")
        sys.stderr.write(f"\nFix: {FIX}\n")
        return 1

    print(f"preflight_env: OK ({sys.executable})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
