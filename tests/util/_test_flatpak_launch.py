from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from lutris.exceptions import GameConfigError
from lutris.runners.flatpak import flatpak
from lutris.util.flatpak import is_game_data_directory


class TestFlatpakGameDirectory(TestCase):
    def runner(self, directory="", **options):
        runner = object.__new__(flatpak)
        runner._config = SimpleNamespace(game_config={"appid": "technology.haniwa.ai5-sdl2", **options})
        runner.game_data = {"directory": directory}
        return runner

    def command(self, runner):
        with patch("lutris.util.flatpak.get_command", return_value=["flatpak"]):
            return runner.play()["command"]

    def test_external_data_and_quoted_font(self):
        command = self.command(self.runner("/home/test/Games/YU NO", args='--font "MS PGothic.ttf"'))
        self.assertEqual(
            command,
            [
                "flatpak",
                "run",
                "--user",
                "--filesystem=/home/test/Games/YU NO:rw",
                "--cwd=/home/test/Games/YU NO",
                "technology.haniwa.ai5-sdl2",
                "--font",
                "MS PGothic.ttf",
            ],
        )

    def test_relative_working_directory(self):
        command = self.command(self.runner("/home/test/Games/yuno", working_dir="data"))
        self.assertIn("--cwd=/home/test/Games/yuno/data", command)
        self.assertIn("--filesystem=/home/test/Games/yuno:rw", command)
        self.assertIn("--filesystem=/home/test/Games/yuno/data:rw", command)

    def test_imported_application_has_no_automatic_grant(self):
        command = self.command(self.runner(install_type="system"))
        self.assertEqual(command, ["flatpak", "run", "--system", "technology.haniwa.ai5-sdl2"])

    def test_host_spawn_preserves_data_arguments(self):
        with patch(
            "lutris.util.flatpak.get_command",
            return_value=["flatpak-spawn", "--host", "flatpak"],
        ):
            command = self.runner("/home/test/Games/yuno").play()["command"]
        self.assertEqual(command[:4], ["flatpak-spawn", "--host", "flatpak", "run"])
        self.assertIn("--cwd=/home/test/Games/yuno", command)

    def test_never_exposes_root_or_interprets_permission_suffixes(self):
        for directory in ("/", "/home/test/Games/yuno:ro"):
            with self.subTest(directory=directory), self.assertRaises(GameConfigError):
                self.command(self.runner(directory))

    def test_trashing_data_does_not_uninstall_the_package(self):
        runner = self.runner("/home/test/Games/yuno")
        runner._config.system_config = {}
        with (
            patch("lutris.util.flatpak.is_game_data_directory", return_value=True),
            patch("lutris.runners.flatpak.system.remove_folder") as trash,
            patch("lutris.runners.flatpak.uninstall_user") as uninstall,
        ):
            runner.remove_game_data(game_path="/home/test/Games/yuno")
        trash.assert_called_once_with("/home/test/Games/yuno")
        uninstall.assert_not_called()

    def test_uninstalling_package_does_not_trash_data(self):
        with (
            patch("lutris.runners.flatpak.system.remove_folder") as trash,
            patch("lutris.runners.flatpak.uninstall_user") as uninstall,
        ):
            self.runner("/home/test/Games/yuno").remove_game_data()
        uninstall.assert_called_once_with("technology.haniwa.ai5-sdl2", "", "")
        trash.assert_not_called()

    def test_protected_data_is_not_trashed(self):
        runner = self.runner("/var/lib/flatpak/app/example")
        runner._config.system_config = {}
        with (
            patch("lutris.util.flatpak.is_game_data_directory", return_value=False),
            patch("lutris.runners.flatpak.system.remove_folder") as trash,
            patch("lutris.runners.flatpak.uninstall_user") as uninstall,
        ):
            runner.remove_game_data(game_path=runner.game_path)
        trash.assert_not_called()
        uninstall.assert_not_called()

    def test_flatpak_storage_and_its_parents_are_protected(self):
        with patch("lutris.util.system.is_removeable", return_value=True):
            self.assertTrue(is_game_data_directory("/home/test/Games/yuno", {}))
            self.assertFalse(is_game_data_directory("/var/lib/flatpak/app/example", {}))
            self.assertFalse(is_game_data_directory("/var/lib", {}))
            self.assertFalse(is_game_data_directory("~/.local/share/flatpak/app/example", {}))
            self.assertFalse(is_game_data_directory("~/.var/app/example", {}))

    def test_symlink_to_flatpak_storage_is_protected(self):
        with (
            patch("lutris.util.system.is_removeable", return_value=True),
            patch(
                "lutris.util.flatpak.os.path.realpath",
                side_effect=lambda p: "/var/lib/flatpak" if p == "/tmp/link" else p,
            ),
        ):
            self.assertFalse(is_game_data_directory("/tmp/link", {}))
