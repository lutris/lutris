"""Build provenance, available without Git at runtime."""

import re
import subprocess
from pathlib import Path


def get_checkout_commit() -> str:
    """Read Git only for a source checkout, never an unrelated parent repository."""
    root = Path(__file__).resolve().parent.parent
    if not (root / ".git").exists():
        return ""
    try:
        top = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        ).strip()
        if Path(top).resolve() != root:
            return ""
        commit = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return ""
    return commit.lower() if re.fullmatch(r"[0-9a-fA-F]{40,64}", commit) else ""


def get_display_version(version: str) -> str:
    """Append the short packaged source revision when one is available."""
    commit = get_checkout_commit()
    if commit:
        return f"{version}-{commit[:7]}"
    try:
        commit = Path(__file__).with_name("build_commit.txt").read_text(encoding="ascii").strip()
    except (OSError, UnicodeError):
        return version
    if not re.fullmatch(r"[0-9a-fA-F]{7,64}", commit):
        return version
    return f"{version}-{commit[:7].lower()}"
