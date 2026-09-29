import os
from contextlib import contextmanager
from itertools import permutations
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from lutris.util.game_finder import find_linux_game_executable, find_windows_game_executable

# Magic strings as libmagic reports them for a typical Unity build.
WINDOWS_UNITY_BUILD = {
    "StillLeben.exe": "PE32+ executable (GUI) x86-64, for MS Windows, 8 sections",
    "UnityCrashHandler64.exe": "PE32+ executable (GUI) x86-64, for MS Windows, 6 sections",
    "UnityPlayer.dll": "PE32+ executable (DLL) (GUI) x86-64, for MS Windows, 6 sections",
}

LINUX_UNITY_BUILD = {
    "StillLeben.x86_64": "ELF 64-bit LSB executable, x86-64, version 1 (SYSV), dynamically linked",
    "UnityPlayer.so": "ELF 64-bit LSB shared object, x86-64, version 1 (SYSV), dynamically linked",
    "UnityPlayer_s.debug": (
        "ELF 64-bit LSB shared object, x86-64, version 1 (SYSV), dynamically linked, with debug_info, not stripped"
    ),
}


class GameFinderTestCase(TestCase):
    """Lays out a game directory and fakes libmagic for the files in it."""

    def setUp(self):
        self.tmp_dir = TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)

    @contextmanager
    def game_folder(self, file_types, order=None, dir_name="game"):
        """Creates the files of `file_types` in a folder called `dir_name`, and forces
        os.walk to list them in `order` (defaulting to the order of `file_types`)."""
        game_dir = os.path.join(self.tmp_dir.name, dir_name)
        os.makedirs(game_dir, exist_ok=True)
        for name in file_types:
            with open(os.path.join(game_dir, name), "wb"):
                pass

        def fake_from_file(path, **_kwargs):
            return file_types[os.path.basename(path)]

        walk_result = [(game_dir, [], list(order or file_types))]
        with patch("lutris.util.magic.from_file", fake_from_file):
            with patch("os.walk", return_value=walk_result):
                yield game_dir


class TestFindWindowsGameExecutable(GameFinderTestCase):
    def test_unity_build_picks_the_game_not_the_crash_handler(self):
        """Issue #6881: UnityCrashHandler64.exe or UnityPlayer.dll gets picked over the
        game's own exe, depending on the order the filesystem lists them in."""
        for order in permutations(WINDOWS_UNITY_BUILD):
            with self.subTest(order=order):
                with self.game_folder(WINDOWS_UNITY_BUILD, order) as game_dir:
                    found = find_windows_game_executable(game_dir)
                self.assertEqual(os.path.basename(found), "StillLeben.exe")

    def test_executable_named_after_its_folder_wins(self):
        file_types = {
            "launcher.exe": "PE32+ executable (GUI) x86-64, for MS Windows",
            "Still Leben.exe": "PE32+ executable (GUI) x86-64, for MS Windows",
            "zzz.exe": "PE32+ executable (GUI) x86-64, for MS Windows",
        }
        with self.game_folder(file_types, dir_name="still-leben") as game_dir:
            found = find_windows_game_executable(game_dir)
        self.assertEqual(os.path.basename(found), "Still Leben.exe")

    def test_longest_name_wins_when_nothing_matches_the_folder(self):
        file_types = {
            "app.exe": "PE32+ executable (GUI) x86-64, for MS Windows",
            "TheGreatEscape.exe": "PE32+ executable (GUI) x86-64, for MS Windows",
        }
        with self.game_folder(file_types, dir_name="unrelated") as game_dir:
            found = find_windows_game_executable(game_dir)
        self.assertEqual(os.path.basename(found), "TheGreatEscape.exe")

    def test_spaces_and_punctuation_count_towards_the_length(self):
        file_types = {
            "Startup.exe": "PE32+ executable (GUI) x86-64, for MS Windows",
            "A-B-C-D-E.exe": "PE32+ executable (GUI) x86-64, for MS Windows",
        }
        with self.game_folder(file_types, dir_name="unrelated") as game_dir:
            found = find_windows_game_executable(game_dir)
        self.assertEqual(os.path.basename(found), "A-B-C-D-E.exe")

    def test_falls_back_to_alphabetical_order_for_names_of_equal_length(self):
        file_types = {
            "zzz.exe": "PE32+ executable (GUI) x86-64, for MS Windows",
            "aaa.exe": "PE32+ executable (GUI) x86-64, for MS Windows",
        }
        with self.game_folder(file_types, dir_name="unrelated") as game_dir:
            found = find_windows_game_executable(game_dir)
        self.assertEqual(os.path.basename(found), "aaa.exe")

    def test_length_does_not_override_a_folder_name_match(self):
        file_types = {
            "Escape.exe": "PE32+ executable (GUI) x86-64, for MS Windows",
            "SomeVeryLongLauncherName.exe": "PE32+ executable (GUI) x86-64, for MS Windows",
        }
        with self.game_folder(file_types, dir_name="escape") as game_dir:
            found = find_windows_game_executable(game_dir)
        self.assertEqual(os.path.basename(found), "Escape.exe")

    def test_dlls_are_never_candidates(self):
        file_types = {"UnityPlayer.dll": "PE32+ executable (DLL) (GUI) x86-64, for MS Windows"}
        with self.game_folder(file_types) as game_dir:
            self.assertEqual(find_windows_game_executable(game_dir), "")


