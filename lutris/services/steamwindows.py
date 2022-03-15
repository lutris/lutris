import os
from gettext import gettext as _

from gi.repository import Gio

from lutris.database.games import get_game_by_field, get_games
from lutris.game import Game
from lutris.installer import get_installers
from lutris.services.steam import SteamGame, SteamService
from lutris.util import system
from lutris.util.log import logger
from lutris.util.strings import slugify

STEAM_INSTALLER = "steam-wine"  # Lutris installer used to setup the Steam client


class SteamWindowsGame(SteamGame):
    service = "steamwindows"
    installer_slug = "steamwindows"
    runner = "wine"


class SteamWindowsService(SteamService):
    id = "steamwindows"
    name = _("Steam for Windows")
    runner = "wine"
    game_class = SteamWindowsGame
    client_installer = "steam-wine"

    def generate_installer(self, db_game, steam_game):
        """Generate a basic Steam installer"""
        return {
            "name": db_game["name"],
            "version": self.name,
            "slug": slugify(db_game["name"]) + "-" + self.id,
            "game_slug": slugify(db_game["name"]),
            "runner": self.runner,
            "appid": db_game["appid"],
            "script": {
                "requires": self.client_installer,
                "game": {
                    "exe": steam_game.config.game_config["exe"],
                    "args": "-no-cef-sandbox -applaunch %s" % db_game["appid"],
                    "prefix": steam_game.config.game_config["prefix"],
                }
            }
        }

    def get_steam(self):
        db_entry = get_game_by_field(self.client_installer, "installer_slug")
        if db_entry:
            return Game(db_entry["id"])

    def install(self, db_game):
        steam_game = self.get_steam()
        if not steam_game:
            installers = get_installers(
                game_slug=self.client_installer,
            )
            appid = None
        else:
            installers = [self.generate_installer(db_game, steam_game)]
            appid = db_game["appid"]
            db_games = get_games(filters={"service_id": appid, "installed": "1", "service": self.id})
            existing_game = self.match_existing_game(db_games, appid)
            if existing_game:
                logger.debug("Found steam game: %s", existing_game)
                game = Game(existing_game.id)
                game.save()
                return
        application = Gio.Application.get_default()
        application.show_installer_window(
            installers,
            service=self,
            appid=appid
        )

    @property
    def steamapps_paths(self):
        """Return steamapps paths"""
        steam_game = self.get_steam()
        if not steam_game:
            return []
        dirs = []
        steam_path = steam_game.config.game_config["exe"]
        steam_data_dir = os.path.dirname(steam_path)
        if steam_data_dir:
            main_dir = os.path.join(steam_data_dir, "steamapps")
            main_dir = system.fix_path_case(main_dir)
            if main_dir and os.path.isdir(main_dir):
                dirs.append(os.path.abspath(main_dir))
        return dirs
