"""Ubisoft Connect service"""

import json
import os
import shutil
from gettext import gettext as _
from urllib.parse import unquote

from gi.repository import Gio

from lutris import settings
from lutris.config import LutrisConfig, write_game_config
from lutris.database.games import add_game, get_game_by_field, update_existing
from lutris.database.services import ServiceGameCollection
from lutris.game import Game
from lutris.services.base import SERVICE_LOGIN, SERVICE_LOGOUT, OnlineService
from lutris.services.lutris import sync_media
from lutris.services.service_game import ServiceGame
from lutris.services.service_media import ServiceMedia
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
from lutris.util.strings import slugify
from lutris.util.ubisoft import consts
from lutris.util.ubisoft.client import UbisoftConnectClient
from lutris.util.ubisoft.helpers import get_ubisoft_registry
from lutris.util.ubisoft.parser import UbisoftParser
from lutris.util.wine.prefix import WinePrefixManager


class UbisoftCover(ServiceMedia):
    """Ubisoft connect cover art"""

    service = "ubisoft"
    size = (160, 186)
    dest_path = os.path.join(settings.CACHE_DIR, "ubisoft/covers")
    file_patterns = ["%s.jpg"]
    api_field = "thumbImage"
    url_pattern = "https://static3.cdn.ubi.com/orbit/uplay_launcher_3_0/assets/%s"

    def download(self, slug, url):
        if url.startswith("http"):
            return super().download(slug, url)
        if not url.endswith(".jpg"):
            return
        ubi_game = get_game_by_field("ubisoft-connect", "slug")
        if not ubi_game:
            return
        base_dir = ubi_game["directory"]
        asset_file = os.path.join(
            base_dir, "drive_c/Program Files (x86)/Ubisoft/Ubisoft Game Launcher/cache/assets", url
        )
        cache_path = os.path.join(self.dest_path, self.get_filename(slug))
        if os.path.exists(asset_file):
            shutil.copy(asset_file, cache_path)
        else:
            logger.warning("No thumbnail in %s", asset_file)


class UbisoftGame(ServiceGame):
    """Service game for games from Ubisoft connect"""

    service = "ubisoft"

    @classmethod
    def new_from_api(cls, payload):
        """Convert an Ubisoft game to a service game"""
        service_game = cls()
        service_game.appid = payload["spaceId"] or payload["installId"]
        service_game.slug = slugify(payload["name"])
        service_game.name = payload["name"]
        service_game.details = json.dumps(payload)
        return service_game


