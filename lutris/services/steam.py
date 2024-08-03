"""Steam service"""

import json
import os
from collections import defaultdict
from gettext import gettext as _

from lutris import settings
from lutris.config import LutrisConfig, write_game_config
from lutris.database import sql
from lutris.database.games import add_game, get_game_by_field, get_games
from lutris.database.services import ServiceGameCollection
from lutris.game import Game
from lutris.installer.installer_file import InstallerFile
from lutris.services.base import BaseService
from lutris.services.lutris import sync_media
from lutris.services.service_game import ServiceGame
from lutris.services.service_media import ServiceMedia
from lutris.util.log import logger
from lutris.util.steam.appmanifest import AppManifest, get_appmanifests
from lutris.util.steam.config import get_active_steamid64, get_steam_library, get_steamapps_dirs
from lutris.util.strings import slugify


class SteamBanner(ServiceMedia):
    service = "steam"
    size = (184, 69)
    dest_path = os.path.join(settings.CACHE_DIR, "steam/banners")
    file_patterns = ["%s.jpg"]
    api_field = "appid"
    url_pattern = "http://cdn.akamai.steamstatic.com/steam/apps/%s/capsule_184x69.jpg"


class SteamCover(ServiceMedia):
    service = "steam"
    size = (200, 300)
    dest_path = os.path.join(settings.CACHE_DIR, "steam/covers")
    file_patterns = ["%s.jpg"]
    api_field = "appid"
    url_pattern = "http://cdn.steamstatic.com/steam/apps/%s/library_600x900.jpg"


class SteamBannerLarge(ServiceMedia):
    service = "steam"
    size = (460, 215)
    dest_path = os.path.join(settings.CACHE_DIR, "steam/header")
    file_patterns = ["%s.jpg"]
    api_field = "appid"
    url_pattern = "https://cdn.cloudflare.steamstatic.com/steam/apps/%s/header.jpg"


class SteamGame(ServiceGame):
    """ServiceGame for Steam games"""

    service = "steam"
    installer_slug = "steam"
    runner = "steam"

    @classmethod
    def new_from_steam_game(cls, steam_game):
        """Return a Steam game instance from an AppManifest"""
        game = cls()
        game.appid = steam_game["appid"]
        game.game_id = steam_game["appid"]
        game.name = steam_game["name"]
        game.slug = slugify(steam_game["name"])
        game.runner = cls.runner
        game.details = json.dumps(steam_game)
        return game


