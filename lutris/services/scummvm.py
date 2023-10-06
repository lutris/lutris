import os
import re
from configparser import ConfigParser
from gettext import gettext as _

from lutris import settings
from lutris.services.base import BaseService
from lutris.services.service_game import ServiceGame
from lutris.services.service_media import ServiceMedia
from lutris.util.strings import slugify

SCUMMVM_CONFIG_FILE = os.path.join(os.path.expanduser("~/.config/scummvm"), "scummvm.ini")


# Dummy banner. Maybe the download from lutris should be implemented at this place
class ScummvmBanner(ServiceMedia):
    service = "scummvm"
    source = "local"
    size = (96, 32)
    file_pattern = "%s.png"
    file_format = "jpeg"
    dest_path = settings.CACHE_DIR


class ScummvmService(BaseService):
    id = "scummvm"
    icon = "scummvm"
    name = _("ScummVM")
    local = True
    medias = {
        "icon": ScummvmBanner
    }

    def get_games(self):
        if not os.path.isfile(SCUMMVM_CONFIG_FILE):
            return None

        config = ConfigParser()
        config.read(SCUMMVM_CONFIG_FILE)
        config_sections = config.sections()
        games = {}

        for section in config_sections:
            if section == "scummvm":
                continue
            game = ScummvmGame()
            game.name = re.split(r" \(.*\)$", config[section]["description"])[0]
            game.slug = slugify(game.name)
            game.appid = section
            game.game_id = section
            game.runner = "scummvm"
            game.lutris_slug = game.slug
            game.details = config[section]["description"]
            game.path = config[section]["path"]
            games[game.slug] = game

        return games

    def load(self):
        games = self.get_games()
        if games is not None:
            for slug in games:
                games[slug].save()

    def generate_installer(self, game):
        games = self.get_games()
        game_data = games.get(game["slug"])

        return {
            "name": game["name"],
            "version": "ScummVM",
            "slug": game["slug"],
            "game_slug": slugify(game["lutris_slug"]),
            "runner": "scummvm",
            "script": {
                "game": {
                    "game_id": game["appid"],
                    "path": game_data.path,
                    "platform": "scummvm"
                }
            }
        }


class ScummvmGame(ServiceGame):
    service = "scummvm"
    runner = "scummvm"
