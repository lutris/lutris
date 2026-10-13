#!/usr/bin/env python3
"""Resolve the source revision at build time without importing Lutris or GTK."""

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def get_commit() -> str:
    candidate = os.environ.get("LUTRIS_BUILD_COMMIT", "")
    if re.fullmatch(r"[0-9a-fA-F]{7,64}", candidate):
        return candidate.lower()
    try:
        top = subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "--show-toplevel"], stderr=subprocess.DEVNULL, text=True
        ).strip()
        if Path(top).resolve() == ROOT:
            candidate = subprocess.check_output(
                ["git", "-C", str(ROOT), "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True
            ).strip()
            if re.fullmatch(r"[0-9a-fA-F]{40,64}", candidate):
                return candidate.lower()
    except (OSError, subprocess.CalledProcessError):
        pass
    try:
        candidate = (ROOT / "lutris" / "build_commit.txt").read_text(encoding="ascii").strip()
    except (OSError, UnicodeError):
        return ""
    return candidate.lower() if re.fullmatch(r"[0-9a-fA-F]{7,64}", candidate) else ""


if __name__ == "__main__":
    print(get_commit())
