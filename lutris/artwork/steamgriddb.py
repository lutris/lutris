"""A small client for SteamGridDB's API, which needs the user's own API key."""

import os
from gettext import gettext as _
from typing import Any
from urllib.parse import quote

import requests

from lutris import settings
from lutris.exceptions import LutrisError
from lutris.util.http import get_request_proxies
from lutris.util.log import logger

API_URL = "https://www.steamgriddb.com/api/v2"
API_KEY_SETTING = "steamgriddb_api_key"
API_KEY_ENVIRONMENT = "LUTRIS_STEAMGRIDDB_API_KEY"
# Where users create their key
API_KEY_PAGE = "https://www.steamgriddb.com/profile/preferences/api"
# Grid sizes to ask for, best first; what matters is the shape the library shows them at.
# Covers are 2:3, with SteamGridDB's near 2:3 sizes as a fallback, and banners have the
# shape of Steam's 920x430 header capsules.
COVER_DIMENSIONS = ("600x900", "342x482,660x930")
BANNER_DIMENSIONS = ("920x430,460x215",)
TIMEOUT_SECONDS = 15


class SteamGridDBError(LutrisError):
    """SteamGridDB refused a request, such as for a wrong API key."""


def get_api_key() -> str:
    """Return the API key from the environment or the settings, or an empty string."""
    return os.environ.get(API_KEY_ENVIRONMENT) or settings.read_setting(API_KEY_SETTING)


class SteamGridDB:
    def __init__(self, api_key: str) -> None:
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {api_key}"
        self._session.proxies = get_request_proxies(API_URL)

    def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        """Return a response's data, or None if SteamGridDB has nothing there."""
        try:
            response = self._session.get(API_URL + path, params=params, timeout=TIMEOUT_SECONDS)
        except requests.RequestException as error:
            raise SteamGridDBError(_("SteamGridDB could not be reached: %s") % error) from error
        if response.status_code == 404:
            return None
        if response.status_code in (401, 403):
            raise SteamGridDBError(_("SteamGridDB rejected the API key."))
        if not response.ok:
            raise SteamGridDBError(_("SteamGridDB answered with error %s.") % response.status_code)
        body = response.json()
        return body.get("data") if isinstance(body, dict) and body.get("success") else None

    def check_api_key(self) -> None:
        """Raise SteamGridDBError unless the API key is accepted."""
        self._get("/search/autocomplete/" + quote("portal", safe=""))

    def find_game(self, name: str, steam_appid: str = "") -> int | None:
        """Return SteamGridDB's id for a game, by its Steam app id if it has one, else by name."""
        if steam_appid:
            game = self._get(f"/games/steam/{quote(steam_appid, safe='')}")
            if isinstance(game, dict) and game.get("id"):
                return int(game["id"])
        if not name.strip():
            return None
        results = self._get("/search/autocomplete/" + quote(name.strip(), safe=""))
        if not isinstance(results, list) or not results:
            return None
        wanted = name.strip().casefold()
        exact = [result for result in results if str(result.get("name", "")).casefold() == wanted]
        return int((exact or results)[0]["id"])

    def grids(self, game_id: int, dimensions: str) -> list[dict[str, Any]]:
        """Return the static grids of some dimensions, best first."""
        params = {
            "dimensions": dimensions,
            "types": "static",
            "mimes": "image/png,image/jpeg",
            "nsfw": "false",
            "humor": "false",
        }
        return _images(self._get(f"/grids/game/{game_id}", params))

    def icons(self, game_id: int) -> list[dict[str, Any]]:
        params = {"types": "static", "mimes": "image/png", "nsfw": "false", "humor": "false"}
        return _images(self._get(f"/icons/game/{game_id}", params))

    def grid_url(self, game_id: int, dimensions: tuple[str, ...]) -> str | None:
        """Return the URL of the best static grid, trying each set of dimensions in turn."""
        for sizes in dimensions:
            if url := self._first_url(self.grids(game_id, sizes)):
                return url
        return None

    def icon_url(self, game_id: int) -> str | None:
        return self._first_url(self.icons(game_id))

    @staticmethod
    def _first_url(images: list[dict[str, Any]]) -> str | None:
        if images:
            return str(images[0]["url"])
        logger.debug("SteamGridDB has no matching image")
        return None


def _images(data: Any) -> list[dict[str, Any]]:
    """Return the images in a response that have a URL."""
    if not isinstance(data, list):
        return []
    return [image for image in data if isinstance(image, dict) and image.get("url")]
