"""EA App service."""

import json
import os
import ssl
from gettext import gettext as _
from typing import Any, Dict, Optional
from xml.etree import ElementTree

import requests
import urllib3
from gi.repository import Gio

from lutris import settings
from lutris.config import LutrisConfig, write_game_config
from lutris.database.games import add_game, get_game_by_field
from lutris.database.services import ServiceGameCollection
from lutris.game import Game
from lutris.services.base import SERVICE_LOGIN, OnlineService
from lutris.services.lutris import sync_media
from lutris.services.service_game import ServiceGame
from lutris.services.service_media import ServiceMedia
from lutris.util.log import logger
from lutris.util.strings import slugify

SSL_OP_ALLOW_UNSAFE_LEGACY_RENEGOTIATION = 1 << 18


class EAAppGames:
    ea_games_location = "Program Files/EA Games"

    def __init__(self, prefix_path):
        self.prefix_path = prefix_path
        self.ea_games_path = os.path.join(self.prefix_path, "drive_c", self.ea_games_location)

    def iter_installed_games(self):
        if not os.path.exists(self.ea_games_path):
            return
        for game_folder in os.listdir(self.ea_games_path):
            yield game_folder

    def get_installed_games_content_ids(self):
        installed_game_ids = []
        for game_folder in self.iter_installed_games():
            installer_data_path = os.path.join(self.ea_games_path, game_folder, "__Installer/installerdata.xml")
            if not os.path.exists(installer_data_path):
                logger.warning("No installerdata.xml for %s", game_folder)
                continue
            tree = ElementTree.parse(installer_data_path)
            nodes = tree.find("contentIDs").findall("contentID")
            if not nodes:
                logger.warning("Content ID not found for %s", game_folder)
                continue
            installed_game_ids.append([node.text for node in nodes])
        return installed_game_ids


class EAAppMedia(ServiceMedia):
    service = "ea_app"
    file_patterns = ["%s.jpg"]
    name = NotImplemented

    @property
    def dest_path(self):
        return os.path.join(settings.CACHE_DIR, self.service, self.name)

    def get_media_url(self, details: Dict[str, Any]) -> Optional[str]:
        image = details["baseItem"][self.name]["largestImage"]
        return image.get("path", None) if image is not None else None


class EAAppKeyArt(EAAppMedia):
    name = "keyArt"
    size = (192, 108)


class EAAppPackArt(EAAppMedia):
    name = "packArt"
    size = (135, 240)


class EAAppPrimaryLogo(EAAppMedia):
    name = "primaryLogo"
    size = (200, 100)


class EAAppGame(ServiceGame):
    service = "ea_app"

    @classmethod
    def new_from_api(cls, game):
        ea_game = EAAppGame()
        ea_game.appid = game["contentId"]
        ea_game.slug = game["gameSlug"]
        ea_game.name = game["baseItem"]["title"]
        ea_game.details = json.dumps(game)
        return ea_game


class LegacyRenegotiationHTTPAdapter(requests.adapters.HTTPAdapter):
    """Allow insecure SSL/TLS protocol renegotiation in an HTTP request.

    By default, OpenSSL v3 expects that servers support RFC 5746. Unfortunately,
    accounts.ea.com does not support this TLS extension (from 2010!), causing
    OpenSSL to refuse to connect. This `requests` HTTP Adapter configures
    OpenSSL to allow "unsafe legacy renegotiation", allowing EA Origin to
    connect. This is only intended as a temporary workaround, and should be
    removed as soon as accounts.ea.com is updated to support RFC 5746.

    Using this adapter will reduce the security of the connection. However, the
    impact should be relatively minimal this is only used to connect to EA
    services. See CVE-2009-3555 for more details.

    See #4235 for more information.
    """

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        """Override the default PoolManager to allow insecure renegotiation."""
        # Based off of the default function from `requests`.
        self._pool_connections = connections
        self._pool_maxsize = maxsize
        self._pool_block = block

        ssl_context = ssl.create_default_context()
        ssl_context.options |= SSL_OP_ALLOW_UNSAFE_LEGACY_RENEGOTIATION

        self.poolmanager = urllib3.PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            strict=True,
            ssl_context=ssl_context,
            **pool_kwargs,
        )


