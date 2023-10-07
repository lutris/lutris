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

    game_paths = None

    def load(self):
        if not os.path.isfile(SCUMMVM_CONFIG_FILE):
            return

        config = ConfigParser()
        config.read(SCUMMVM_CONFIG_FILE)
        config_sections = config.sections()
        self.game_paths = {}

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
            self.game_paths[game.slug] = game.path

            game.save()

    def generate_installer(self, game):
        return {
            "name": game["name"],
            "version": "ScummVM",
            "slug": game["slug"],
            "game_slug": slugify(game["lutris_slug"]),
            "runner": "scummvm",
            "script": {
                "game": {
                    "game_id": game["appid"],
                    "path": self.game_paths[game["slug"]],
                    "platform": "scummvm"
                }
            }
        }


class ScummvmGame(ServiceGame):
    service = "scummvm"
    runner = "scummvm"
