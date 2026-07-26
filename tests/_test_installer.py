from unittest import TestCase
from unittest.mock import patch

import requests

from lutris.installer.errors import ScriptingError
from lutris.installer.interpreter import ScriptInterpreter
from lutris.util.test_config import setup_test_environment

setup_test_environment()

TEST_INSTALLER = {
    "script": {"game": {"exe": "test"}},
    "version": "test",
    "game_slug": "test",
    "name": "test",
    "slug": "test",
    "runner": "linux",
}


class MockInterpreter(ScriptInterpreter):
    """A script interpreter mock."""

    runner = "linux"


class TestScriptInterpreter(TestCase):
    def get_moddb_interpreter(self, moddb_url):
        installer = {
            **TEST_INSTALLER,
            "script": {
                "files": [{"moddb_file": {"url": moddb_url, "filename": "test-file.zip"}}],
                "game": {"exe": "test"},
            },
        }
        return MockInterpreter(installer, None)

    def test_script_with_correct_values_is_valid(self):
        installer = {
            "runner": "linux",
            "script": {"exe": "doom"},
            "name": "Doom",
            "slug": "doom",
            "game_slug": "doom",
            "version": "doom-gzdoom",
        }
        interpreter = ScriptInterpreter(installer, None)
        self.assertEqual(interpreter.installer.game_name, "Doom")
        self.assertFalse(interpreter.installer.get_errors())

    def test_move_requires_src_and_dst(self):
        script = {
            "foo": "bar",
            "script": {},
            "name": "missing_runner",
            "game_slug": "missing-runner",
            "slug": "some-slug",
            "runner": "linux",
            "version": "bar-baz",
        }
        with self.assertRaises(ScriptingError):
            interpreter = ScriptInterpreter(script, None)
            interpreter._get_move_paths({})

    def test_get_command_returns_a_method(self):
        interpreter = MockInterpreter(TEST_INSTALLER, None)
        command, params = interpreter._map_command({"move": "whatever"})
        self.assertIn("bound method CommandsMixin.move", str(command))
        self.assertEqual(params, "whatever")

    def test_get_command_doesnt_return_private_methods(self):
        interpreter = MockInterpreter(TEST_INSTALLER, None)
        with self.assertRaises(ScriptingError) as ex:
            interpreter._map_command({"_substitute": "foo"})
        self.assertEqual(ex.exception.message, 'The command "substitute" does not exist.')

    def test_prepare_game_files_resolves_moddb_url(self):
        moddb_url = "https://www.moddb.com/downloads/test-file"
        mirror_url = "https://www.moddb.com/downloads/mirror/test-file"
        interpreter = self.get_moddb_interpreter(moddb_url)

        with patch("lutris.installer.installer.ModDB.transform_url", return_value=mirror_url):
            interpreter.installer.prepare_game_files([])

        installer_file = interpreter.installer.files[0]
        self.assertEqual(installer_file.url, mirror_url)
        self.assertEqual(installer_file.default_provider, "download")

    def test_prepare_game_files_keeps_moddb_file_selectable_on_resolution_error(self):
        moddb_url = "https://www.moddb.com/downloads/test-file"
        interpreter = self.get_moddb_interpreter(moddb_url)

        with patch(
            "lutris.installer.installer.ModDB.transform_url",
            side_effect=requests.HTTPError("403 Client Error"),
        ):
            interpreter.installer.prepare_game_files([])

        installer_file = interpreter.installer.files[0]
        self.assertEqual(
            installer_file.url,
            "N/A:Download from https://www.moddb.com/downloads/test-file and select the file here",
        )
        self.assertEqual(installer_file.default_provider, "user")
        self.assertEqual(installer_file.providers, {"user"})
        self.assertEqual(installer_file.filename, "test-file.zip")

    def test_prepare_game_files_keeps_moddb_configuration_errors_visible(self):
        moddb_url = "https://www.moddb.com/downloads/test-file"
        interpreter = self.get_moddb_interpreter(moddb_url)

        with patch("lutris.installer.installer.ModDB.transform_url", side_effect=RuntimeError("Invalid ModDB URL")):
            with self.assertRaises(RuntimeError):
                interpreter.installer.prepare_game_files([])
