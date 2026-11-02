import os
from types import SimpleNamespace
from unittest import TestCase

from lutris.game import Game


class TestFlatpakGamePath(TestCase):
    def game(self, directory):
        return SimpleNamespace(
            config=SimpleNamespace(game_config={"appid": "technology.haniwa.ai5-sdl2"}),
            runner_name="flatpak",
            directory=directory,
        )

    def test_external_data_directory_is_used_for_path_cache(self):
        self.assertEqual(
            Game.get_path_from_config(self.game("/home/test/Games/YU NO")),
            "/home/test/Games/YU NO",
        )

    def test_user_directory_is_expanded(self):
        self.assertEqual(
            Game.get_path_from_config(self.game("~/Games/yuno")),
            os.path.expanduser("~/Games/yuno"),
        )

    def test_imported_app_does_not_invent_a_deployment_path(self):
        self.assertEqual(Game.get_path_from_config(self.game("")), "")