class SteamService(BaseService):
    id = "steam"
    name = _("Steam")
    icon = "steam-client"
    medias = {
        "banner": SteamBanner,
        "banner_large": SteamBannerLarge,
        "cover": SteamCover,
    }
    default_format = "banner"
    runner = "steam"
    excluded_appids = [
        "221410",  # Steam for Linux
        "228980",  # Steamworks Common Redistributables
        "1070560",  # Steam Linux Runtime
    ]
    game_class = SteamGame

    def load(self):
        """Return importable Steam games"""
        steamid = get_active_steamid64()
        if not steamid:
            logger.error("Unable to find SteamID from Steam config")
            return
        steam_games = get_steam_library(steamid)
        if not steam_games:
            raise RuntimeError(_("Failed to load games. Check that your profile is set to public during the sync."))
        for steam_game in steam_games:
            if steam_game["appid"] in self.excluded_appids:
                continue
            game = self.game_class.new_from_steam_game(steam_game)
            game.save()
        self.match_games()
        return steam_games

    def match_game(self, service_game, lutris_game):
        super().match_game(service_game, lutris_game)

        if service_game:
            # Copy playtimes from Steam's data
            for game in get_games(filters={"service": self.id, "service_id": service_game["appid"]}):
                steam_game_playtime = json.loads(service_game["details"]).get("playtime_forever")
                playtime = steam_game_playtime / 60
                sql.db_update(settings.DB_PATH, "games", {"playtime": playtime}, conditions={"id": game["id"]})

    def get_installer_files(self, installer, _installer_file_id, _selected_extras):
        steam_uri = "$STEAM:%s:."
        appid = str(installer.script["game"]["appid"])
        file = InstallerFile(installer.game_slug, "steam_game", {"url": steam_uri % appid, "filename": appid})
        return [file], []

    def install_from_steam(self, manifest):
        """Create a new Lutris game based on an existing Steam install"""
        if not manifest.is_installed():
            return
        appid = manifest.steamid
        if appid in self.excluded_appids:
            return
        try:
            service_game = ServiceGameCollection.get_game(self.id, appid)
            if not service_game:
                return
            lutris_game_id = "%s-%s" % (self.id, appid)
            existing_game = get_game_by_field(lutris_game_id, "installer_slug")
            if existing_game:
                return
            game_config = LutrisConfig().game_level
            game_config["game"]["appid"] = appid
            configpath = write_game_config(lutris_game_id, game_config)
            slug = self.get_installed_slug(service_game)
            add_game(
                name=service_game["name"],
                runner="steam",
                slug=slug,
                installed=1,
                installer_slug=lutris_game_id,
                configpath=configpath,
                platform="Linux",
                service=self.id,
                service_id=appid,
            )
            return slug
        except Exception as e:
            logger.error("Failed to install from Steam: %s", str(e))
            return None

    @property
    def steamapps_paths(self):
        return get_steamapps_dirs()

    def add_installed_games(self):
        """Syncs installed Steam games with Lutris"""
        stats = {"installed": 0, "removed": 0, "deduped": 0, "paths": []}
        installed_slugs = []
        installed_appids = []

        for steamapps_path in self.steamapps_paths:
            for appmanifest_file in get_appmanifests(steamapps_path):
                if steamapps_path not in stats["paths"]:
                    stats["paths"].append(steamapps_path)
                app_manifest_path = os.path.join(steamapps_path, appmanifest_file)
                try:
                    app_manifest = AppManifest(app_manifest_path)
                    installed_appids.append(app_manifest.steamid)
                    slug = self.install_from_steam(app_manifest)
                    if slug:
                        installed_slugs.append(slug)
                    stats["installed"] += 1
                except Exception as e:
                    logger.error("Failed to process app manifest %s: %s", app_manifest_path, str(e))

        if stats["paths"]:
            logger.debug("%s Steam games detected and installed", stats["installed"])
            logger.debug("Games found in: %s", ", ".join(stats["paths"]))
        else:
            logger.debug("No Steam folder found with games")

        db_games = get_games(filters={"runner": "steam"})
        for db_game in db_games:
            steam_game = Game(db_game["id"])
            if steam_game.config is None:
                logger.warning("Steam game %s has no config", db_game["id"])
                continue
            try:
                appid = steam_game.config.game_level["game"]["appid"]
            except KeyError:
                logger.warning("Steam game %s has no AppID", db_game["id"])
                continue
            if appid not in installed_appids:
                try:
                    steam_game.uninstall()
                    stats["removed"] += 1
                except Exception as e:
                    logger.error("Failed to uninstall game %s: %s", appid, str(e))

        logger.debug("%s Steam games removed", stats["removed"])

        db_appids = defaultdict(list)
        db_games = get_games(filters={"service": "steam"})
        for db_game in db_games:
            db_appids[db_game["service_id"]].append(db_game["id"])

        for appid, game_ids in db_appids.items():
            if len(game_ids) == 1:
                continue
            for game_id in game_ids:
                steam_game = Game(game_id)
                if steam_game.config is None:
                    logger.warning("Steam game %s has no config for deduplication", game_id)
                    continue
                if not steam_game.playtime:
                    try:
                        # Unsafe to emit a signal from a worker thread!
                        steam_game.uninstall()
                        steam_game.delete()
                        stats["deduped"] += 1
                    except Exception as e:
                        logger.error("Failed to deduplicate game %s: %s", game_id, str(e))

        sync_media(installed_slugs)
        logger.debug("%s Steam games deduplicated", stats["deduped"])

    def generate_installer(self, db_game):
        """Generate a basic Steam installer"""
        return {
            "name": db_game["name"],
            "version": self.name,
            "slug": slugify(db_game["name"]) + "-" + self.id,
            "game_slug": self.get_installed_slug(db_game),
            "runner": self.get_installed_runner_name(db_game),
            "appid": db_game["appid"],
            "script": {"game": {"appid": db_game["appid"]}},
        }

    def get_installed_runner_name(self, db_game):
        return self.runner

    def install(self, db_game):
        appid = db_game["appid"]
        db_games = get_games(filters={"service_id": appid, "installed": "1", "service": self.id})
        existing_game = self.match_existing_game(db_games, appid)
        if existing_game:
            logger.debug("Found steam game: %s", existing_game)
            game = Game(existing_game.id)
            game.save()
            return
        self.install_from_api(db_game, appid)
