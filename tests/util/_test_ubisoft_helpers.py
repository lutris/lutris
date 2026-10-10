import os
import tempfile
from unittest import TestCase
from unittest.mock import patch

from lutris.util.ubisoft import helpers


def _normalized(path):
    return os.path.normcase(os.path.normpath(path))


class TestReturnLocalGamePath(TestCase):
    def test_returns_none_when_the_registry_has_no_install_dir(self):
        with patch.object(helpers, "WineRegistry") as wine_registry:
            wine_registry.return_value.query.return_value = None

            self.assertIsNone(helpers._return_local_game_path("1234"))

    def test_normalizes_the_registry_path(self):
        with patch.object(helpers, "WineRegistry") as wine_registry:
            wine_registry.return_value.query.return_value = "C:/Games/Some Game"

            self.assertEqual(helpers._return_local_game_path("1234"), _normalized("C:/Games/Some Game"))


class TestGetLocalGamePath(TestCase):
    def test_returns_none_when_neither_lookup_finds_a_path(self):
        with patch.object(helpers, "WineRegistry") as wine_registry:
            wine_registry.return_value.query.return_value = None

            self.assertIsNone(helpers.get_local_game_path(None, "1234"))

    def test_falls_back_to_the_special_registry_path(self):
        with patch.object(helpers, "WineRegistry") as wine_registry:
            wine_registry.return_value.query.side_effect = [None, "D:/Ubisoft Game"]

            game_path = helpers.get_local_game_path("HKEY_LOCAL_MACHINE\\Software\\Ubisoft", "1234")

        self.assertEqual(game_path, "D:/Ubisoft Game")


class TestReadStatusFromStateFile(TestCase):
    def _game_path(self, content):
        """Return a game directory holding a uplay_install.state file; no file
        is created when content is None."""
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        if content is not None:
            with open(os.path.join(temp_dir.name, "uplay_install.state"), "wb") as state_file:
                state_file.write(content)
        return temp_dir.name

    def test_installed_when_the_state_file_starts_with_a_newline_byte(self):
        game_path = self._game_path(b"\n\x01\x00")

        self.assertEqual(helpers._read_status_from_state_file(game_path), helpers.INSTALLED)

    def test_not_installed_when_the_state_file_has_no_newline_byte(self):
        game_path = self._game_path(b"\x01\x00")

        self.assertEqual(helpers._read_status_from_state_file(game_path), helpers.NOT_INSTALLED)

    def test_not_installed_and_silent_when_the_state_file_is_empty(self):
        game_path = self._game_path(b"")

        with self.assertNoLogs(helpers.logger, level="WARNING"):
            status = helpers._read_status_from_state_file(game_path)

        self.assertEqual(status, helpers.NOT_INSTALLED)

    def test_not_installed_and_silent_when_the_state_file_is_missing(self):
        game_path = self._game_path(None)

        with self.assertNoLogs(helpers.logger, level="WARNING"):
            status = helpers._read_status_from_state_file(game_path)

        self.assertEqual(status, helpers.NOT_INSTALLED)

    def test_logs_a_warning_when_the_state_file_cannot_be_read(self):
        game_path = self._game_path(b"\n")

        with (
            self.assertLogs(helpers.logger, level="WARNING"),
            patch("builtins.open", side_effect=PermissionError("permission denied")),
        ):
            status = helpers._read_status_from_state_file(game_path)

        self.assertEqual(status, helpers.NOT_INSTALLED)