class UbisoftConnectService(OnlineService):
    """Service class for Ubisoft Connect"""

    id = "ubisoft"
    name = _("Ubisoft Connect")
    icon = "ubisoft"
    runner = "wine"
    client_installer = "ubisoft-connect"
    browser_size = (460, 690)
    login_window_width = 460
    login_window_height = 690
    cookies_path = os.path.join(settings.CACHE_DIR, "ubisoft/.auth")
    token_path = os.path.join(settings.CACHE_DIR, "ubisoft/.token")
    cache_path = os.path.join(settings.CACHE_DIR, "ubisoft/library/")
    login_url = consts.LOGIN_URL
    redirect_uris = ["https://connect.ubisoft.com/change_domain/"]
    scripts = {
        "https://connect.ubisoft.com/ready": ('window.location.replace("https://connect.ubisoft.com/change_domain/");'),
        "https://connect.ubisoft.com/change_domain/": (
            'window.location.replace(localStorage.getItem("PRODloginData") +","+ '
            'localStorage.getItem("PRODrememberMe") +"," + localStorage.getItem("PRODlastProfile"));'
        ),
    }
    medias = {
        "cover": UbisoftCover,
    }
    default_format = "cover"

    def __init__(self):
        super().__init__()
        self.client = UbisoftConnectClient(self)

    def auth_lost(self):
        SERVICE_LOGOUT.fire(self)

    def login_callback(self, credentials):
        """Called after the user has logged in successfully"""
        logger.info("Login to Ubisoft Connect sucessful")
        url = credentials[len("https://connect.ubisoft.com/change_domain/") :]
        unquoted_url = unquote(url)
        storage_jsons = json.loads("[" + unquoted_url + "]")
        user_data = self.client.authorise_with_local_storage(storage_jsons)
        logger.debug("Ubisoft user data: %s", user_data)
        self.client.set_auth_lost_callback(self.auth_lost)
        SERVICE_LOGIN.fire(self)
        return (user_data["userId"], user_data["username"])

    def is_connected(self):
        res = self.is_authenticated()
        logger.debug("Ubisoft Connect is connected: %s", res)
        return res

    def get_configurations(self):
        ubi_game = get_game_by_field("ubisoft-connect", "slug")
        if not ubi_game:
            return
        base_dir = ubi_game["directory"]
        configurations_path = os.path.join(
            base_dir, "drive_c/Program Files (x86)/Ubisoft/Ubisoft Game Launcher/" "cache/configuration/configurations"
        )
        if not os.path.exists(configurations_path):
            return
        with open(configurations_path, "rb") as config_file:
            content = config_file.read()
        return content

    def load(self):
        try:
            self.client.authorise_with_stored_credentials(self.load_credentials())
        except RuntimeError as ex:
            logger.error("Failed to authorize with API: %s. Re-login required." % ex)
            AsyncCall(self.logout, self.login)
            return
        response = self.client.get_club_titles()
        games = response["data"]["viewer"]["ownedGames"].get("nodes", [])
        ubi_games = []
        for game in games:
            if "ownedPlatformGroups" in game:
                is_pc = False
                for platform_group in game["ownedPlatformGroups"]:
                    for platform in platform_group:
                        if platform["type"] == "PC":
                            is_pc = True
                if not is_pc:
                    continue
            ubi_game = UbisoftGame.new_from_api(game)
            ubi_game.save()
            ubi_games.append(ubi_game)
        configuration_data = self.get_configurations()
        config_parser = UbisoftParser()
        for game in config_parser.parse_games(configuration_data):
            ubi_game = UbisoftGame.new_from_api(game)
            ubi_game.save()
            ubi_games.append(ubi_game)
        return ubi_games

    @property
    def credential_files(self):
        """Return a list of all files used for authentication"""
        return [self.token_path]

    def store_credentials(self, credentials):
        if not os.path.exists(os.path.dirname(self.token_path)):
            logger.debug("Creating Ubisoft credentials path: %s", self.token_path)
            os.mkdir(os.path.dirname(self.token_path))

        logger.debug("Writing Ubisoft credentials to %s", self.token_path)
        with open(self.token_path, "w", encoding="utf-8") as auth_file:
            auth_file.write(json.dumps(credentials, indent=2))

    def load_credentials(self):
        logger.debug("Loading credentials from %s", self.token_path)
        with open(self.token_path, encoding="utf-8") as auth_file:
            credentials = json.load(auth_file)
        return credentials

    def install_from_ubisoft(self, ubisoft_connect, game):
        app_name = game["name"]

        lutris_game_id = slugify(game["name"]) + "-" + self.id
        existing_game = get_game_by_field(lutris_game_id, "installer_slug")
        if existing_game and existing_game["installed"] == 1:
            logger.debug("Ubisoft Connect game %s installed in Lutris", app_name)
            return
        logger.debug("Installing Ubisoft Connect game %s", app_name)
        game_config = LutrisConfig(game_config_id=ubisoft_connect["configpath"]).game_level
        details = json.loads(game["details"])
        launch_id = details.get("launchId") or details.get("installId") or details.get("spaceId")
        game_config["game"]["args"] = f"uplay://launch/{launch_id}"
        configpath = write_game_config(lutris_game_id, game_config)
        slug = self.get_installed_slug(game)
        if existing_game:
            update_existing(
                id=existing_game["id"],
                name=game["name"],
                runner=self.runner,
                slug=slug,
                directory=ubisoft_connect["directory"],
                installed=1,
                installer_slug=lutris_game_id,
                configpath=configpath,
                service=self.id,
                service_id=game["appid"],
            )
            return existing_game["id"]
        add_game(
            name=game["name"],
            runner=self.runner,
            slug=slug,
            directory=ubisoft_connect["directory"],
            installed=1,
            installer_slug=lutris_game_id,
            configpath=configpath,
            service=self.id,
            service_id=game["appid"],
        )
        return slug

    def add_installed_games(self):
        ubisoft_connect = get_game_by_field(self.client_installer, "slug")
        if not ubisoft_connect:
            logger.warning("Ubisoft Connect not installed")
            return
        prefix_path = ubisoft_connect["directory"].split("drive_c")[0]
        prefix = WinePrefixManager(prefix_path)
        installed_slugs = []
        for game in ServiceGameCollection.get_for_service(self.id):
            details = json.loads(game["details"])
            install_path = get_ubisoft_registry(prefix, details.get("registryPath"))
            exe = get_ubisoft_registry(prefix, details.get("exe"))
            if install_path and exe:
                slug = self.install_from_ubisoft(ubisoft_connect, game)
                if slug:
                    installed_slugs.append(slug)
        logger.debug("Syncing media for %s games", len(installed_slugs))
        sync_media(installed_slugs)

    def generate_installer(self, db_game, ubi_db_game):
        ubisoft_connect = Game(ubi_db_game["id"])
        uc_exe = ubisoft_connect.config.game_config["exe"]
        if not os.path.isabs(uc_exe):
            uc_exe = os.path.join(ubisoft_connect.config.game_config["prefix"], uc_exe)
        details = json.loads(db_game["details"])
        launch_id = details.get("launchId") or details.get("installId") or details.get("spaceId")
        install_id = details.get("installId") or details.get("launchId") or details.get("spaceId")
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
                    "args": f"uplay://launch/{launch_id}",
                },
                "installer": [
                    {
                        "task": {
                            "name": "wineexec",
                            "executable": uc_exe,
                            "args": f"uplay://install/{install_id}",
                            "prefix": ubisoft_connect.config.game_config["prefix"],
                            "description": (
                                "Ubisoft will now open and install %s. "
                                "Close Ubisoft Connect to complete the install process."
                            )
                            % db_game["name"],
                        }
                    }
                ],
            },
        }

    def get_installed_runner_name(self, db_game):
        return self.runner

    def install(self, db_game):
        """Install a game or Ubisoft Connect if not already installed"""
        ubisoft_connect = get_game_by_field(self.client_installer, "slug")
        application = Gio.Application.get_default()
        if not ubisoft_connect or not ubisoft_connect["installed"]:
            logger.warning("Ubisoft Connect (%s) not installed", self.client_installer)
            application.show_lutris_installer_window(game_slug=self.client_installer)
        else:
            application.show_installer_window(
                [self.generate_installer(db_game, ubisoft_connect)], service=self, appid=db_game["appid"]
            )
