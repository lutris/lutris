import os
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import requests

from lutris.database.games import add_game, delete_game, get_games, update_existing
from lutris.installer.errors import ScriptingError
from lutris.installer.installer import LutrisInstaller
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
        command_name, command, params = interpreter._map_command({"move": "whatever"})
        self.assertEqual(command_name, "move")
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


class TestCreatesGameFolder(TestCase):
    def get_installer(self, script):
        return MockInterpreter({**TEST_INSTALLER, "script": script}, None).installer

    def test_script_without_files_or_gamedir_needs_no_folder(self):
        installer = self.get_installer(
            {
                "game": {"exe": "/usr/bin/true"},
                "installer": [{"execute": {"command": "/bin/true"}}],
            }
        )
        self.assertFalse(installer.creates_game_folder)

    def test_command_using_gamedir_needs_a_folder(self):
        installer = self.get_installer(
            {
                "game": {"exe": "game.sh"},
                "installer": [{"write_file": {"file": "$GAMEDIR/game.sh", "content": "hello"}}],
            }
        )
        self.assertTrue(installer.creates_game_folder)

    def test_braced_gamedir_needs_a_folder(self):
        installer = self.get_installer(
            {
                "game": {"exe": "game.sh"},
                "installer": [{"mkdir": "${GAMEDIR}/data"}],
            }
        )
        self.assertTrue(installer.creates_game_folder)

    def test_game_section_using_gamedir_needs_a_folder(self):
        installer = self.get_installer(
            {
                "game": {"exe": "$GAMEDIR/game.sh"},
                "installer": [{"execute": {"command": "/bin/true"}}],
            }
        )
        self.assertTrue(installer.creates_game_folder)

    def test_gamedir_lookalikes_do_not_need_a_folder(self):
        installer = self.get_installer(
            {
                "game": {"exe": "/usr/bin/true"},
                "installer": [{"execute": {"command": "/bin/true", "args": "$GAMEDIRECTORY $CACHE"}}],
            }
        )
        self.assertFalse(installer.creates_game_folder)

    def test_extending_script_using_gamedir_needs_no_folder(self):
        # 'extends' scripts install into the folder of the game they extend, which
        # already exists, so no location page is needed. This one is built directly
        # since the interpreter refuses scripts whose dependency isn't installed.
        script = {
            "extends": "some-other-game",
            "game": {"exe": "$GAMEDIR/game.sh"},
            "installer": [{"write_file": {"file": "$GAMEDIR/game.sh", "content": "hello"}}],
        }
        interpreter = MockInterpreter(TEST_INSTALLER, None)
        installer = LutrisInstaller({**TEST_INSTALLER, "script": script}, interpreter, service=None, appid=None)
        self.assertFalse(installer.creates_game_folder)


class _FakeService:
    id = "gog"


class TestReusesServiceLibraryEntry(TestCase):
    """Installing a service game fills its library entry, even when lutris.net
    now gives the game another slug than the one in the library."""

    def setUp(self):
        self.service_id = "2086050016%s" % id(self)
        self.library_game_id = add_game(
            name="SimCity 3000",
            slug="simcity-3000",
            service="gog",
            service_id=self.service_id,
            installed=0,
        )

    def tearDown(self):
        for game in get_games(filters={"service": "gog", "service_id": self.service_id}):
            delete_game(game["id"])

    def get_installer(self):
        installer = {**TEST_INSTALLER, "game_slug": "simcity-3000-unlimited", "slug": "simcity_3000"}
        delegate = ScriptInterpreter.InterpreterUIDelegate(service=_FakeService(), appid=self.service_id)
        return ScriptInterpreter(installer, delegate).installer

    def test_install_reuses_uninstalled_library_entry(self):
        self.assertEqual(self.get_installer().game_id, self.library_game_id)

    def test_installed_library_entry_is_not_reused(self):
        update_existing(id=self.library_game_id, installed=1)
        self.assertIsNone(self.get_installer().game_id)


class TestLocalFiles(TestCase):
    """Local paths in a script's files are only allowed for local scripts."""

    def get_installer(self, file_url, installer_file=None):
        installer = {
            **TEST_INSTALLER,
            "script": {"files": [{"setup": file_url}], "game": {"exe": "test"}},
        }
        if installer_file:
            installer["installer_file"] = installer_file
        return MockInterpreter(installer, None).installer

    def test_website_script_cannot_use_absolute_path(self):
        installer = self.get_installer("/home/user/.ssh/id_rsa")
        with self.assertRaises(ScriptingError):
            installer.prepare_game_files({})

    def test_website_script_cannot_use_file_url(self):
        installer = self.get_installer("file:///etc/passwd")
        with self.assertRaises(ScriptingError):
            installer.prepare_game_files({})

    def test_website_script_cannot_use_scriptdir(self):
        installer = self.get_installer("$SCRIPTDIR/setup.exe")
        with self.assertRaises(ScriptingError):
            installer.prepare_game_files({})

    def test_local_script_can_use_scriptdir(self):
        with TemporaryDirectory() as script_dir:
            script_path = os.path.join(script_dir, "game.yml")
            open(script_path, "w", encoding="utf-8").close()
            installer = self.get_installer("$SCRIPTDIR/setup.exe", installer_file=script_path)
            installer.prepare_game_files({})
        self.assertEqual(installer.files[0].url, "file://%s/setup.exe" % os.path.realpath(script_dir))

    def test_website_script_can_use_https(self):
        installer = self.get_installer("https://example.com/setup.exe")
        installer.prepare_game_files({})
        self.assertEqual(installer.files[0].url, "https://example.com/setup.exe")
