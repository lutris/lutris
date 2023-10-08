import json
import os
import re
from configparser import ConfigParser
from gettext import gettext as _

from lutris import settings
from lutris.services.base import BaseService
from lutris.services.service_game import ServiceGame
from lutris.services.service_media import ServiceMedia
from lutris.util import system
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

    def load(self):
        if not system.path_exists(SCUMMVM_CONFIG_FILE):
            return

        config = ConfigParser()
        config.read(SCUMMVM_CONFIG_FILE)
        config_sections = config.sections()

        for section in config_sections:
            if section == "scummvm":
                continue
            game = ScummvmGame()
            game.name = config[section]["description"]
            game.slug = slugify(re.split(r" \(.*\)$", game.name)[0])
            game.appid = section
            game.game_id = section
            game.runner = "scummvm"
            game.lutris_slug = game.slug
            game.details = json.dumps({
                "path": config[section]["path"]
            })
            game.save()

    def generate_installer(self, game):
        details = json.loads(game["details"])
        return {
            "name": game["name"],
            "version": "ScummVM",
            "slug": game["slug"],
            "game_slug": slugify(game["lutris_slug"]),
            "runner": "scummvm",
            "script": {
                "game": {
                    "game_id": game["game_id"],
                    "path": details["path"],
                    "platform": "scummvm"
                }
            }
        }


class ScummvmGame(ServiceGame):
    service = "scummvm"
    runner = "scummvm"
