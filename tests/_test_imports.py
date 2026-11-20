"""Every core module can be imported first.

Tests import modules in whatever order they happen to, which hides circular
imports that break a module imported on its own (as bin/lutris and scripts do).
"""

import subprocess
import sys
from pathlib import Path

LUTRIS_DIR = Path(__file__).resolve().parents[1] / "lutris"

# Imports each module named on the command line with no lutris module loaded,
# and prints those that fail
IMPORT_EACH = """
import importlib
import sys
import traceback

for name in sys.argv[1:]:
    for loaded in [m for m in sys.modules if m == "lutris" or m.startswith("lutris.")]:
        del sys.modules[loaded]
    try:
        importlib.import_module(name)
    except Exception:
        print("%s:\\n%s" % (name, traceback.format_exc(limit=-3)))
"""


def test_core_modules_import_on_their_own():
    names = sorted(f"lutris.{path.stem}" for path in LUTRIS_DIR.glob("*.py") if path.stem != "__init__")
    names += ["lutris.services", "lutris.installer", "lutris.runners"]
    result = subprocess.run(
        [sys.executable, "-c", IMPORT_EACH, *names],
        capture_output=True,
        text=True,
        check=True,
        cwd=LUTRIS_DIR.parent,
    )
    assert not result.stdout, result.stdout
