"""Tests for importing games installed through the EA App."""

import unittest
from unittest.mock import MagicMock, patch

from lutris.services import ea_app

EA_APP_GAME = {
    "name": "EA App",
    "slug": "ea-app",
    "runner": "wine",
    "directory": "/games/ea-app/drive_c/Program Files/Electronic Arts/EA Desktop",
    "configpath": "ea-app-1234",
}


class TestInstallFromEAApp(unittest.TestCase):
    def install(self, service_game):
        service = ea_app.EAAppService()
        with (
            patch.object(ea_app.ServiceGameCollection, "get_game", return_value=service_game),
            patch.object(ea_app, "get_game_by_field", return_value=None),
            patch.object(ea_app, "LutrisConfig", return_value=MagicMock(game_level={"game": {}})),
            patch.object(ea_app, "write_game_config", return_value="configpath"),
            patch.object(ea_app, "get_launch_arguments", return_value=""),
            patch.object(ea_app, "add_game") as add_game,
        ):
            slug = service.install_from_ea_app(EA_APP_GAME, ["Origin.OFR.50.0001"])
        return slug, add_game

    def test_game_gets_its_own_slug(self):
        slug, add_game = self.install({"name": "Mass Effect Legendary Edition"})

        self.assertEqual(slug, "mass-effect-legendary-edition")
        self.assertEqual(add_game.call_args.kwargs["slug"], "mass-effect-legendary-edition")

    def test_games_do_not_share_the_ea_app_slug(self):
        first_slug, _add_game = self.install({"name": "Dead Space"})
        second_slug, _add_game = self.install({"name": "Titanfall 2"})

        self.assertNotEqual(first_slug, second_slug)
        self.assertNotIn(EA_APP_GAME["slug"], (first_slug, second_slug))
