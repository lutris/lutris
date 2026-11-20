"""`lutris` runs the commands that need no GUI without a GUI toolkit."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

LUTRIS = Path(__file__).resolve().parents[2] / "bin" / "lutris"

# Runs bin/lutris with GTK and GDK unimportable, as if no GUI toolkit were installed
RUN_WITHOUT_GTK = """
import runpy
import sys


class BlockGtk:
    def find_spec(self, name, path=None, target=None):
        if name in ("gi.repository.Gtk", "gi.repository.Gdk"):
            raise ImportError("No GUI toolkit here")
        return None


sys.meta_path.insert(0, BlockGtk())
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""


def run_lutris(tmp_path: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run `lutris` on a private session bus, with a fresh profile and no display."""
    env = {key: value for key, value in os.environ.items() if key not in ("DISPLAY", "WAYLAND_DISPLAY")}
    env |= {
        "HOME": str(tmp_path),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "LUTRIS_ALLOW_LOCAL_PYTHON_PACKAGES": "1",
    }
    return subprocess.run(
        ["dbus-run-session", "--", sys.executable, "-c", RUN_WITHOUT_GTK, str(LUTRIS), *arguments],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
    )


@pytest.mark.skipif(not shutil.which("dbus-run-session"), reason="Needs dbus-run-session for a private bus")
@pytest.mark.skipif(os.geteuid() == 0, reason="Lutris refuses to run as root")
def test_text_commands_run_without_gtk(tmp_path):
    result = run_lutris(tmp_path, "--list-runners")

    assert result.returncode == 0, result.stderr
    assert "wine" in result.stdout.split()


@pytest.mark.skipif(not shutil.which("dbus-run-session"), reason="Needs dbus-run-session for a private bus")
def test_other_commands_are_handed_to_the_gui(tmp_path):
    result = run_lutris(tmp_path, "lutris:rungame/some-game")

    assert result.returncode == 1
    assert "Error importing Lutris application module: No GUI toolkit here" in result.stderr
