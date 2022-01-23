"""EA Origin service."""
import json
import os
import random
import urllib.parse
from gettext import gettext as _
from xml.etree import ElementTree

import requests
from gi.repository import Gio

from lutris import settings
from lutris.config import LutrisConfig, write_game_config
from lutris.database.games import add_game, get_game_by_field
from lutris.database.services import ServiceGameCollection
from lutris.game import Game
from lutris.installer import get_installers
from lutris.services.base import OnlineService
from lutris.services.service_game import ServiceGame
from lutris.services.service_media import ServiceMedia
from lutris.util.log import logger
from lutris.util.strings import slugify


class OriginLauncher:
    manifests_paths = "ProgramData/Origin/LocalContent"

    def __init__(self, prefix_path):
        self.prefix_path = prefix_path

    def iter_manifests(self):
        manifests_path = os.path.join(self.prefix_path, 'drive_c', self.manifests_paths)
        for game_folder in os.listdir(manifests_path):
            for manifest in os.listdir(os.path.join(manifests_path, game_folder)):
                if not manifest.endswith(".mfst"):
                    continue
                with open(os.path.join(manifests_path, game_folder, manifest), encoding="utf-8") as manifest_file:
                    manifest_content = manifest_file.read()
                parsed_url = urllib.parse.urlparse(manifest_content)
                parsed_data = dict(urllib.parse.parse_qsl(parsed_url.query))
                yield parsed_data


class OriginPackArtSmall(ServiceMedia):
    service = "origin"
    file_pattern = "%s.jpg"
    size = (63, 89)
    dest_path = os.path.join(settings.CACHE_DIR, "origin/pack-art-small")
    api_field = "packArtSmall"

    def get_media_url(self, details):
        return details["imageServer"] + details["i18n"][self.api_field]


class OriginPackArtMedium(OriginPackArtSmall):
    size = (142, 200)
    dest_path = os.path.join(settings.CACHE_DIR, "origin/pack-art-medium")
    api_field = "packArtMedium"


class OriginPackArtLarge(OriginPackArtSmall):
    size = (231, 326)
    dest_path = os.path.join(settings.CACHE_DIR, "origin/pack-art-large")
    api_field = "packArtLarge"


class OriginGame(ServiceGame):
    service = "origin"

    @classmethod
    def new_from_api(cls, offer):
        origin_game = OriginGame()
        origin_game.appid = offer["offerId"]
        origin_game.slug = offer["gameNameFacetKey"]
        origin_game.name = offer["i18n"]["displayName"]
        origin_game.details = json.dumps(offer)
        return origin_game


