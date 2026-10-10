"""EA App service."""

import json
import os
import ssl
from collections.abc import Iterator
from gettext import gettext as _
from typing import Any
from xml.etree import ElementTree

import requests
import urllib3
from gi.repository import Gio

from lutris import settings
from lutris.config import LutrisConfig, write_game_config
from lutris.database.games import add_game, get_game_by_field
from lutris.database.services import ServiceGameCollection
from lutris.game import Game
from lutris.services.base import SERVICE_LOGIN, AuthTokenExpiredError, OnlineService
from lutris.services.lutris import sync_media
from lutris.services.service_game import ServiceGame
from lutris.services.service_media import LogoOverlayMedia
from lutris.util.log import logger
from lutris.util.strings import slugify

# SSL_OP_ALLOW_UNSAFE_LEGACY_RENEGOTIATION, as needed by LegacyRenegotiationHTTPAdapter.
# Python's ssl module does not expose this OpenSSL flag (it only provides
# OP_LEGACY_SERVER_CONNECT), so its value has to be passed to OpenSSL directly.
SSL_OP_ALLOW_UNSAFE_LEGACY_RENEGOTIATION = 1 << 18

# EA can be slow to answer, but it must never hang a service reload forever.
HTTP_TIMEOUT = 30

# Number of entitlements to request, and of game details to look up, at a time.
API_PAGE_SIZE = 100


class EAAppGames:
    """Scans the games installed by the EA App inside a Wine prefix."""

    ea_games_location = "Program Files/EA Games"

    def __init__(self, prefix_path: str) -> None:
        self.prefix_path = prefix_path
        self.ea_games_path = os.path.join(self.prefix_path, "drive_c", self.ea_games_location)

    def iter_installed_games(self) -> Iterator[str]:
        """Yield the name of each folder in the EA Games directory."""
        try:
            with os.scandir(self.ea_games_path) as entries:
                for entry in entries:
                    if entry.is_dir():
                        yield entry.name
        except OSError:
            logger.debug("No EA Games folder in %s", self.prefix_path)
            return

    def get_installed_games_content_ids(self) -> list[list[str]]:
        """Return the content IDs of each game installed by the EA App, as read
        from the installerdata.xml files it writes next to the games."""
        installed_game_ids = []
        for game_folder in self.iter_installed_games():
            content_ids = self._read_content_ids(game_folder)
            if content_ids:
                installed_game_ids.append(content_ids)
        return installed_game_ids

    def _read_content_ids(self, game_folder: str) -> list[str]:
        """Return the content IDs in the installerdata.xml of a game folder, or
        an empty list if it is missing or unreadable."""
        installer_data_path = os.path.join(self.ea_games_path, game_folder, "__Installer", "installerdata.xml")
        if not os.path.exists(installer_data_path):
            logger.warning("No installerdata.xml for %s", game_folder)
            return []
        try:
            tree = ElementTree.parse(installer_data_path)
        except ElementTree.ParseError:
            logger.warning("Could not parse %s", installer_data_path)
            return []
        content_ids_node = tree.find("contentIDs")
        content_ids: list[str] = []
        if content_ids_node is not None:
            content_ids = [node.text for node in content_ids_node.findall("contentID") if node.text]
        if not content_ids:
            logger.warning("Content ID not found for %s", game_folder)
        return content_ids


class EAAppMedia(LogoOverlayMedia):
    """Media of the EA App games, as returned by the EA API.

    The API provides the artwork and a separate logo image, and the logo is
    composited onto the artwork when it is a real logo rather than a duplicate of
    the artwork itself.
    """

    service = "ea_app"
    file_patterns = ["%s.jpg"]
    name = NotImplemented
    logo_y_position = 0.7

    # ServiceMedia declares dest_path as a plain attribute; deriving it from the
    # media name keeps the media directory in sync with that name instead.
    @property
    def dest_path(self) -> str:  # type: ignore[override]
        return self.get_dest_path()

    @classmethod
    def get_dest_path(cls) -> str:
        return os.path.join(settings.CACHE_DIR, cls.service, cls.name)

    def get_media_url(self, details: dict[str, Any]) -> str | None:
        """Return the URL of this media for a game, or None if the API did not
        provide an image of this type."""
        base_item = details.get("baseItem")
        art = base_item.get(self.name) if isinstance(base_item, dict) else None
        largest_image = art.get("largestImage") if isinstance(art, dict) else None
        path = largest_image.get("path") if isinstance(largest_image, dict) else None
        return path if isinstance(path, str) else None


