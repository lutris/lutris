"""Epic Games Store service"""

import json
import os
from collections import defaultdict
from gettext import gettext as _
from typing import Any, Optional, cast

import requests
from gi.repository import Gio

from lutris import settings
from lutris.config import LutrisConfig, write_game_config
from lutris.database.games import add_game, get_game_by_field
from lutris.database.services import ServiceGameCollection
from lutris.game import Game
from lutris.gui.widgets.utils import Image, paste_overlay, thumbnail_image
from lutris.services.base import SERVICE_LOGIN, AuthTokenExpiredError, OnlineService
from lutris.services.lutris import sync_media
from lutris.services.service_game import ServiceGame
from lutris.services.service_media import ServiceMedia
from lutris.util import system
from lutris.util.egs.egs_launcher import EGSLauncher
from lutris.util.log import logger
from lutris.util.strings import slugify

EGS_LOGO_PATH = os.path.join(settings.CACHE_DIR, "egs/game_logo")


class DieselGameMedia(ServiceMedia):
    service = "egs"
    remote_size = (200, 267)
    file_patterns = ["%s.jpg"]
    min_logo_x = 300
    min_logo_y = 150

    def _render_filename(self, filename: str) -> None:
        game_box_path = os.path.join(self.dest_path, filename)
        logo_path = os.path.join(EGS_LOGO_PATH, filename.replace(".jpg", ".png"))
        has_logo = os.path.exists(logo_path)
        thumb_image = Image.open(game_box_path)  # type: ignore[union-attr]
        thumb_image = thumb_image.convert("RGBA")
        thumb_image = thumbnail_image(thumb_image, self.remote_size)
        if has_logo:
            logo_image = Image.open(logo_path)  # type: ignore[union-attr]
            logo_image = logo_image.convert("RGBA")
            logo_width, logo_height = logo_image.size
            if logo_width > self.min_logo_x:
                logo_image = logo_image.resize(
                    (self.min_logo_x, int(logo_height * (self.min_logo_x / logo_width))),
                    resample=Image.Resampling.BICUBIC,  # type: ignore[union-attr]
                )
            elif logo_height > self.min_logo_y:
                logo_image = logo_image.resize(
                    (int(logo_width * (self.min_logo_y / logo_height)), self.min_logo_y),
                    resample=Image.Resampling.BICUBIC,  # type: ignore[union-attr]
                )
            thumb_image = paste_overlay(thumb_image, logo_image)
        thumb_path = os.path.join(self.dest_path, filename)
        thumb_image = thumb_image.convert("RGB")
        thumb_image.save(thumb_path)

    def get_media_url(self, details: dict[str, Any]) -> str | None:
        for image in details.get("keyImages", []):
            if image["type"] == self.api_field:
                return f"{image['url']}?w={self.remote_size[0]}&resize=1&h={self.remote_size[1]}"
        return None


class DieselGameBoxTall(DieselGameMedia):
    """EGS tall game box"""

    size = (200, 267)
    remote_size = size
    min_logo_x = 100
    min_logo_y = 100
    dest_path = os.path.join(settings.CACHE_DIR, "egs/game_box_tall")
    api_field = "DieselGameBoxTall"

    def render(self) -> None:
        if not os.path.isdir(self.dest_path):
            return
        for filename in os.listdir(self.dest_path):
            self._render_filename(filename)


class DieselGameBoxSmall(DieselGameBoxTall):
    size = (100, 133)
    remote_size = (200, 267)


class DieselGameBox(DieselGameBoxTall):
    """EGS game box"""

    size = (316, 178)
    remote_size = size
    min_logo_x = 300
    min_logo_y = 150
    dest_path = os.path.join(settings.CACHE_DIR, "egs/game_box")
    api_field = "DieselGameBox"


class DieselGameBannerSmall(DieselGameBox):
    size = (158, 89)
    remote_size = (316, 178)


class DieselGameBoxLogo(DieselGameMedia):
    """EGS game box"""

    size = (200, 100)
    remote_size = size
    file_patterns = ["%s.png"]
    visible = False
    dest_path = os.path.join(settings.CACHE_DIR, "egs/game_logo")
    api_field = "DieselGameBoxLogo"