class OriginService(OnlineService):
    """Service class for EA Origin"""

    id = "origin"
    name = _("Origin")
    icon = "origin"
    client_installer = "origin"
    runner = "wine"
    online = True
    medias = {
        "packArtSmall": OriginPackArtSmall,
        "packArtMedium": OriginPackArtMedium,
        "packArtLarge": OriginPackArtLarge,
    }
    default_format = "packArtMedium"
    cache_path = os.path.join(settings.CACHE_DIR, "origin/cache/")
    cookies_path = os.path.join(settings.CACHE_DIR, "origin/cookies")
    token_path = os.path.join(settings.CACHE_DIR, "origin/auth_token")
    redirect_uri = "https://www.origin.com/views/login.html"
    login_url = (
        "https://accounts.ea.com/connect/auth"
        "?response_type=code&client_id=ORIGIN_SPA_ID&display=originXWeb/login"
        "&locale=en_US&release_type=prod"
        "&redirect_uri=%s"
    ) % redirect_uri
    is_loading = False

    def __init__(self):
        super().__init__()

        self.session = requests.session()
        self.access_token = self.load_access_token()

    @property
    def api_url(self):
        return "https://api%s.origin.com" % random.randint(1, 4)

    def is_connected(self):
        return bool(self.access_token)

    def login_callback(self, url):
        self.fetch_access_token()
        self.emit("service-login")

    def fetch_access_token(self):
        token_data = self.get_access_token()
        if not token_data:
            raise RuntimeError("Failed to get access token")
        with open(self.token_path, "w", encoding='utf-8') as token_file:
            token_file.write(json.dumps(token_data, indent=2))
        self.access_token = self.load_access_token()

    def load_access_token(self):
        if not os.path.exists(self.token_path):
            return ""
        with open(self.token_path) as token_file:
            token_data = json.load(token_file)
            return token_data.get("access_token", "")

    def get_access_token(self):
        """Request an access token from EA"""
        response = self.session.get(
            "https://accounts.ea.com/connect/auth",
            params={
                "client_id": "ORIGIN_JS_SDK",
                "response_type": "token",
                "redirect_uri": "nucleus:rest",
                "prompt": "none"
            },
            cookies=self.load_cookies()
        )
        response.raise_for_status()
        token_data = response.json()
        if "error" in token_data:
            raise RuntimeError(
                "%s (Error code: %s)" % (token_data["error"], token_data["error_number"])
            )
        return token_data

    def _request_identity(self):
        response = self.session.get(
            "https://gateway.ea.com/proxy/identity/pids/me",
            cookies=self.load_cookies(),
            headers=self.get_auth_headers()
        )
        return response.json()

    def get_identity(self):
        """Request the user info"""
        identity_data = self._request_identity()
        if identity_data.get('error') == "invalid_access_token":
            logger.warning("Refreshing Origin access token")
            self.fetch_access_token()
            identity_data = self._request_identity()

        if 'error' in identity_data:
            raise RuntimeError(identity_data["error"])
        try:
            user_id = identity_data["pid"]["pidId"]
        except KeyError:
            logger.error("Can't read user ID from %s", identity_data)
            raise

        persona_id_response = self.session.get(
            "{}/atom/users?userIds={}".format(self.api_url, user_id),
            headers=self.get_auth_headers()
        )
        content = persona_id_response.text
        origin_account_info = ElementTree.fromstring(content)
        persona_id = origin_account_info.find("user").find("personaId").text
        user_name = origin_account_info.find("user").find("EAID").text
        return str(user_id), str(persona_id), str(user_name)

    def load(self):
        if self.is_loading:
            logger.warning("Origin games are already loading")
            return
        self.is_loading = True
        user_id, _persona_id, _user_name = self.get_identity()
        games = self.get_library(user_id)
        origin_games = []
        for game in games:
            origin_game = OriginGame.new_from_api(game)
            origin_game.save()
            origin_games.append(origin_game)
        self.is_loading = False
        return origin_games

    def get_library(self, user_id):
        """Load Origin library"""
        offers = []
        for entitlement in self.get_entitlements(user_id):
            if entitlement["offerType"] != "basegame":
                continue
            offer_id = entitlement["offerId"]
            offer = self.get_offer(offer_id)
            offers.append(offer)
        return offers

    def get_offer(self, offer_id):
        """Load offer details from Origin"""
        url = "{}/ecommerce2/public/supercat/{}/{}".format(self.api_url, offer_id, "en_US")
        response = self.session.get(url, headers=self.get_auth_headers())
        return response.json()

    def get_entitlements(self, user_id):
        """Request the user's entitlements"""
        url = "%s/ecommerce2/consolidatedentitlements/%s?machine_hash=1" % (
            self.api_url,
            user_id
        )
        headers = self.get_auth_headers()
        headers["Accept"] = "application/vnd.origin.v3+json; x-cache/force-write"
        response = self.session.get(url, headers=headers)
        data = response.json()
        return data["entitlements"]

    def get_auth_headers(self):
        """Return headers needed to authenticate HTTP requests"""
        if not self.access_token:
            raise RuntimeError("User not authenticated to Origin")
        return {
            "Authorization": "Bearer %s" % self.access_token,
            "AuthToken": self.access_token,
            "X-AuthToken": self.access_token
        }

    def add_installed_games(self):
        origin_game = get_game_by_field("origin", "slug")
        if not origin_game:
            logger.error("Origin is not installed")
        origin_prefix = origin_game["directory"].split("drive_c")[0]
        if not os.path.exists(os.path.join(origin_prefix, "drive_c")):
            logger.error("Invalid install of Origin at %s", origin_prefix)
            return
        origin_launcher = OriginLauncher(origin_prefix)
        for manifest in origin_launcher.iter_manifests():
            self.install_from_origin(origin_game, manifest)
        logger.debug("All EGS games imported")

    def install_from_origin(self, origin_game, manifest):
        offer_id = manifest["id"].split("@")[0]
        logger.debug("Installing Origin game %s", offer_id)
        service_game = ServiceGameCollection.get_game("origin", offer_id)
        if not service_game:
            logger.error("Aborting install, %s is not present in the game library.", offer_id)
            return
        lutris_game_id = slugify(service_game["name"]) + "-" + self.id
        existing_game = get_game_by_field(lutris_game_id, "installer_slug")
        if existing_game:
            return
        game_config = LutrisConfig(game_config_id=origin_game["configpath"]).game_level
        game_config["game"]["args"] = get_launch_arguments(manifest["id"])
        configpath = write_game_config(lutris_game_id, game_config)
        game_id = add_game(
            name=service_game["name"],
            runner=origin_game["runner"],
            slug=slugify(service_game["name"]),
            directory=origin_game["directory"],
            installed=1,
            installer_slug=lutris_game_id,
            configpath=configpath,
            service=self.id,
            service_id=offer_id,
        )
        return game_id

    def generate_installer(self, db_game, origin_db_game):
        origin_game = Game(origin_db_game["id"])
        origin_exe = origin_game.config.game_config["exe"]
        if not os.path.isabs(origin_exe):
            origin_exe = os.path.join(origin_game.config.game_config["prefix"], origin_exe)
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
                    "args": get_launch_arguments(db_game["appid"]),
                },
                "installer": [
                    {"task": {
                        "name": "wineexec",
                        "executable": origin_exe,
                        "args": get_launch_arguments(db_game["appid"], "download"),
                        "prefix": origin_game.config.game_config["prefix"],
                        "description": (
                            "Origin will now open and install %s." % db_game["name"]
                        )
                    }}
                ]
            }
        }

    def install(self, db_game):
        origin_game = get_game_by_field(self.client_installer, "slug")
        application = Gio.Application.get_default()
        if not origin_game or not origin_game["installed"]:
            logger.warning("Installing the Origin client")
            installers = get_installers(game_slug=self.client_installer)
            application.show_installer_window(installers)
        else:
            application.show_installer_window(
                [self.generate_installer(db_game, origin_game)],
                service=self,
                appid=db_game["appid"]
            )


def get_launch_arguments(offer_id, action="launch"):
    if action == "launch":
        return "origin2://game/launch?offerIds=%s&autoDownload=1" % offer_id
    if action == "download":
        return "origin2://game/download?offerId=%s" % offer_id
