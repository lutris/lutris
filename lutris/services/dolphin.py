import json
import os
from gettext import gettext as _
from typing import List

from PIL import Image

from lutris import settings
from lutris.runners.dolphin import PLATFORMS
from lutris.services.base import BaseService
from lutris.services.service_game import ServiceGame
from lutris.services.service_media import ServiceMedia
from lutris.util import system
from lutris.util.dolphin.cache_reader import DOLPHIN_GAME_CACHE_FILE, DolphinCacheReader
from lutris.util.strings import slugify


class DolphinBanner(ServiceMedia):
    service = "dolphin"
    source = "local"
    size = (96, 32)
    file_patterns = ["%s.png"]
    dest_path = os.path.join(settings.CACHE_DIR, "dolphin/banners/small")


class DolphinService(BaseService):
    id = "dolphin"
    icon = "dolphin"
    name = _("Dolphin")
    runner = "dolphin"
    local = True
    medias = {"icon": DolphinBanner}

    def load(self):
        if not system.path_exists(DOLPHIN_GAME_CACHE_FILE):
            return
        cache_reader = DolphinCacheReader()
        dolphin_games = [DolphinGame.new_from_cache(game) for game in cache_reader.get_games()]
        for game in dolphin_games:
            game.save()
        return dolphin_games

    def generate_installer(self, db_game):
        details = json.loads(db_game["details"])
        return {
            "name": db_game["name"],
            "version": "Dolphin",
            "slug": db_game["slug"],
            "game_slug": self.get_installed_slug(db_game),
            "runner": self.get_installed_runner_name(db_game),
            "script": {
                "game": {"main_file": details["path"], "platform": details["platform"]},
            },
        }

    def get_installed_runner_name(self, db_game):
        return self.runner

    def get_game_directory(self, installer):
        """Pull install location from installer"""
        return os.path.dirname(installer["script"]["game"]["main_file"])

    def get_game_platforms(self, db_game: dict) -> List[str]:
        details_json = db_game.get("details")
        if details_json:
            details = json.loads(details_json)
            if details and details.get("platform"):
                platform_value = details["platform"]
                if platform_value.isdigit():
                    platform_number = int(details["platform"])
                    if 0 <= platform_number < len(PLATFORMS):
                        platform = PLATFORMS[platform_number]
                        return [platform]

                return [platform_value]
        return []


class DolphinGame(ServiceGame):
    """Game for the Dolphin emulator"""

    service = "dolphin"
    runner = "dolphin"
    installer_slug = "dolphin"

    @classmethod
    def new_from_cache(cls, cache_entry):
        """Create a service game from an entry from the Dolphin cache"""
        name = cache_entry["internal_name"] or os.path.splitext(cache_entry["file_name"])[0]
        service_game = cls()
        service_game.name = name
        service_game.appid = str(cache_entry["game_id"])
        service_game.slug = slugify(name)
        service_game.icon = service_game.get_banner(cache_entry)

        service_game.details = json.dumps({"path": cache_entry["file_path"], "platform": cache_entry["platform"][:-1]})
        return service_game

    @staticmethod
    def get_game_name(cache_entry):
        names = cache_entry["long_names"]
        name_index = 1 if len(names.keys()) > 1 else 0
        return str(names[list(names.keys())[name_index]])

    def get_banner(self, cache_entry):
        banner = DolphinBanner()
        banner_path = banner.get_possible_media_paths(self.appid)[0].path  # Dolphin only supports one media type

        if os.path.exists(banner_path):
            return banner_path

        (width, height), data = cache_entry["volume_banner"]
        if data:
            img = Image.frombytes("RGB", (width, height), data, "raw", ("BGRX"))
            # 96x32 is a bit small, maybe 2x scale?
            # img.resize((width * 2, height * 2))
            img.save(banner_path)
            return banner_path

        return ""
