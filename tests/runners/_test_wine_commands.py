import os
import tempfile
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from lutris.runners.commands import wine as wine_commands
from lutris.util.test_config import setup_test_environment

setup_test_environment()


class FakeUmuCommand:
    """Stands in for the MonitoredCommand running 'umu-run createprefix'; it exits after
    being polled a given number of times."""

    def __init__(self, polls_before_exit):
        self.polls_before_exit = polls_before_exit
        self.return_code = None

    def start(self):
        pass

    @property
    def game_process_has_exited(self):
        if self.polls_before_exit > 0:
            self.polls_before_exit -= 1
            return False
        return True


class TestCreateProtonPrefix(TestCase):
    def setUp(self):
        prefix_dir = tempfile.TemporaryDirectory()
        self.addCleanup(prefix_dir.cleanup)
        self.prefix = prefix_dir.name

    def create_prefix(self, umu_command):
        with (
            patch.object(wine_commands, "is_disallowed_fs", return_value=False),
            patch.object(wine_commands.proton, "is_umu_path", return_value=True),
            patch.object(wine_commands.proton, "is_proton_path", return_value=True),
            patch.object(wine_commands.proton, "update_proton_env"),
            patch.object(wine_commands.proton, "get_umu_path", return_value="umu-run"),
            patch.object(wine_commands, "MonitoredCommand", return_value=umu_command),
            patch.object(wine_commands, "WinePrefixManager"),
            patch.object(wine_commands.time, "sleep"),
        ):
            wine_commands.create_prefix(
                self.prefix,
                wine_path="/nonexistent/proton/files/bin/wine",
                arch="win64",
                runner=SimpleNamespace(system_config={"env": {}}),
            )

    def write_registry_files(self):
        for name in ("user.reg", "userdef.reg", "system.reg"):
            with open(os.path.join(self.prefix, name), "w", encoding="utf-8"):
                pass

    def test_waits_for_umu_to_exit_after_registry_files_appear(self):
        self.write_registry_files()
        umu_command = FakeUmuCommand(polls_before_exit=3)
        self.create_prefix(umu_command)
        self.assertEqual(umu_command.polls_before_exit, 0)

    def test_raises_if_umu_exits_without_creating_prefix(self):
        with self.assertRaises(RuntimeError):
            self.create_prefix(FakeUmuCommand(polls_before_exit=0))