class TestFindLinuxGameExecutable(GameFinderTestCase):
    def test_unity_build_picks_the_game_not_the_engine_or_debug_symbols(self):
        """Issue #6881: UnityPlayer_s.debug gets picked over the game's own binary."""
        for order in permutations(LINUX_UNITY_BUILD):
            with self.subTest(order=order):
                with self.game_folder(LINUX_UNITY_BUILD, order) as game_dir:
                    found = find_linux_game_executable(game_dir)
                self.assertEqual(os.path.basename(found), "StillLeben.x86_64")

    def test_executable_named_after_its_folder_wins(self):
        file_types = {
            "zzz.x86_64": "ELF 64-bit LSB executable, x86-64, version 1 (SYSV)",
            "StillLeben.x86_64": "ELF 64-bit LSB executable, x86-64, version 1 (SYSV)",
        }
        with self.game_folder(file_types, dir_name="still-leben") as game_dir:
            found = find_linux_game_executable(game_dir)
        self.assertEqual(os.path.basename(found), "StillLeben.x86_64")

    def test_pie_executables_are_detected(self):
        """libmagic 5.33 and later report PIE binaries as 'pie executable', which matches
        neither of the substrings the finder originally looked for."""
        file_types = {
            "StillLeben.x86_64": (
                "ELF 64-bit LSB pie executable, x86-64, version 1 (SYSV), dynamically linked, "
                "interpreter /lib64/ld-linux-x86-64.so.2, stripped"
            ),
        }
        with self.game_folder(file_types) as game_dir:
            found = find_linux_game_executable(game_dir)
        self.assertEqual(os.path.basename(found), "StillLeben.x86_64")

    def test_shared_libraries_are_excluded_by_name(self):
        file_types = {
            "StillLeben.x86_64": "ELF 64-bit LSB pie executable, x86-64, version 1 (SYSV)",
            "libsteam_api.so": "ELF 64-bit LSB shared object, x86-64, version 1 (SYSV)",
            "libfmod.so.13": "ELF 64-bit LSB shared object, x86-64, version 1 (SYSV)",
        }
        with self.game_folder(file_types) as game_dir:
            found = find_linux_game_executable(game_dir)
        self.assertEqual(os.path.basename(found), "StillLeben.x86_64")

    def test_shared_objects_are_a_last_resort_not_a_first_choice(self):
        """Old libmagic reports PIE executables as shared objects, so an unnamed one is
        still usable -- but only when there is no real executable to prefer."""
        file_types = {
            "StillLeben": "ELF 64-bit LSB shared object, x86-64, version 1 (SYSV)",
            "helper.x86_64": "ELF 64-bit LSB executable, x86-64, version 1 (SYSV)",
        }
        with self.game_folder(file_types) as game_dir:
            self.assertEqual(os.path.basename(find_linux_game_executable(game_dir)), "helper.x86_64")

        file_types.pop("helper.x86_64")
        with self.game_folder(file_types) as game_dir:
            self.assertEqual(os.path.basename(find_linux_game_executable(game_dir)), "StillLeben")

    def test_shell_scripts_still_take_priority_over_binaries(self):
        file_types = {
            "start.sh": "POSIX shell script executable (binary data)",
            "StillLeben.x86_64": "ELF 64-bit LSB executable, x86-64, version 1 (SYSV)",
        }
        with self.game_folder(file_types, dir_name="still-leben") as game_dir:
            found = find_linux_game_executable(game_dir)
        self.assertEqual(os.path.basename(found), "start.sh")
