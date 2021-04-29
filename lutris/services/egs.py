"""Epic Games Store service.
Not ready yet.
"""
import json
import os
from gettext import gettext as _

import requests

from lutris import settings
from lutris.gui.dialogs.webconnect_dialog import WebConnectDialog
from lutris.services.base import OnlineService
from lutris.services.service_game import ServiceGame
from lutris.services.service_media import ServiceMedia
from lutris.util.log import logger
from lutris.util.strings import slugify


class DieselGameBoxTall(ServiceMedia):
    """EGS icon"""
    service = "egs"
    size = (255, 340)
    dest_path = os.path.join(settings.CACHE_DIR, "egs/game_box_tall")
    file_pattern = "%s"
    api_field = "DieselGameBoxTall"


class EGSGame(ServiceGame):
    """Service game for Epic Games Store"""
    service = "egs"

    @classmethod
    def new_from_api(cls, egs_game):
        """Convert an EGS game to a service game"""
        service_game = cls()
        service_game.appid = egs_game["id"]
        service_game.slug = slugify(egs_game["title"])
        service_game.name = egs_game["title"]
        service_game.details = json.dumps(egs_game)
        return service_game


class EpicGamesStoreService(OnlineService):
    """Service class for Epic Games Store"""

    id = "egs"
    name = _("Epic Games Store")
    icon = "egs"
    online = True
    medias = {
        "box_tall": DieselGameBoxTall,
    }
    default_format = "box_tall"
    requires_login_page = True
    cookies_path = os.path.join(settings.CACHE_DIR, ".egs.auth")
    token_path = os.path.join(settings.CACHE_DIR, ".egs.token")
    cache_path = os.path.join(settings.CACHE_DIR, "egs-library.json")
    login_url = "https://www.epicgames.com/id/login?redirectUrl=https://www.epicgames.com/id/api/redirect"
    redirect_uri = "https://www.epicgames.com/id/api/redirect"
    launcher_url = "https://launcher-public-service-prod06.ol.epicgames.com"
    oauth_url = 'https://account-public-service-prod03.ol.epicgames.com'
    catalog_url = 'https://catalog-public-service-prod06.ol.epicgames.com'
    is_loading = False

    user_agent = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'EpicGamesLauncher/11.0.1-14907503+++Portal+Release-Live '
        'UnrealEngine/4.23.0-14907503+++Portal+Release-Live '
        'Chrome/84.0.4147.38 Safari/537.36'
    )

    def __init__(self):
        super().__init__()
        self.session = None

    @property
    def http_basic_auth(self):
        return requests.auth.HTTPBasicAuth(
            '34a02cf8f4414e29b15921876da36f9a',
            'daafbccc737745039dffe53d94fc76cf'
        )

    @property
    def exchange_code(self):
        if not os.path.exists(self.token_path):
            return ''
        with open(self.token_path) as auth_file:
            content = json.loads(auth_file.read())
        return content.get('exchange_code')

    @property
    def refresh_token(self):
        if not os.path.exists(self.token_path):
            return ''
        with open(self.token_path) as auth_file:
            content = json.loads(auth_file.read())
        return content.get('refresh_token')

    def write_refresh_token(self, refresh_token):
        with open(self.token_path) as auth_file:
            content = json.loads(auth_file.read())
        content["refresh_token"] = refresh_token
        with open(self.token_path, "w") as auth_file:
            auth_file.write(json.dumps(content))

    def login(self, parent=None):
        logger.debug("Connecting to EGS")
        dialog = WebConnectDialog(self, parent)
        dialog.set_modal(True)
        dialog.show()

    def is_connected(self):
        return self.is_authenticated()

    def login_callback(self, content):
        """Store session ID and exchange token to auth file"""
        logger.debug("Login to EGS successful")
        logger.debug(content)
        content_json = json.loads(content.decode())
        session_id = content_json["sid"]
        _session = requests.session()
        _session.headers.update({
            'X-Epic-Event-Action': 'login',
            'X-Epic-Event-Category': 'login',
            'X-Epic-Strategy-Flags': '',
            'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': self.user_agent
        })
        _session.get('https://www.epicgames.com/id/api/set-sid', params={'sid': session_id})
        _session.get('https://www.epicgames.com/id/api/csrf')
        response = _session.post(
            'https://www.epicgames.com/id/api/exchange/generate',
            headers={'X-XSRF-TOKEN': _session.cookies['XSRF-TOKEN']}
        )

        if response.status_code != 200:
            logger.error("Failed to connec to EGS (Status %s): %s", response.status_code, response.json())
            return
        logger.debug("received %s", response.json())
        credentials = {
            'session_id': session_id,
            'exchange_code': response.json()['code']
        }
        with open(self.token_path, "w") as auth_file:
            auth_file.write(json.dumps(credentials))
        self.emit("service-login")

    def oauth_verify(self, access_token):
        self.session.headers['Authorization'] = 'bearer %s' % access_token
        response = self.session.get('%s/account/api/oauth/verify' % self.oauth_url)
        if response.status_code >= 500:
            response.raise_for_status()

        response_content = response.json()
        if 'errorMessage' in response_content:
            raise RuntimeError(response_content)
        logger.debug(response_content)
        return response_content

    def start_session(self):
        self.session = requests.session()
        self.session.headers['User-Agent'] = self.user_agent
        if self.refresh_token:
            grant_type = 'refresh_token'
            token = self.refresh_token
        else:
            grant_type = 'exchange_code'
            token = self.exchange_code
        response = self.session.post(
            'https://account-public-service-prod03.ol.epicgames.com/account/api/oauth/token',
            data={
                'grant_type': grant_type,
                grant_type: token,
                'token_type': 'eg1'
            },
            auth=self.http_basic_auth
        )
        if response.status_code >= 500:
            response.raise_for_status()

        response_content = response.json()
        logger.debug(response_content)
        if 'error' in response_content:
            raise RuntimeError(response_content)
        self.oauth_verify(response_content["access_token"])
        self.write_refresh_token(response_content["access_token"])

    def get_game_details(self, namespace, catalog_item_id):
        response = self.session.get(
            '%s/catalog/api/shared/namespace/%s/bulk/items' % (self.catalog_url, namespace),
            params={
                "id": catalog_item_id,
                "includeDLCDetails": True,
                "includeMainGameDetails": True,
                "country": "US",
                "locale": "en"
            }
        )
        response.raise_for_status()
        return response.json()[catalog_item_id]

    def get_library(self):
        self.start_session()
        response = self.session.get(
            '%s/launcher/api/public/assets/Windows' % self.launcher_url,
            params={'label': 'Live'}
        )
        response.raise_for_status()
        assets = response.json()
        games = []
        for asset in assets:
            if asset["namespace"] == "ue":
                continue
            game_details = self.get_game_details(asset["namespace"], asset["catalogItemId"])
            games.append(game_details)
        return games

    def load(self):
        """Load the list of games"""
        if self.is_loading:
            logger.warning("EGS games are already loading")
            return
        self.is_loading = True
        self.emit("service-games-load")
        library = self.get_library()
        egs_games = []
        for game in library:
            egs_games.append(EGSGame.new_from_api(game))
        self.is_loading = False
        self.emit("service-games-loaded")
        return egs_games