class EAAppPrimaryLogo(EAAppMedia):
    """The logo images; these are composited onto the other media types."""

    name = "primaryLogo"
    size = (200, 100)
    file_patterns = ["%s.png"]


EA_LOGO_PATH = EAAppPrimaryLogo.get_dest_path()


class EAAppKeyArt(EAAppMedia):
    name = "keyArt"
    size = (192, 108)
    logo_path = EA_LOGO_PATH
    logo_max_size = (150, 65)


class EAAppPackArt(EAAppMedia):
    name = "packArt"
    size = (135, 240)
    logo_path = EA_LOGO_PATH
    logo_max_size = (110, 80)


class EAAppGame(ServiceGame):
    service = "ea_app"

    @classmethod
    def new_from_api(cls, game: dict[str, Any]) -> "EAAppGame | None":
        """Convert an EA App API game to a service game, or None if the API data
        is missing the fields that Lutris needs."""
        base_item = game.get("baseItem")
        title = base_item.get("title") if isinstance(base_item, dict) else None
        content_id = game.get("contentId")
        if not content_id or not title:
            logger.warning("Skipping an EA game without content ID or title: %s", game)
            return None
        ea_game = cls()
        ea_game.appid = content_id
        ea_game.slug = game.get("gameSlug") or slugify(str(title))
        ea_game.name = title
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
    }
    extra_medias = {
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

    def __init__(self) -> None:
        super().__init__()

        self.session = requests.session()
        self.session.mount("https://", LegacyRenegotiationHTTPAdapter())
        self.access_token = self.load_access_token()

    @property
    def api_headers(self) -> dict[str, str]:
        headers = {"User-Agent": self.login_user_agent}
        headers.update(self.get_auth_headers())
        return headers

    def is_connected(self) -> bool:
        return bool(self.access_token)

    def login_callback(self, url: str) -> None:
        self.fetch_access_token()
        SERVICE_LOGIN.fire(self)

    def fetch_access_token(self) -> None:
        token_data = self.get_access_token()
        if not token_data:
            raise RuntimeError("Failed to get access token")
        with open(self.token_path, "w", encoding="utf-8") as token_file:
            token_file.write(json.dumps(token_data, indent=2))
        self.access_token = self.load_access_token()

    def load_access_token(self) -> str:
        """Return the stored access token, or an empty string if there is none."""
        try:
            with open(self.token_path, encoding="utf-8") as token_file:
                token_data = json.load(token_file)
        except FileNotFoundError:
            return ""
        except (OSError, ValueError):
            logger.warning("Unreadable EA access token in %s", self.token_path, exc_info=True)
            return ""
        if not isinstance(token_data, dict):
            return ""
        return token_data.get("access_token") or ""

    def fetch_api(self, query: str, params: dict | None = None) -> dict[str, Any]:
        """Run a GraphQL query against the EA API and return the reply."""
        response = self.session.post(
            self.api_url,
            headers=self.api_headers,
            json={"query": query, "variables": params or {}},
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise RuntimeError("Unexpected reply from the EA api: %s" % result)
        if result.get("errors"):
            raise RuntimeError("Errors occurred while running an EA api query: %s" % result["errors"])
        return result

    def get_access_token(self) -> dict[str, Any]:
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
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    def _request_identity(self) -> dict[str, Any]:
        response = self.session.get(
            "https://gateway.ea.com/proxy/identity/pids/me",
            cookies=self.load_cookies(),
            headers=self.get_auth_headers(),
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        identity = response.json()
        return identity if isinstance(identity, dict) else {}

    def _refresh_access_token(self) -> None:
        """Request a new access token, raising AuthTokenExpiredError if EA refuses."""
        try:
            self.fetch_access_token()
        except Exception:  # pylint: disable=broad-except
            raise AuthTokenExpiredError("EA access token expired, please log in again")

    def get_identity(self) -> tuple[str, str, str]:
        """Request the user info"""
        if not self.access_token:
            logger.warning("No EA access token, attempting to refresh")
            self._refresh_access_token()

        identity_data = self._request_identity()
        if identity_data.get("error") == "invalid_access_token":
            logger.warning("Refreshing EA access token")
            self._refresh_access_token()
            identity_data = self._request_identity()

        error = identity_data.get("error")
        if error:
            raise RuntimeError("%s (Error code: %s)" % (error, identity_data.get("error_number")))

        player = self.fetch_api("query{me{player{pd psd displayName}}}")["data"]["me"]["player"]
        return str(player["pd"]), str(player["psd"]), str(player["displayName"])

    def load(self) -> list[EAAppGame]:
        # get_identity() refreshes the access token, and raises AuthTokenExpiredError
        # if the user has to log in again.
        self.get_identity()
        games = self.get_library()
        logger.info("Retrieved %s games from EA library", len(games))
        ea_games: list[EAAppGame] = []
        for game in games:
            ea_game = EAAppGame.new_from_api(game)
            if ea_game:
                ea_game.save()
                ea_games.append(ea_game)
        return ea_games

    def get_library(self) -> list[dict[str, Any]]:
        """Load the EA library: the API details of each owned base game."""
        entitlements = [
            entitlement
            for entitlement in self.get_entitlements()
            if entitlement.get("originOfferId") and self._is_base_game(entitlement)
        ]
        games: list[dict[str, Any]] = []
        for start in range(0, len(entitlements), API_PAGE_SIZE):
            chunk = entitlements[start : start + API_PAGE_SIZE]
            games += self.get_games([entitlement["originOfferId"] for entitlement in chunk])
        return games

    @staticmethod
    def _is_base_game(entitlement: dict[str, Any]) -> bool:
        """True for the entitlements of a base game. The other entitlements (DLC and
        the likes) have no artwork of their own, and the EA App does not list them
        either."""
        product = entitlement.get("product")
        if not isinstance(product, dict):
            return False
        base_item = product.get("baseItem")
        return isinstance(base_item, dict) and base_item.get("gameType") == "BASE_GAME"

    def get_games(self, offer_ids: list[str]) -> list[dict[str, Any]]:
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

        data = result.get("data") or {}
        legacy_offers = data.get("legacyOffers") or []
        game_products = (data.get("gameProducts") or {}).get("items") or []
        products = [product for product in game_products if isinstance(product, dict)]
        by_offer = {p.get("originOfferId"): p for p in products if p.get("originOfferId")}
        by_product_id = {p.get("id"): p for p in products if p.get("id")}

        games = []
        for legacy_offer in legacy_offers:
            if not isinstance(legacy_offer, dict):
                continue
            offer_id = legacy_offer.get("offerId")
            content_id = legacy_offer.get("contentId")
            if not offer_id:
                continue
            # The game details can be listed under the offer ID or the content ID.
            product = by_offer.get(offer_id)
            if not product and content_id:
                product = by_product_id.get(content_id)
            if not product:
                product = by_product_id.get(offer_id)
            # Certain games have identification data but no product information; skip those.
            if not product:
                continue
            games.append({"contentId": content_id, **product})
        return games

    def get_entitlements(self) -> list[dict[str, Any]]:
        """Request the user's entitlements"""
        games: list[dict[str, Any]] = []
        variables: dict[str, Any] = {"limit": API_PAGE_SIZE}
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
            games += products["items"]
            next_cursor = products["next"]
            # Stop at the end of the list, or if EA hands out the same cursor again.
            if not next_cursor or next_cursor == variables.get("next"):
                break
            variables["next"] = next_cursor
        return games

    def get_auth_headers(self) -> dict[str, str]:
        """Return headers needed to authenticate HTTP requests"""
        if not self.access_token:
            raise RuntimeError("User not authenticated to EA")
        return {
            "Authorization": "Bearer %s" % self.access_token,
            "AuthToken": self.access_token,
            "X-AuthToken": self.access_token,
        }

    def add_installed_games(self) -> None:
        """Scan the games installed by the EA App and add them to the library."""
        ea_app_game = get_game_by_field(self.client_installer, "slug")
        if not ea_app_game:
            logger.error("EA App is not installed")
            return
        ea_app_prefix = self._get_prefix_path(ea_app_game)
        if not ea_app_prefix:
            return
        ea_app_launcher = EAAppGames(ea_app_prefix)
        installed_slugs = []
        for content_ids in ea_app_launcher.get_installed_games_content_ids():
            slug = self.install_from_ea_app(ea_app_game, content_ids)
            if slug:
                installed_slugs.append(slug)
        logger.debug("Installed %s EA games", len(installed_slugs))
        sync_media(installed_slugs)

    @staticmethod
    def _get_prefix_path(ea_app_game: dict[str, Any]) -> str | None:
        """Return the Wine prefix that the EA App is installed in, or None if the
        game directory does not look like a Wine prefix."""
        directory = ea_app_game.get("directory")
        if not directory:
            logger.error("The EA App install has no directory; cannot scan for games.")
            return None
        drive_c_index = directory.find("drive_c")
        if drive_c_index == -1:
            logger.error("Could not find a Wine prefix in the EA App directory '%s'.", directory)
            return None
        prefix_path = directory[:drive_c_index].rstrip("/\\")
        if not os.path.isdir(os.path.join(prefix_path, "drive_c")):
            logger.error("Invalid install of EA App at %s", prefix_path)
            return None
        return prefix_path

    def install_from_ea_app(self, ea_app_game: dict[str, Any], content_ids: list[str]) -> str | None:
        """Add a game the EA App installed to the Lutris library, and return the
        slug of the added game, if it was added."""
        content_ids = [content_id for content_id in content_ids if content_id]
        if not content_ids:
            return None
        offer_id = content_ids[0]
        logger.debug("Installing EA game %s", offer_id)
        service_game = ServiceGameCollection.get_game(self.id, offer_id)
        if not service_game:
            logger.error("Aborting install, %s is not present in the game library.", offer_id)
            return None
        lutris_game_id = slugify(str(service_game["name"])) + "-" + self.id
        existing_game = get_game_by_field(lutris_game_id, "installer_slug")
        if existing_game:
            return None
        game_config = LutrisConfig(game_config_id=ea_app_game["configpath"]).game_level
        game_config["game"]["args"] = get_launch_arguments(",".join(content_ids))
        configpath = write_game_config(lutris_game_id, game_config)
        slug = self.get_installed_slug(service_game)
        add_game(
            name=service_game["name"],
            runner=ea_app_game["runner"],
            slug=slug,
            directory=ea_app_game["directory"],
            installed=1,
            installer_slug=lutris_game_id,
            configpath=configpath,
            service=self.id,
            service_id=offer_id,
        )
        return slug

    def generate_installer(  # type: ignore[override]
        self, db_game: dict[str, Any], ea_db_game: dict[str, Any]
    ) -> dict[str, Any]:
        ea_game = Game(ea_db_game["id"])
        ea_config = ea_game.config
        if not ea_config or not ea_config.game_config:
            raise RuntimeError("EA App game '%s' has no configuration." % ea_db_game.get("id"))

        ea_exe = ea_config.game_config.get("exe")
        ea_prefix = ea_config.game_config.get("prefix")
        if not ea_exe or not ea_prefix:
            raise RuntimeError("EA App game '%s' has no 'exe' or 'prefix'." % ea_db_game.get("id"))
        if not os.path.isabs(ea_exe):
            ea_exe = os.path.join(ea_prefix, ea_exe)
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
                            "prefix": ea_prefix,
                            "description": ("EA App will now open and prompt you to install %s." % db_game["name"]),
                        }
                    }
                ],
            },
        }

    def get_installed_runner_name(self, db_game: dict[str, Any]) -> str:
        return self.runner

    def install(self, db_game: dict[str, Any]) -> None:  # type: ignore[override]
        ea_app_game = get_game_by_field(self.client_installer, "slug")
        application = Gio.Application.get_default()
        assert application is not None
        if not ea_app_game or not ea_app_game.get("installed"):
            logger.warning("Installing the EA App client")
            application.show_lutris_installer_window(game_slug=self.client_installer)  # type: ignore[attr-defined]
        else:
            application.show_installer_window(  # type: ignore[attr-defined]
                [self.generate_installer(db_game, ea_app_game)], service=self, appid=db_game["appid"]
            )


def get_launch_arguments(content_id: str, action: str = "launch") -> str:
    """Return the launch argument for an EA game.

    download used to be a valid action but it doesn't seem like it's implemented in
    the EA App."""
    return f"origin2://game/{action}?offerIds={content_id}&autoDownload=1"