class EAAppService(OnlineService):
    """Service class for EA App"""

    id = "ea_app"
    name = _("EA App")
    icon = "ea_app"
    client_installer = "ea-app"
    login_window_width = 460
    login_window_height = 760
    runner = "wine"
    online = True
    medias = {
        "keyArt": EAAppKeyArt,
        "packArt": EAAppPackArt,
        "primaryLogo": EAAppPrimaryLogo,
    }
    default_format = "keyArt"
    cache_path = os.path.join(settings.CACHE_DIR, "ea_app/cache/")
    cookies_path = os.path.join(settings.CACHE_DIR, "ea_app/cookies")
    token_path = os.path.join(settings.CACHE_DIR, "ea_app/auth_token")
    origin_redirect_uri = "https://www.origin.com/views/login.html"
    login_url = "https://www.ea.com/login"
    redirect_uris = ["https://www.ea.com/"]
    origin_login_url = (
        "https://accounts.ea.com/connect/auth"
        "?response_type=code&client_id=ORIGIN_SPA_ID&display=originXWeb/login"
        "&locale=en_US&release_type=prod"
        "&redirect_uri=%s"
    ) % origin_redirect_uri
    api_url = "https://service-aggregation-layer.juno.ea.com/graphql"
    login_user_agent = settings.DEFAULT_USER_AGENT + " QtWebEngine/5.8.0"

    def __init__(self):
        super().__init__()

        self.session = requests.session()
        self.session.mount("https://", LegacyRenegotiationHTTPAdapter())
        self.access_token = self.load_access_token()

    @property
    def api_headers(self):
        headers = {"User-Agent": self.login_user_agent}
        headers.update(self.get_auth_headers())
        return headers

    def is_connected(self):
        return bool(self.access_token)

    def login_callback(self, url):
        self.fetch_access_token()
        SERVICE_LOGIN.fire(self)

    def fetch_access_token(self):
        token_data = self.get_access_token()
        if not token_data:
            raise RuntimeError("Failed to get access token")
        with open(self.token_path, "w", encoding="utf-8") as token_file:
            token_file.write(json.dumps(token_data, indent=2))
        self.access_token = self.load_access_token()

    def load_access_token(self):
        if not os.path.exists(self.token_path):
            return ""
        with open(self.token_path, encoding="utf-8") as token_file:
            token_data = json.load(token_file)
            return token_data.get("access_token", "")

    def fetch_api(self, query, params: dict = None):
        result = self.session.post(
            self.api_url, headers=self.api_headers, json={"query": query, "variables": params or {}}
        ).json()

        if "errors" in result:
            raise RuntimeError("Errors occurred while running an EA api query.", result["errors"])

        return result

    def get_access_token(self):
        """Request an access token from EA"""
        response = self.session.get(
            "https://accounts.ea.com/connect/auth",
            params={
                "client_id": "ORIGIN_JS_SDK",
                "response_type": "token",
                "redirect_uri": "nucleus:rest",
                "prompt": "none",
            },
            cookies=self.load_cookies(),
        )
        response.raise_for_status()
        token_data = response.json()
        return token_data

    def _request_identity(self):
        response = self.session.get(
            "https://gateway.ea.com/proxy/identity/pids/me",
            cookies=self.load_cookies(),
            headers=self.get_auth_headers(),
        )
        return response.json()

    def get_identity(self):
        """Request the user info"""
        identity_data = self._request_identity()
        if identity_data.get("error") == "invalid_access_token":
            logger.warning("Refreshing EA access token")
            self.fetch_access_token()
            identity_data = self._request_identity()
        elif identity_data.get("error"):
            raise RuntimeError("%s (Error code: %s)" % (identity_data["error"], identity_data["error_number"]))

        if "error" in identity_data:
            raise RuntimeError(identity_data["error"])

        player = self.fetch_api("query{me{player{pd psd displayName}}}")["data"]["me"]["player"]
        user_id = player["pd"]
        persona_id = player["psd"]
        user_name = player["displayName"]
        return str(user_id), str(persona_id), str(user_name)

    def load(self):
        user_id, _persona_id, _user_name = self.get_identity()
        games = self.get_library(user_id)
        logger.info("Retrieved %s games from EA library", len(games))
        ea_games = []
        for game in games:
            ea_game = EAAppGame.new_from_api(game)
            ea_game.save()
            ea_games.append(ea_game)
        return ea_games

    def get_library(self, user_id):
        """Load EA library"""
        chunk_size = 100
        games = []
        entitlements = list(
            filter(
                lambda e: e["product"] is not None and e["product"]["baseItem"]["gameType"] == "BASE_GAME",
                self.get_entitlements(user_id),
            )
        )
        for chunk in [entitlements[i : i + chunk_size] for i in range(0, len(entitlements), chunk_size)]:
            games += self.get_games([e["originOfferId"] for e in chunk])
        return games

    def get_games(self, offer_ids):
        """Load game details from EA"""
        result = self.fetch_api(
            """query getOffers($offerIds: [String!]!) {
                legacyOffers(offerIds: $offerIds, locale: "DEFAULT") {
                    offerId: id
                    contentId
                }
                gameProducts(offerIds: $offerIds, locale: "DEFAULT") {
                    items {
                        id
                        originOfferId
                        gameSlug
                        baseItem {
                            keyArt {
                                largestImage { path }
                            }
                            packArt {
                                largestImage { path }
                            }
                            primaryLogo {
                                largestImage { path }
                            }
                            title
                        }
                    }
                }
            }
            """,
            params={"offerIds": offer_ids},
        )

        games = []
        legacy_offers = result["data"].get("legacyOffers")
        game_products = (result["data"].get("gameProducts") or {}).get("items", [])
        by_offer = {p.get("originOfferId"): p for p in game_products if isinstance(p, dict) and p.get("originOfferId")}
        by_product_id = {p.get("id"): p for p in game_products if isinstance(p, dict) and p.get("id")}

        for legacy_offer in legacy_offers:
            if not isinstance(legacy_offer, dict):
                continue
            offer_id = legacy_offer["offerId"]
            content_id = legacy_offer["contentId"]
            if not offer_id:
                continue
            product = (
                by_offer.get(offer_id)
                or (content_id and by_product_id.get(content_id))
                or by_product_id.get(offer_id)
                or {}
            )
            # Certain games will have identification data but without any product information.
            # Skip those.
            if not product:
                continue
            game = {"contentId": content_id}
            game.update(product)
            games.append(game)
        return games

    def get_entitlements(self, user_id):
        """Request the user's entitlements"""
        games = []
        variables = {"limit": 100}
        while True:
            result = self.fetch_api(
                """query getEntitlements($limit: Int, $next: String) {
                    me {
                        ownedGameProducts(
                            locale: "DEFAULT"
                            entitlementEnabled: true
                            storefronts: [EA]
                            type: [DIGITAL_FULL_GAME, PACKAGED_FULL_GAME]
                            platforms: [PC]
                            paging: {
                                limit: $limit,
                                next: $next
                            }
                        ) {
                            next,
                            items {
                                originOfferId
                                product {
                                    baseItem {
                                        gameType
                                    }
                                }
                            }
                        }
                    }
                }""",
                params=variables,
            )

            products = result["data"]["me"]["ownedGameProducts"]
            variables["next"] = products["next"]
            games += products["items"]
            if products["next"] is None:
                break
        return games

    def get_auth_headers(self):
        """Return headers needed to authenticate HTTP requests"""
        if not self.access_token:
            raise RuntimeError("User not authenticated to EA")
        return {
            "Authorization": "Bearer %s" % self.access_token,
            "AuthToken": self.access_token,
            "X-AuthToken": self.access_token,
        }

    def add_installed_games(self):
        ea_app_game = get_game_by_field("ea-app", "slug")
        if not ea_app_game:
            logger.error("EA App is not installed")
        ea_app_prefix = ea_app_game["directory"].split("drive_c")[0]
        if not os.path.exists(os.path.join(ea_app_prefix, "drive_c")):
            logger.error("Invalid install of EA App at %s", ea_app_prefix)
            return
        ea_app_launcher = EAAppGames(ea_app_prefix)
        installed_slugs = []
        for content_ids in ea_app_launcher.get_installed_games_content_ids():
            slug = self.install_from_ea_app(ea_app_game, content_ids)
            if slug:
                installed_slugs.append(slug)
        sync_media(installed_slugs)
        logger.debug("Installed %s EA games", len(installed_slugs))

    def install_from_ea_app(self, ea_game, content_ids):
        offer_id = content_ids[0]
        logger.debug("Installing EA game %s", offer_id)
        service_game = ServiceGameCollection.get_game("ea_app", offer_id)
        if not service_game:
            logger.error("Aborting install, %s is not present in the game library.", offer_id)
            return
        lutris_game_id = slugify(service_game["name"]) + "-" + self.id
        existing_game = get_game_by_field(lutris_game_id, "installer_slug")
        if existing_game:
            return
        game_config = LutrisConfig(game_config_id=ea_game["configpath"]).game_level
        game_config["game"]["args"] = get_launch_arguments(",".join(content_ids))
        configpath = write_game_config(lutris_game_id, game_config)
        slug = self.get_installed_slug(ea_game)
        add_game(
            name=service_game["name"],
            runner=ea_game["runner"],
            slug=slug,
            directory=ea_game["directory"],
            installed=1,
            installer_slug=lutris_game_id,
            configpath=configpath,
            service=self.id,
            service_id=offer_id,
        )
        return slug

    def generate_installer(self, db_game, ea_db_game):
        ea_game = Game(ea_db_game["id"])
        ea_exe = ea_game.config.game_config["exe"]
        if not os.path.isabs(ea_exe):
            ea_exe = os.path.join(ea_game.config.game_config["prefix"], ea_exe)
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
                    "args": get_launch_arguments(db_game["appid"]),
                },
                "installer": [
                    {
                        "task": {
                            "name": "wineexec",
                            "executable": ea_exe,
                            "args": get_launch_arguments(db_game["appid"]),
                            "prefix": ea_game.config.game_config["prefix"],
                            "description": ("EA App will now open and prompt you to install %s." % db_game["name"]),
                        }
                    }
                ],
            },
        }

    def get_installed_runner_name(self, db_game):
        return self.runner

    def install(self, db_game):
        ea_app_game = get_game_by_field(self.client_installer, "slug")
        application = Gio.Application.get_default()
        if not ea_app_game or not ea_app_game["installed"]:
            logger.warning("Installing the EA App client")
            application.show_lutris_installer_window(game_slug=self.client_installer)
        else:
            application.show_installer_window(
                [self.generate_installer(db_game, ea_app_game)], service=self, appid=db_game["appid"]
            )


def get_launch_arguments(content_id, action="launch"):
    """Return launch argument for EA games.
    download used to be a valid action but it doesn't seem like it's implemented in EA App."""
    return f"origin2://game/{action}?offerIds={content_id}&autoDownload=1"
