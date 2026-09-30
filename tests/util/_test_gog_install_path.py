"""Tests for finding where a GOG game was installed inside a Wine prefix."""

import json
import os
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase

from lutris.installer.installer import apply_gog_config_if_exe_missing
from lutris.util.gog import get_gog_game_path

GOG_ID = "2106942030"


def make_game(prefix, folder, exe="Forager.exe", gog_id=GOG_ID, with_exe=True):
    """Lay out a GOG install the way GOG's installer does: the game and its goggame-*.info."""
    game_dir = os.path.join(prefix, "drive_c", folder)
    os.makedirs(game_dir, exist_ok=True)
    info = {"gameId": gog_id, "playTasks": [{"isPrimary": True, "path": exe, "name": "Forager"}]}
    with open(os.path.join(game_dir, "goggame-%s.info" % gog_id), "w", encoding="utf-8") as info_file:
        json.dump(info, info_file)
    if with_exe:
        open(os.path.join(game_dir, exe), "w", encoding="utf-8").close()
    return game_dir


def make_installer(prefix, exe):
    interpreter = SimpleNamespace(target_path=prefix, _substitute=lambda v: v.replace("$GAMEDIR", prefix))
    return SimpleNamespace(
        script={"game": {"exe": exe, "prefix": "$GAMEDIR"}},
        interpreter=interpreter,
        service=SimpleNamespace(id="gog"),
        service_appid=GOG_ID,
    )


class TestGogGamePath(TestCase):
    def test_default_folder(self):
        with TemporaryDirectory() as prefix:
            game_dir = make_game(prefix, "GOG Games/Forager")
            self.assertEqual(get_gog_game_path(prefix, GOG_ID), game_dir)

    def test_folder_chosen_by_player(self):
        with TemporaryDirectory() as prefix:
            game_dir = make_game(prefix, "Games/Forager")
            self.assertEqual(get_gog_game_path(prefix, GOG_ID), game_dir)

    def test_ignores_copies_without_the_game(self):
        """GOG's support installer keeps a copy of the .info file in ProgramData."""
        with TemporaryDirectory() as prefix:
            make_game(prefix, "ProgramData/GOG.com/supportInstaller/" + GOG_ID, with_exe=False)
            game_dir = make_game(prefix, "Games/Forager")
            self.assertEqual(get_gog_game_path(prefix, GOG_ID), game_dir)

    def test_other_products_are_ignored(self):
        with TemporaryDirectory() as prefix:
            make_game(prefix, "Games/Other", gog_id="1")
            game_dir = make_game(prefix, "Games/Forager")
            self.assertEqual(get_gog_game_path(prefix, GOG_ID), game_dir)


class TestScriptedGogInstall(TestCase):
    def test_missing_exe_is_found_in_chosen_folder(self):
        with TemporaryDirectory() as prefix:
            game_dir = make_game(prefix, "Games/Forager")
            installer = make_installer(prefix, "drive_c/GOG Games/Forager/Forager.exe")
            apply_gog_config_if_exe_missing(installer)
            self.assertEqual(installer.script["game"]["exe"], os.path.join(game_dir, "Forager.exe"))

    def test_existing_exe_is_kept(self):
        with TemporaryDirectory() as prefix:
            make_game(prefix, "GOG Games/Forager")
            exe = "drive_c/GOG Games/Forager/Forager.exe"
            installer = make_installer(prefix, exe)
            apply_gog_config_if_exe_missing(installer)
            self.assertEqual(installer.script["game"], {"exe": exe, "prefix": "$GAMEDIR"})

    def test_auto_exe_is_left_to_autosetup(self):
        with TemporaryDirectory() as prefix:
            make_game(prefix, "Games/Forager")
            installer = make_installer(prefix, "_xXx_AUTO_WIN32_xXx_")
            apply_gog_config_if_exe_missing(installer)
            self.assertEqual(installer.script["game"]["exe"], "_xXx_AUTO_WIN32_xXx_")
