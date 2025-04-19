"""Steam Family service"""

import json
import os
from gettext import gettext as _

import requests

from lutris import settings
from lutris.services.base import SERVICE_LOGIN, AuthTokenExpiredError, OnlineService
from lutris.services.steam import SteamGame, SteamService
from lutris.util.log import logger
from lutris.util.steam.config import get_active_steamid64, get_steam_library


class SteamFamilyGame(SteamGame):
    service = "steamfamily"
    installer_slug = "steam"
    runner = "steam"

    @classmethod
    def new_from_steamfamily_game(cls, game):
        """Return a Steam Family game instance from an AppManifest"""
        game = cls.new_from_steam_game(game)
        game.service = cls.service
        return game


class SteamFamilyService(SteamService, OnlineService):
    """Service class for Steam Family sharing"""

    id = "steamfamily"
    name = _("Steam Family")
    description = _("Use for displaying every game in the Steam family")
    login_window_width = 500
    login_window_height = 850
    online = True
    requires_login_page = True
    game_class = SteamFamilyGame
    include_own_games = settings.STEAM_FAMILY_INCLUDE_OWN
    cookies_path = os.path.join(settings.CACHE_DIR, ".steam.auth")
    token_path = os.path.join(settings.CACHE_DIR, ".steam.token")
    cache_path = os.path.join(settings.CACHE_DIR, "steam-library.json")
    login_url = "https://store.steampowered.com/login/?redir=/about"
    redirect_uri = "https://store.steampowered.com/about"
    access_token_url = "https://store.steampowered.com/pointssummary/ajaxgetasyncconfig"
    library_url = "https://api.steampowered.com/IFamilyGroupsService/GetSharedLibraryApps/v1/"
    family_url = "https://api.steampowered.com/IFamilyGroupsService/GetFamilyGroupForUser/v1/"

    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/84.0.4147.38 Safari/537.36"
    )

    def __init__(self):
        super().__init__()
        self.session = requests.session()
        self.session.headers["User-Agent"] = self.user_agent
        self.access_token = self.load_access_token()

    def is_connected(self):
        return self.is_authenticated() and bool(self.load_access_token())

    def fetch_access_token(self):
        """Fetch the access token from the store, save to disk and set"""
        token_data = self.get_access_token()
        if not token_data:
            raise RuntimeError("Failed to get access token")
        with open(self.token_path, "w", encoding="utf-8") as token_file:
            token_file.write(json.dumps(token_data, indent=2))
        self.access_token = self.load_access_token()

    def load_access_token(self):
        """Load the access token from disk"""
        if not os.path.exists(self.token_path):
            return ""
        with open(self.token_path, encoding="utf-8") as token_file:
            token_data = json.load(token_file)
            return token_data.get("data").get("webapi_token", "")

    def get_access_token(self):
        """Request an access token from steam and return dump"""
        logger.debug("Requesting access token")
        response = self.session.get(
            self.access_token_url,
            cookies=self.load_cookies(),
        )
        response.raise_for_status()
        token_data = response.json()
        return token_data

    def login_callback(self, content):
        """Once the user logs in in a browser window, they're redirected to a
        an arbitrary page (about), then we redirect to a page containing the
        store access token which we can use to fetch family games"""
        logger.debug("Login to Steam store successful")
        self.fetch_access_token()
        SERVICE_LOGIN.fire(self)

    def get_family_groupid(self):
        """Get the user's family group id"""
        response = self.session.get(
            self.family_url, params={"access_token": self.load_access_token(), "steamid": get_active_steamid64()}
        )
        response.raise_for_status()
        resData = response.json()
        records = resData["response"]
        if not records["is_not_member_of_any_group"]:
            return records["family_groupid"]
        logger.error("User is not a member of any family group")
        return None

    def get_library(self):
        steamid = get_active_steamid64()
        if not steamid:
            logger.error("Unable to find SteamID from Steam config")
            return []
        response = self.session.get(
            self.library_url,
            params={
                "access_token": self.load_access_token(),
                "family_groupid": self.get_family_groupid(),
                "steamid": get_active_steamid64(),
            },
        )
        response.raise_for_status()
        resData = response.json()
        records = resData["response"]["apps"]
        if self.include_own_games:
            own_games = get_steam_library(steamid)
            ids = {game["appid"] for game in records}
            records.extend([game for game in own_games if game["appid"] not in ids])
        return records

    def load(self):
        """Load the list of games"""
        try:
            library = self.get_library()
        except Exception as ex:  # pylint=disable:broad-except
            logger.warning("Access Token expired, will attempt to get a new one")
            try:
                self.fetch_access_token()
                library = self.get_library()
            except:
                logger.warning("Failed to get a new access token")
                raise AuthTokenExpiredError("Access Token expired") from ex
        for steam_game in library:
            if steam_game["appid"] in self.excluded_appids:
                continue
            game = self.game_class.new_from_steamfamily_game(steam_game)
            game.save()
        self.match_games()
        return library
