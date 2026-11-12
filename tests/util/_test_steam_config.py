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
    def _write_library_folders(self, steam_dir, content, directory="config"):
        config_dir = os.path.join(steam_dir, directory)
        os.makedirs(config_dir, exist_ok=True)
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

    def test_returns_none_when_libraryfolders_is_not_a_dictionary(self):
        with tempfile.TemporaryDirectory() as steam_dir:
            self._write_library_folders(steam_dir, '"libraryfolders"\t\t"4567"\n')

            self.assertIsNone(config.read_library_folders(steam_dir))

    def test_drops_contentstatsid_regardless_of_the_key_case(self):
        content = (
            '"LibraryFolders"\n'
            "{\n"
            '\t"contentstatsid"\t\t"5678"\n'
            '\t"0"\n'
            "\t{\n"
            '\t\t"path"\t\t"/home/user/.local/share/Steam"\n'
            "\t}\n"
            "}\n"
        )
        with tempfile.TemporaryDirectory() as steam_dir:
            self._write_library_folders(steam_dir, content)

            library_folders = config.read_library_folders(steam_dir)

        self.assertIn("0", library_folders)
        self.assertNotIn("contentstatsid", library_folders)

    def test_reads_current_steamapps_location(self):
        with tempfile.TemporaryDirectory() as steam_dir:
            self._write_library_folders(steam_dir, LIBRARY_FOLDERS_VDF, directory="steamapps")

            library_folders = config.read_library_folders(steam_dir)

        self.assertEqual(library_folders["0"]["path"], "/home/user/.local/share/Steam")

    def test_prefers_current_location_over_legacy_location(self):
        canonical_content = LIBRARY_FOLDERS_VDF.replace("/home/user/.local/share/Steam", "/mnt/games/SteamLibrary")
        with tempfile.TemporaryDirectory() as steam_dir:
            self._write_library_folders(steam_dir, LIBRARY_FOLDERS_VDF)
            self._write_library_folders(steam_dir, canonical_content, directory="steamapps")

            library_folders = config.read_library_folders(steam_dir)

        self.assertEqual(library_folders["0"]["path"], "/mnt/games/SteamLibrary")

    def test_falls_back_when_current_location_is_invalid(self):
        with tempfile.TemporaryDirectory() as steam_dir:
            self._write_library_folders(steam_dir, LIBRARY_FOLDERS_VDF)
            self._write_library_folders(steam_dir, '"somethingelse"\n{\n\t"foo"\t\t"bar"\n}\n', directory="steamapps")

            library_folders = config.read_library_folders(steam_dir)

        self.assertEqual(library_folders["0"]["path"], "/home/user/.local/share/Steam")


class TestMountedSteamappsDirs(TestCase):
    def test_finds_conventional_library_on_data_mount(self):
        with tempfile.TemporaryDirectory() as mount_path, tempfile.NamedTemporaryFile(mode="w") as mounts_file:
            steamapps_dir = os.path.join(mount_path, "SteamLibrary", "steamapps")
            os.makedirs(steamapps_dir)
            mounts_file.write(f"/dev/test {mount_path} ext4 rw 0 0\n")
            mounts_file.flush()

            steamapps_dirs = config.get_mounted_steamapps_dirs(mounts_file.name)

        self.assertEqual(steamapps_dirs, [steamapps_dir])

    def test_ignores_non_data_filesystems(self):
        with tempfile.TemporaryDirectory() as mount_path, tempfile.NamedTemporaryFile(mode="w") as mounts_file:
            steamapps_dir = os.path.join(mount_path, "SteamLibrary", "steamapps")
            os.makedirs(steamapps_dir)
            mounts_file.write(f"tmpfs {mount_path} tmpfs rw 0 0\n")
            mounts_file.flush()

            steamapps_dirs = config.get_mounted_steamapps_dirs(mounts_file.name)

        self.assertEqual(steamapps_dirs, [])


class TestGetSteamappsDirs(TestCase):
    def _get_steamapps_dirs(self, library_config):
        with (
            patch.object(config, "STEAM_DATA_DIRS", ()),
            patch.object(config, "get_mounted_steamapps_dirs", return_value=()),
            patch.object(config, "get_steam_config", return_value=None),
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

    def test_includes_mounted_steam_library(self):
        with tempfile.TemporaryDirectory() as mount_path:
            steamapps_dir = os.path.join(mount_path, "SteamLibrary", "steamapps")
            os.makedirs(steamapps_dir)
            with (
                patch.object(config, "STEAM_DATA_DIRS", ()),
                patch.object(config, "get_mounted_steamapps_dirs", return_value=(steamapps_dir,)),
                patch.object(config, "get_steam_config", return_value=None),
                patch.object(config, "get_library_config", return_value=None),
                patch.dict(os.environ, {"STEAM_EXTRA_COMPAT_TOOLS_PATHS": ""}),
            ):
                steamapps_dirs = list(config.get_steamapps_dirs())

        self.assertEqual(steamapps_dirs, [steamapps_dir])

    def test_ignores_unmounted_library_entries(self):
        with tempfile.TemporaryDirectory() as steam_dir:
            os.makedirs(os.path.join(steam_dir, "steamapps"))

            steamapps_dirs = self._get_steamapps_dirs({"0": {"path": steam_dir, "mounted": "0"}})

        self.assertEqual(steamapps_dirs, [])

    def test_ignores_library_entries_that_are_not_dicts(self):
        # Old-format libraryfolders.vdf mixes plain string values with library entries.
        self.assertEqual(self._get_steamapps_dirs({"TimeNextStatsReport": "1234", "1": "/media/games"}), [])
