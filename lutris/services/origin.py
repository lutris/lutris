"""EA Origin service.
Not ready yet.
"""
import json
import os
import random
from gettext import gettext as _
from xml.etree import ElementTree

import requests

from lutris import settings
from lutris.services.base import OnlineService
from lutris.services.service_media import ServiceMedia
from lutris.util.log import logger


class OriginGameBox(ServiceMedia):
    service = "origin"
    file_pattern = "%s.jpg"
    size = (256, 284)
    dest_path = os.path.join(settings.CACHE_DIR, "origin/game_box")
    api_field = "boxart"


class OriginService(OnlineService):
    """Service class for EA Origin"""

    id = "origin"
    name = _("Origin (WIP)")
    icon = "origin"
    online = True
    medias = {
        "game_box": OriginGameBox,
    }
    default_format = "game_box"
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

    def __init__(self):
        super().__init__()
        self.session = requests.session()

    @property
    def api_url(self):
        return "https://api%s.origin.com" % random.randint(1, 4)

    def login_callback(self, url):
        token = self.get_access_token()
        if not token:
            raise RuntimeError("Failed to get access token")
        with open(self.token_path, "w") as token_file:
            token_file.write(json.dumps(token, indent=2))
        self.emit("service-login")

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
            cookies=self.load_cookies
        )
        response.raise_for_status()
        token_data = response.json()
        if "error" in token_data:
            raise RuntimeError(
                "{} (Error code: {})".format(token_data["error"], token_data["error_number"])
            )
        return token_data

    def get_identity(self):
        """Request the user info"""
        response = self.session.get("https://gateway.ea.com/proxy/identity/pids/me", cookies=self.load_cookies())
        identity_data = response.json()
        user_id = identity_data["pid"]["pidId"]

        persona_id_response = self.session.get(
            "{}/atom/users?userIds={}".format(self.api_url, user_id)
        )
        content = persona_id_response.text()

        origin_account_info = ElementTree.fromstring(content)
        persona_id = origin_account_info.find("user").find("personaId").text
        user_name = origin_account_info.find("user").find("EAID").text
        return str(user_id), str(persona_id), str(user_name)

    def load(self):
        user_id, _persona_id, _user_name = self.get_identity()
        games = self.get_library(user_id)
        logger.debug(games)

    def get_library(self, user_id):
        """Request the user's library"""
        url = "{}/ecommerce2/consolidatedentitlements/{}?machine_hash=1".format(
            self.api_url,
            user_id
        )
        headers = {
            "Accept": "application/vnd.origin.v3+json; x-cache/force-write"
        }
        response = self.session.get(url, headers=headers)
        data = response.json()
        return data["entitlements"]

    def get_auth_headers(self, access_token):
        """Return headers needed to authenticate HTTP requests"""
        return {
            "Authorization": "Bearer %s" % access_token,
            "AuthToken": access_token,
            "X-AuthToken": access_token
        }
