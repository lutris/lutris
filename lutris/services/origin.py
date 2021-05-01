"""EA Origin service.
Not ready yet.
"""
import random
from gettext import gettext as _
from xml.etree import ElementTree

import requests

from lutris.services.base import OnlineService


class OriginService(OnlineService):
    """Service class for EA Origin"""

    id = "origin"
    name = _("Origin (WIP)")
    icon = "origin"

    def __init__(self):
        self.session = requests.session()

    @property
    def api_url(self):
        return "https://api%s.origin.com" % random.randint(1, 4)

    def get_access_token(self):
        """Request an access token from EA"""
        response = self.session.get(
            "https://accounts.ea.com/connect/auth",
            params={
                "client_id": "ORIGIN_JS_SDK",
                "response_type": "token",
                "redirect_uri": "nucleus:rest",
                "prompt": "none"
            }
        )
        response.raise_for_status()
        return response.json()

    def get_identity(self):
        """Request the user info"""
        response = self.session.get("https://gateway.ea.com/proxy/identity/pids/me")
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

    def get_library(self, user_id):
        """Request the user's library"""
        url = "%s/ecommerce2/consolidatedentitlements/%s?machine_hash=1" % (
            self.api_url,
            user_id
        )
        headers = {
            "Accept": "application/vnd.origin.v3+json; x-cache/force-write"
        }
        response = self.session.get(url, headers=headers)
        data = response.json()
        return data["entitlements"]
