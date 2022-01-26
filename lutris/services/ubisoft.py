"""Ubisoft Connect service"""
import json
import os
import shutil
from gettext import gettext as _
from urllib.parse import unquote

from lutris import settings
from lutris.database.games import get_game_by_field
from lutris.game import Game
from lutris.services.base import OnlineService
from lutris.services.service_game import ServiceGame
from lutris.services.service_media import ServiceMedia
from lutris.util.log import logger
from lutris.util.strings import slugify
from lutris.util.ubisoft import consts
from lutris.util.ubisoft.client import UbisoftConnectClient
from lutris.util.ubisoft.parser import UbisoftParser


class UbisoftCover(ServiceMedia):
    """Ubisoft connect cover art"""
    service = "ubisoft"
    size = (160, 186)
    dest_path = os.path.join(settings.CACHE_DIR, "ubisoft/covers")
    file_pattern = "%s.jpg"
    api_field = "id"
    url_pattern = "https://ubiservices.cdn.ubi.com/%s/spaceCardAsset/boxArt_mobile.jpg?imwidth=320"

    def get_media_url(self, details):
        if self.api_field in details:
            return super().get_media_url(details)
        return details["thumbImage"]

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
            base_dir,
            "drive_c/Program Files (x86)/Ubisoft/Ubisoft Game Launcher/cache/assets",
            url
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
    cookies_path = os.path.join(settings.CACHE_DIR, "ubisoft/.auth")
    token_path = os.path.join(settings.CACHE_DIR, "ubisoft/.token")
    cache_path = os.path.join(settings.CACHE_DIR, "ubisoft/library/")
    login_url = consts.LOGIN_URL
    redirect_uri = "https://connect.ubisoft.com/change_domain/"
    scripts = {
        "https://connect.ubisoft.com/ready": (
            'window.location.replace("https://connect.ubisoft.com/change_domain/");'
        ),
        "https://connect.ubisoft.com/change_domain/": (
            'window.location.replace(localStorage.getItem("PRODloginData") +","+ '
            'localStorage.getItem("PRODrememberMe") +"," + localStorage.getItem("PRODlastProfile"));'
        )
    }
    medias = {
        "cover": UbisoftCover,
    }
    default_format = "cover"
    is_loading = False

    def __init__(self):
        super().__init__()
        self.client = UbisoftConnectClient(self)

    def auth_lost(self):
        self.emit("service-logout")

    def login_callback(self, credentials):
        """Called after the user has logged in successfully"""
        url = credentials[len("https://connect.ubisoft.com/change_domain/"):]
        unquoted_url = unquote(url)
        storage_jsons = json.loads("[" + unquoted_url + "]")
        user_data = self.client.authorise_with_local_storage(storage_jsons)
        self.client.set_auth_lost_callback(self.auth_lost)
        self.emit("service-login")
        return (user_data['userId'], user_data['username'])

    def is_connected(self):
        return self.is_authenticated()

    def get_configurations(self):
        ubi_game = get_game_by_field("ubisoft-connect", "slug")
        if not ubi_game:
            return
        base_dir = ubi_game["directory"]
        configurations_path = os.path.join(
            base_dir,
            "drive_c/Program Files (x86)/Ubisoft/Ubisoft Game Launcher/"
            "cache/configuration/configurations"
        )
        with open(configurations_path, "rb") as config_file:
            content = config_file.read()
        return content

    def load(self):
        self.is_loading = True
        self.client.authorise_with_stored_credentials(self.load_credentials())
        response = self.client.get_club_titles()
        games = response['data']['viewer']['ownedGames'].get('nodes', [])
        ubi_games = []
        for game in games:
            ubi_game = UbisoftGame.new_from_api(game)
            ubi_game.save()
            ubi_games.append(ubi_game)
        configuration_data = self.get_configurations()
        config_parser = UbisoftParser()
        games = []
        for game in config_parser.parse_games(configuration_data):
            ubi_game = UbisoftGame.new_from_api(game)
            ubi_game.save()
            ubi_games.append(ubi_game)
        self.is_loading = False
        return ubi_games

    def store_credentials(self, credentials):
        with open(self.token_path, "w", encoding='utf-8') as auth_file:
            auth_file.write(json.dumps(credentials, indent=2))

    def load_credentials(self):
        with open(self.token_path) as auth_file:
            credentials = json.load(auth_file)
        return credentials

    def generate_installer(self, db_game):
        ubi_db_game = get_game_by_field("ubisoft-connect", "slug")
        ubisoft_connect = Game(ubi_db_game["id"])
        uc_exe = ubisoft_connect.config.game_config["exe"]
        if not os.path.isabs(uc_exe):
            uc_exe = os.path.join(ubisoft_connect.config.game_config["prefix"], uc_exe)
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
                    "args": f"uplay://launch/{db_game['appid']}",
                },
                "installer": [
                    {"task": {
                        "name": "wineexec",
                        "executable": uc_exe,
                        "args": f"uplay://install/{db_game['appid']}",
                        "prefix": ubisoft_connect.config.game_config["prefix"],
                        "description": (
                            "Ubisoft will now open and install %s." % db_game["name"]
                        )
                    }}
                ]
            }
        }
