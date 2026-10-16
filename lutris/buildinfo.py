"""Source revision for checkouts and packaged builds; also usable as a build script."""

import os
import re
import subprocess
from pathlib import Path


def get_commit() -> str:
    root = Path(__file__).resolve().parent.parent
    candidates = []
    # Only inspect this checkout, never an unrelated parent repository.
    if (root / ".git").exists():
        try:
            candidates.append(
                subprocess.check_output(
                    ["git", "-C", str(root), "rev-parse", "HEAD"],
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=2,
                ).strip()
            )
        except (OSError, subprocess.SubprocessError):
            pass
    candidates.append(os.environ.get("LUTRIS_BUILD_COMMIT", ""))
    try:
        candidates.append(Path(__file__).with_name("build_commit.txt").read_text(encoding="ascii").strip())
    except (OSError, UnicodeError):
        pass
    return next((value[:7].lower() for value in candidates if re.fullmatch(r"[0-9a-fA-F]{7,64}", value)), "")


def get_display_version(version: str) -> str:
    commit = get_commit()
    return f"{version}-{commit}" if commit else version


if __name__ == "__main__":
    print(get_commit())
