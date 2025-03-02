"""Epic Games Store service"""

import json
import os
from gettext import gettext as _
from typing import Any, Dict, Optional

import requests

from lutris import settings
from lutris.services.base import SERVICE_LOGIN, AuthTokenExpiredError, OnlineService
from lutris.util.log import logger
from lutris.services.steam import SteamGame, SteamService
from lutris.util.steam.config import get_active_steamid64
from lutris.database.services import ServiceGameCollection

STEAM_INSTALLER = "steam-wine"  # Lutris installer used to setup the Steam client

class SteamFamilyGame(SteamGame):
    service = "steamfamily"
    installer_slug = "steam"
    runner = "steam"


class SteamFamilyService(SteamService, OnlineService):
    """Service class for Epic Games Store"""

    id = "steamfamily"
    name = _("Steam Family")
    description = _("Use for displaying every game in the Steam family")
    login_window_width = 500
    login_window_height = 850
    online = True
    requires_login_page = True
    cookies_path = os.path.join(settings.CACHE_DIR, ".steam.auth")
    token_path = os.path.join(settings.CACHE_DIR, ".steam.token")
    cache_path = os.path.join(settings.CACHE_DIR, "steam-library.json")
    login_url = "https://store.steampowered.com/login/?redir="
    redirect_uri = "https://store.steampowered.com/"
    library_url = "https://api.steampowered.com/IFamilyGroupsService/GetSharedLibraryApps/v1/"
    family_url = "https://api.steampowered.com/IFamilyGroupsService/GetFamilyGroupForUser/v1/"

    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/84.0.4147.38 Safari/537.36"
    )

    def __init__(self):
        super().__init__()
        logger.debug(f"STEAM FAMILY INIT, conn:{self.is_connected()}, cachepath:{self.cache_path}, accesstoken:{self.load_access_token()}")
        self.session = requests.session()
        self.session.headers["User-Agent"] = self.user_agent
        self.access_token = self.load_access_token()

    def is_connected(self):
        return self.is_authenticated() and bool(self.load_access_token())

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
            return token_data.get("data").get("webapi_token", "")

    def get_access_token(self):
        """Request an access token from steam"""
        logger.debug("Requesting access token")
        response = self.session.get(
            "https://store.steampowered.com/pointssummary/ajaxgetasyncconfig",
            #params={},
            cookies=self.load_cookies(),
        )
        response.raise_for_status()
        token_data = response.json()
        logger.debug(f"TOKEN DATA {token_data}")
        return token_data

    def login_callback(self, content):
        """Once the user logs in in a browser window, Epic redirects
        to a page containing a Session ID which we can use to finish the authentication.
        Store session ID and exchange token to auth file"""
        logger.debug("Login to Steam store successful")
        logger.debug(content)
        self.fetch_access_token()
        SERVICE_LOGIN.fire(self)

    def get_family_groupid(self):
        """Get the user's family group id"""
        response = self.session.get(self.family_url, params={"access_token": self.load_access_token(),
                                                              "steamid": get_active_steamid64()})
        response.raise_for_status()
        resData = response.json()
        records = resData["response"]
        if not records["is_not_member_of_any_group"]:
            return records["family_groupid"]
        logger.error("User is not a member of any family group")
        return None

    def get_library(self):
        response = self.session.get(self.library_url, params={"access_token": self.load_access_token(),
                                                              "family_groupid": self.get_family_groupid(),
                                                              "steamid": get_active_steamid64()})
        response.raise_for_status()
        resData = response.json()
        records = resData["response"]["apps"]
        return records

    def load(self):
        """Load the list of games"""
        logger.debug("STEAMFAMILY GAME CLASS {}".format(self.game_class))
        try:
            library = self.get_library()
        except Exception as ex:  # pylint=disable:broad-except
            logger.warning("Access Token expired")
            raise AuthTokenExpiredError("Access Token expired") from ex
        for steam_game in library:
            if (steam_game["appid"] in self.excluded_appids) or (steam_game["app_type"] == 4): # Skip SDKs
                continue
            game = self.game_class.new_from_steam_game(steam_game)
            game.save()
        logger.debug("LIBRARY: {}".format(ServiceGameCollection.get_for_service(self.id)))
        self.match_games()
        return library
