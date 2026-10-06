import os
import tempfile
from unittest import TestCase
from unittest.mock import patch

from lutris.util.steam import config

LIBRARY_FOLDERS_VDF = """\
"libraryfolders"
{
\t"contentstatsid"\t\t"5678"
\t"0"
\t{
\t\t"path"\t\t"/home/user/.local/share/Steam"
\t\t"label"\t\t""
\t\t"contentid"\t\t"1234"
\t\t"totalsize"\t\t"0"
\t\t"apps"
\t\t{
\t\t\t"228980"\t\t"123456"
\t\t}
\t}
}
"""

# Steam is not required to write the "libraryfolders" key first.
LIBRARY_FOLDERS_VDF_WITH_TRAILING_KEY = """\
"somethingelse"
{
\t"foo"\t\t"bar"
}
"libraryfolders"
{
\t"0"
\t{
\t\t"path"\t\t"/home/user/.local/share/Steam"
\t}
}
"""


class TestReadLibraryFolders(TestCase):
    def _write_library_folders(self, steam_dir, content):
        config_dir = os.path.join(steam_dir, "config")
        os.makedirs(config_dir)
        with open(os.path.join(config_dir, "libraryfolders.vdf"), "w", encoding="utf-8") as vdf_file:
            vdf_file.write(content)

    def test_returns_none_without_a_steam_data_dir(self):
        self.assertIsNone(config.read_library_folders(None))

    def test_returns_none_without_a_libraryfolders_file(self):
        with tempfile.TemporaryDirectory() as steam_dir:
            self.assertIsNone(config.read_library_folders(steam_dir))

    def test_returns_none_when_libraryfolders_is_missing(self):
        with tempfile.TemporaryDirectory() as steam_dir:
            self._write_library_folders(steam_dir, '"somethingelse"\n{\n\t"foo"\t\t"bar"\n}\n')

            self.assertIsNone(config.read_library_folders(steam_dir))

    def test_returns_library_folders_and_drops_contentstatsid(self):
        with tempfile.TemporaryDirectory() as steam_dir:
            self._write_library_folders(steam_dir, LIBRARY_FOLDERS_VDF)

            library_folders = config.read_library_folders(steam_dir)

        self.assertIn("0", library_folders)
        self.assertEqual(library_folders["0"]["path"], "/home/user/.local/share/Steam")
        self.assertNotIn("contentstatsid", library_folders)

    def test_finds_libraryfolders_when_it_is_not_the_first_key(self):
        with tempfile.TemporaryDirectory() as steam_dir:
            self._write_library_folders(steam_dir, LIBRARY_FOLDERS_VDF_WITH_TRAILING_KEY)

            library_folders = config.read_library_folders(steam_dir)

        self.assertIn("0", library_folders)


class TestGetSteamappsDirs(TestCase):
    def _get_steamapps_dirs(self, library_config):
        with (
            patch.object(config, "STEAM_DATA_DIRS", ()),
            patch.object(config, "get_steam_config", return_value={}),
            patch.object(config, "get_library_config", return_value=library_config),
            patch.dict(os.environ, {"STEAM_EXTRA_COMPAT_TOOLS_PATHS": ""}),
        ):
            return list(config.get_steamapps_dirs())

    def test_ignores_library_entries_without_a_path(self):
        self.assertEqual(self._get_steamapps_dirs({"0": {"totalsize": "0"}}), [])

    def test_includes_mounted_library_entries(self):
        with tempfile.TemporaryDirectory() as steam_dir:
            steamapps_dir = os.path.join(steam_dir, "steamapps")
            os.makedirs(steamapps_dir)

            steamapps_dirs = self._get_steamapps_dirs({"0": {"path": steam_dir, "mounted": "1"}})

        self.assertEqual(steamapps_dirs, [steamapps_dir])

    def test_ignores_unmounted_library_entries(self):
        with tempfile.TemporaryDirectory() as steam_dir:
            os.makedirs(os.path.join(steam_dir, "steamapps"))

            steamapps_dirs = self._get_steamapps_dirs({"0": {"path": steam_dir, "mounted": "0"}})

        self.assertEqual(steamapps_dirs, [])
