import os
from gettext import gettext as _
from typing import Any

from lutris.database.games import get_game_by_field
from lutris.game import Game
from lutris.services.steam import SteamGame, SteamService
from lutris.util import system
from lutris.util.strings import slugify


class SteamWindowsGame(SteamGame):
    service = "steamwindows"
    installer_slug = "steamwindows"
    runner = "wine"


class SteamWindowsService(SteamService):
    id = "steamwindows"
    name = _("Steam for Windows")
    description = _("Use only for the rare games or mods requiring the Windows version of Steam")
    runner = "wine"
    game_class = SteamWindowsGame
    client_installer = "steam-wine"

    def generate_installer(self, db_game, steam_game):
        """Generate a basic Steam installer"""
        return {
            "name": db_game["name"],
            "version": self.name,
            "slug": slugify(db_game["name"]) + "-" + self.id,
            "game_slug": self.get_installed_slug(db_game),
            "runner": self.get_installed_runner_name(db_game),
            "appid": db_game["appid"],
            "script": {
                "requires": self.client_installer,
                "game": {
                    "exe": steam_game.config.game_config["exe"],
                    "args": "-no-cef-sandbox -applaunch %s" % db_game["appid"],
                    "prefix": steam_game.config.game_config["prefix"],
                },
            },
        }

    def get_installed_runner_name(self, db_game):
        return self.runner

    def get_steam(self):
        db_entry = get_game_by_field(self.client_installer, "installer_slug") or get_game_by_field(
            self.client_installer, "slug"
        )
        if db_entry:
            return Game(db_entry["id"])

    def generate_installers(self, db_game: dict[str, Any]) -> list[dict[str, Any]]:
        return [self.generate_installer(db_game, Game(self.get_installation_launcher()["id"]))]

    @property
    def steamapps_paths(self):
        """Return steamapps paths"""
        steam_game = self.get_steam()
        if not steam_game or not steam_game.config or "exe" not in steam_game.config.game_config:
            return []
        dirs = []
        steam_path = steam_game.config.game_config["exe"]
        steam_data_dir = os.path.dirname(steam_path)
        if steam_data_dir:
            main_dir = os.path.join(steam_data_dir, "steamapps")
            main_dir = system.fix_path_case(main_dir)
            if os.path.isdir(main_dir):
                dirs.append(os.path.abspath(main_dir))
        return dirs
