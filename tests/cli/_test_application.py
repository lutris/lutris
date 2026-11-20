"""`lutris` runs the commands that need no GUI without a GUI toolkit."""

import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

import pytest

LUTRIS = Path(sysconfig.get_path("scripts")) / "lutris"

RUN_WITHOUT_QT = """
import sys


class BlockQt:
    def find_spec(self, name, path=None, target=None):
        if name == "PySide6":
            raise ImportError("No GUI toolkit here")
        return None


sys.meta_path.insert(0, BlockQt())
sys.argv[0] = "lutris"
from lutris.launcher import main
raise SystemExit(main())
"""


def isolated_profile(tmp_path: Path) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in ("DISPLAY", "WAYLAND_DISPLAY")}
    return env | {
        "HOME": str(tmp_path),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
    }


def run_lutris(tmp_path: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run `lutris` on a private session bus, with a fresh profile and no display."""
    return subprocess.run(
        ["dbus-run-session", "--", sys.executable, "-c", RUN_WITHOUT_QT, *arguments],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=isolated_profile(tmp_path),
        timeout=120,
        check=False,
    )


@pytest.mark.skipif(not shutil.which("dbus-run-session"), reason="Needs dbus-run-session for a private bus")
@pytest.mark.skipif(os.geteuid() == 0, reason="Lutris refuses to run as root")
def test_text_commands_run_without_qt(tmp_path):
    result = run_lutris(tmp_path, "--list-runners")

    assert result.returncode == 0, result.stderr
    assert "wine" in result.stdout.split()


@pytest.mark.skipif(not shutil.which("dbus-run-session"), reason="Needs dbus-run-session for a private bus")
def test_other_commands_are_handed_to_the_gui(tmp_path):
    result = run_lutris(tmp_path, "lutris:rungame/some-game")

    assert result.returncode == 1
    assert "Error importing the Lutris Qt frontend: No GUI toolkit here" in result.stderr


@pytest.mark.skipif(not all(map(shutil.which, ("dbus-run-session", "gdbus"))), reason="Needs a private D-Bus session")
@pytest.mark.skipif(os.geteuid() == 0, reason="Lutris refuses to run as root")
def test_default_qt_window_starts_and_accepts_forwarded_commands(tmp_path: Path) -> None:
    script = """
import os
import signal
import subprocess
import sys

command = [sys.argv[1]]
with open('primary.log', 'w+') as log:
    primary = subprocess.Popen(command, stdout=log, stderr=log)
    try:
        subprocess.run(['gdbus', 'wait', '--session', '--timeout', '10', 'net.lutris.Lutris'], check=True)
        forwarded = subprocess.run(
            [*command, '--list-runners'], env=os.environ | {'QT_QPA_PLATFORM': 'not-a-platform'},
            capture_output=True, text=True, check=True, timeout=10,
        )
        assert 'wine' in forwarded.stdout.split(), forwarded
        assert primary.poll() is None
        primary.send_signal(signal.SIGINT)
        assert primary.wait(timeout=10) == 0
        log.seek(0)
        assert 'QQmlApplicationEngine failed to load component' not in log.read()
    except Exception:
        log.seek(0)
        sys.stderr.write(log.read())
        raise
    finally:
        if primary.poll() is None:
            primary.kill()
        primary.wait()
"""
    env = isolated_profile(tmp_path) | {
        "LUTRIS_RUNTIME": "0",
        "QT_QPA_PLATFORM": "offscreen",
        "QT_QUICK_BACKEND": "software",
    }
    result = subprocess.run(
        ["dbus-run-session", "--", sys.executable, "-c", script, str(LUTRIS)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
        timeout=35,
        check=False,
    )
    assert result.returncode == 0, result.stderr