class EGSGame(ServiceGame):
    """Service game for Epic Games Store"""

    service = "egs"

    @classmethod
    def new_from_api(cls, egs_game: dict[str, Any]) -> "EGSGame":
        """Convert an EGS game to a service game"""
        service_game = cls()
        service_game.appid = egs_game["appName"]
        service_game.slug = slugify(egs_game["title"])
        service_game.name = egs_game["title"]
        service_game.details = json.dumps(egs_game)
        return service_game


class EpicGamesStoreService(OnlineService):
    """Service class for Epic Games Store"""

    id = "egs"
    name = _("Epic Games Store")
    login_window_width = 500
    login_window_height = 850
    icon = "egs"
    online = True
    runner = "wine"
    client_installer = "epic-games-store"
    medias = {
        "game_box_small": DieselGameBoxSmall,
        "game_banner_small": DieselGameBannerSmall,
        "game_box": DieselGameBox,
        "box_tall": DieselGameBoxTall,
    }
    extra_medias = {
        "logo": DieselGameBoxLogo,
    }
    default_format = "game_banner_small"
    requires_login_page = True
    cookies_path = os.path.join(settings.CACHE_DIR, ".egs.auth")
    token_path = os.path.join(settings.CACHE_DIR, ".egs.token")
    cache_path = os.path.join(settings.CACHE_DIR, "egs-library.json")
    login_url = (
        "https://www.epicgames.com/id/login?redirectUrl="
        "https%3A//www.epicgames.com/id/api/redirect%3F"
        "clientId%3D34a02cf8f4414e29b15921876da36f9a%26responseType%3Dcode"
    )
    redirect_uris = ["https://www.epicgames.com/id/api/redirect"]
    oauth_url = "https://account-public-service-prod03.ol.epicgames.com"
    catalog_url = "https://catalog-public-service-prod06.ol.epicgames.com"
    library_url = "https://library-service.live.use1a.on.epicgames.com"
    token_url = f"{oauth_url}/account/api/oauth/token"

    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "EpicGamesLauncher/11.0.1-14907503+++Portal+Release-Live "
        "UnrealEngine/4.23.0-14907503+++Portal+Release-Live "
        "Chrome/84.0.4147.38 Safari/537.36"
    )

    _http_basic_auth = requests.auth.HTTPBasicAuth(
        "34a02cf8f4414e29b15921876da36f9a", "daafbccc737745039dffe53d94fc76cf"
    )

    def __init__(self) -> None:
        super().__init__()
        self.session = requests.session()
        self.session.headers["User-Agent"] = self.user_agent
        self.session_data: dict[str, Any] = {}
        if os.path.exists(self.token_path):
            try:
                with open(self.token_path, encoding="utf-8") as token_file:
                    self.session_data = json.loads(token_file.read())
            except Exception as ex:
                logger.exception("Unable to load token file '%s': %s", self.token_path, ex)

    @property
    def http_basic_auth(self) -> requests.auth.HTTPBasicAuth:
        return self._http_basic_auth

    def is_connected(self) -> bool:
        return self.is_authenticated()

    def login_callback(self, content: bytes) -> None:
        """Once the user logs in in a browser window, Epic redirects
        to a page containing a Session ID which we can use to finish the authentication.
        Store session ID and exchange token to auth file"""
        logger.debug("Login to EGS successful")
        logger.debug(content)
        content_json = json.loads(content.decode())
        session_id = content_json.get("authorizationCode")
        if not session_id:
            raise RuntimeError("Missing authorizationCode in login callback response")

        self.start_session(authorization_code=session_id)
        SERVICE_LOGIN.fire(self)

    def resume_session(self) -> dict[str, Any]:
        self.session.headers["Authorization"] = f"bearer {self.session_data['access_token']}"
        response = self.session.get(f"{self.oauth_url}/account/api/oauth/verify")
        if response.status_code >= 500:
            response.raise_for_status()

        response_content = response.json()
        if "errorMessage" not in response_content:
            return response_content

        # Access token expired; try to refresh using the stored refresh_token.
        if "refresh_token" in self.session_data:
            logger.info("EGS access token expired; attempting token refresh.")
            self.start_session()
            # Retry the verification with the new access token
            self.session.headers["Authorization"] = f"bearer {self.session_data['access_token']}"
            response = self.session.get(f"{self.oauth_url}/account/api/oauth/verify")
            if response.status_code >= 500:
                response.raise_for_status()
            response_content = response.json()
            if "errorMessage" in response_content:
                raise RuntimeError(response_content)
            return response_content

        raise RuntimeError(response_content)

    def start_session(
        self,
        exchange_code: Optional[str] = None,
        authorization_code: Optional[str] = None,
    ) -> None:
        if exchange_code:
            params: dict[str, str] = {
                "grant_type": "exchange_code",
                "exchange_code": exchange_code,
                "token_type": "eg1",
            }
        elif authorization_code:
            params = {"grant_type": "authorization_code", "code": authorization_code, "token_type": "eg1"}
        else:
            params = {
                "grant_type": "refresh_token",
                "refresh_token": self.session_data["refresh_token"],
                "token_type": "eg1",
            }

        response = self.session.post(
            self.token_url,
            data=params,
            auth=self.http_basic_auth,
        )
        if response.status_code >= 500:
            response.raise_for_status()

        response_content = response.json()
        if "error" in response_content:
            raise RuntimeError(response_content)
        with open(self.token_path, "w", encoding="utf-8") as auth_file:
            auth_file.write(json.dumps(response_content, indent=2))
        self.session_data = response_content

    def get_game_details(self, asset: dict[str, Any]) -> dict[str, Any]:
        namespace = asset["namespace"]
        catalog_item_id = asset["catalogItemId"]
        response = self.session.get(
            f"{self.catalog_url}/catalog/api/shared/namespace/{namespace}/bulk/items",
            params={
                "id": catalog_item_id,
                "includeDLCDetails": True,
                "includeMainGameDetails": True,
                "country": "US",
                "locale": "en",
            },
        )
        response.raise_for_status()
        response_data = response.json()
        details = response_data.get(catalog_item_id)
        if not details:
            logger.warning("No details found in API response for catalog item '%s'", catalog_item_id)
            return asset
        # Merge the details with the initial asset to keep 'appName'
        asset.update(details)
        return asset

    def _get_batched_game_details(self, records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Fetch game details in batches grouped by namespace to minimize API requests."""
        namespace_groups: dict[str, list[str]] = defaultdict(list)
        for record in records:
            namespace = record.get("namespace")
            catalog_item_id = record.get("catalogItemId")
            if namespace and catalog_item_id:
                namespace_groups[namespace].append(catalog_item_id)

        details_map: dict[str, dict[str, Any]] = {}
        for namespace, item_ids in namespace_groups.items():
            if not namespace:
                continue
            # Join all item IDs for this namespace into one request
            joined_ids = ",".join(item_ids)
            response = self.session.get(
                f"{self.catalog_url}/catalog/api/shared/namespace/{namespace}/bulk/items",
                params={
                    "id": joined_ids,
                    "includeDLCDetails": True,
                    "includeMainGameDetails": True,
                    "country": "US",
                    "locale": "en",
                },  # type: ignore[arg-type]
            )
            if response.status_code >= 500:
                response.raise_for_status()
            response_data = response.json()
            for item_id in item_ids:
                details = response_data.get(item_id)
                if details:
                    details_map[item_id] = details
                else:
                    logger.warning("No details found for catalog item '%s' in namespace '%s'", item_id, namespace)
        return details_map

    @staticmethod
    def is_editor_resource(item: dict[str, Any]) -> bool:
        """Return True for Epic/Fab/Unreal resources that are not launchable games."""
        category_paths = {
            category.get("path", "") for category in item.get("categories", []) if isinstance(category, dict)
        }

        custom_attributes = item.get("customAttributes") or {}
        release_info = item.get("releaseInfo") or []

        return (
            item.get("entitlementType") == "AUDIENCE"
            or "type/format-item" in category_paths
            or any(path.startswith("asset-format") for path in category_paths)
            or "ListingIdentifier" in custom_attributes
            or any(isinstance(release, dict) and "compatibleApps" in release for release in release_info)
        )

    def get_library(self) -> list[dict[str, Any]]:
        self.resume_session()
        response = self.session.get(f"{self.library_url}/library/api/public/items", params={"includeMetadata": "true"})
        response.raise_for_status()
        res_data = response.json()
        records: list[dict[str, Any]] = res_data["records"]
        cursor = res_data["responseMetadata"].get("nextCursor")

        while cursor:
            response = self.session.get(
                f"{self.library_url}/library/api/public/items",
                params={"includeMetadata": "true", "cursor": cursor},
            )
            response.raise_for_status()
            res_data = response.json()
            records.extend(res_data["records"])
            cursor = res_data["responseMetadata"].get("nextCursor")

        # Filter out ue namespace records first
        non_ue_records = [r for r in records if r.get("namespace") != "ue"]

        # Batch fetch all game details grouped by namespace
        details_map = self._get_batched_game_details(non_ue_records)

        games = []
        for record in non_ue_records:
            catalog_item_id = record.get("catalogItemId")
            assert isinstance(catalog_item_id, str), f"Expected string catalogItemId, got {type(catalog_item_id)}"
            game_details = details_map.get(catalog_item_id)
            if not game_details:
                logger.warning(
                    "Skipping game '%s' (%s): no details available",
                    record.get("title") or record.get("appName"),
                    catalog_item_id,
                )
                continue

            if self.is_editor_resource(game_details):
                logger.info(
                    "Skipping Epic editor/resource entry: %s (%s)",
                    game_details.get("title") or game_details.get("appName"),
                    game_details.get("entitlementType"),
                )
                continue

            # Merge 'appName' from the original record into the details
            if "appName" in record:
                game_details["appName"] = record["appName"]
            games.append(game_details)
        return games

    def load(self) -> list[EGSGame]:
        """Load the list of games"""
        try:
            library = self.get_library()
        except Exception as ex:
            logger.warning("EGS Token expired")
            raise AuthTokenExpiredError("EGS Token expired") from ex
        egs_games = []
        for game in library:
            try:
                # Subscriptions turn up as 'games' that have no 'appName'; these
                # are not really games, so we skip them.
                if "appName" in game:
                    egs_game = EGSGame.new_from_api(game)
                else:
                    continue
            except Exception as ex:
                logger.exception("Unable to interpret EGS game: %s", ex)
                logger.info("EGS game skipped: %s", game)
                continue
            egs_game.save()
            egs_games.append(egs_game)
        return egs_games

    def install_from_egs(self, egs_game: dict[str, Any], manifest: dict[str, Any]) -> Optional[str]:
        """Create a new Lutris game based on an existing EGS install"""
        app_name = manifest["AppName"]
        logger.debug("Installing EGS game %s", app_name)
        service_game = ServiceGameCollection.get_game("egs", app_name)
        if not service_game:
            logger.error("Aborting install, %s is not present in the game library.", app_name)
            return None
        lutris_game_id = slugify(cast(str, service_game["name"])) + "-" + self.id
        existing_game = get_game_by_field(lutris_game_id, "installer_slug")
        if existing_game:
            return None
        raw_details = cast(str, service_game.get("details") or "{}")
        details = json.loads(raw_details)
        namespace = details.get("namespace")
        catalog_item_id = details.get("catalogItemId")
        game_config = LutrisConfig(game_config_id=egs_game["configpath"]).game_level
        game_config["game"]["args"] = self.get_launch_arguments(
            app_name, namespace=namespace, catalog_item_id=catalog_item_id
        )
        configpath = write_game_config(lutris_game_id, game_config)
        slug = self.get_installed_slug(service_game)
        add_game(
            name=service_game["name"],
            runner=egs_game["runner"],
            slug=slug,
            directory=egs_game["directory"],
            installed=1,
            installer_slug=lutris_game_id,
            configpath=configpath,
            service=self.id,
            service_id=app_name,
        )
        return slug

    def add_installed_games(self) -> None:
        """Scan an existing EGS install for games"""
        egs_game = get_game_by_field("epic-games-store", "slug")
        if not egs_game:
            logger.error("EGS is not installed in Lutris")
            return

        egs_directory = egs_game.get("directory", "")
        if not egs_directory:
            logger.error("EGS install has no directory; cannot scan for games.")
            return

        # Find the Wine prefix root: look for "drive_c" in the path
        assert isinstance(egs_directory, str)
        drive_c_index = egs_directory.find("drive_c")
        if drive_c_index == -1:
            logger.error(
                "Could not determine Wine prefix from EGS directory '%s' (expected 'drive_c' in path).",
                egs_directory,
            )
            return
        egs_prefix = egs_directory[:drive_c_index].rstrip("/\\")
        logger.info("EGS detected in %s", egs_prefix)
        if not system.path_exists(os.path.join(egs_prefix, "drive_c")):
            logger.error("Invalid install of EGS at %s", egs_prefix)
            return
        egs_launcher = EGSLauncher(egs_prefix)
        installed_slugs = []
        for manifest in egs_launcher.iter_manifests():
            slug = self.install_from_egs(egs_game, manifest)
            if slug:
                installed_slugs.append(slug)
        sync_media(installed_slugs)
        logger.debug("All EGS games imported")

    def generate_installer(self, db_game: dict[str, Any], egs_db_game: dict[str, Any]) -> dict[str, Any]:  # type: ignore[override]
        egs_game = Game(egs_db_game["id"])
        egs_config = egs_game.config
        if not egs_config or not egs_config.game_config:
            raise RuntimeError(f"EGS game '{egs_db_game.get('id')}' has no valid configuration.")

        egs_exe = egs_config.game_config.get("exe")
        egs_prefix = egs_config.game_config.get("prefix")

        if not egs_exe or not egs_prefix:
            raise RuntimeError(f"EGS game '{egs_db_game.get('id')}' is missing 'exe' or 'prefix' in its configuration.")

        if not os.path.isabs(egs_exe):
            egs_exe = os.path.join(egs_prefix, egs_exe)
        details = json.loads(db_game.get("details") or "{}")
        namespace = details.get("namespace")
        catalog_item_id = details.get("catalogItemId")
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
                    "args": self.get_launch_arguments(
                        db_game["appid"], namespace=namespace, catalog_item_id=catalog_item_id
                    ),
                },
                "installer": [
                    {
                        "task": {
                            "name": "wineexec",
                            "executable": egs_exe,
                            "args": self.get_launch_arguments(
                                db_game["appid"],
                                "install",
                                namespace=namespace,
                                catalog_item_id=catalog_item_id,
                            ),
                            "prefix": egs_prefix,
                            "description": (
                                "The Epic Game Store will now open. Please launch "
                                "the installation of %s then close the EGS client "
                                "once the game has been downloaded." % db_game["name"]
                            ),
                        }
                    }
                ],
            },
        }

    def get_installed_runner_name(self, db_game: dict[str, Any]) -> str:
        return self.runner

    def install(self, db_game: dict[str, Any]) -> None:  # type: ignore[override]
        egs_game = get_game_by_field(self.client_installer, "slug")
        application = Gio.Application.get_default()
        assert application is not None
        if not egs_game or not egs_game.get("installed"):
            logger.warning("EGS (%s) not installed", self.client_installer)
            application.show_lutris_installer_window(game_slug=self.client_installer)
        else:
            application.show_installer_window(
                [self.generate_installer(db_game, egs_game)], service=self, appid=db_game["appid"]
            )

    @staticmethod
    def get_launch_arguments(
        app_name: str,
        action: str = "launch",
        namespace: Optional[str] = None,
        catalog_item_id: Optional[str] = None,
    ) -> str:
        if namespace and catalog_item_id:
            app_id = f"{namespace}%3A{catalog_item_id}%3A{app_name}"
        else:
            app_id = app_name
        return f"-opengl -SkipBuildPatchPrereq -com.epicgames.launcher://apps/{app_id}?action={action}"
