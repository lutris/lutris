"""Epic Games Store service"""
import json
import os
from gettext import gettext as _

import requests
from gi.repository import Gio

from lutris import settings
from lutris.config import LutrisConfig, write_game_config
from lutris.database.games import add_game, get_game_by_field
from lutris.database.services import ServiceGameCollection
from lutris.game import Game
from lutris.gui.widgets.utils import Image, paste_overlay, thumbnail_image
from lutris.installer import get_installers
from lutris.services.base import OnlineService
from lutris.services.service_game import ServiceGame
from lutris.services.service_media import ServiceMedia
from lutris.util import system
from lutris.util.egs.egs_launcher import EGSLauncher
from lutris.util.log import logger
from lutris.util.strings import slugify

EGS_GAME_ART_PATH = os.path.expanduser("~/.cache/lutris/egs/game_box")
EGS_GAME_BOX_PATH = os.path.expanduser("~/.cache/lutris/egs/game_box_tall")
EGS_LOGO_PATH = os.path.expanduser("~/.cache/lutris/egs/game_logo")
EGS_BANNERS_PATH = os.path.expanduser("~/.cache/lutris/egs/banners")
EGS_BOX_ART_PATH = os.path.expanduser("~/.cache/lutris/egs/boxart")
BANNER_SIZE = (316, 178)
BOX_ART_SIZE = (200, 267)


class DieselGameMedia(ServiceMedia):
    service = "egs"
    file_pattern = "%s.jpg"
    min_logo_x = 300
    min_logo_y = 150

    def _render_filename(self, filename):
        game_box_path = os.path.join(self.dest_path, filename)
        logo_path = os.path.join(EGS_LOGO_PATH, filename.replace(".jpg", ".png"))
        has_logo = os.path.exists(logo_path)
        thumb_image = Image.open(game_box_path)
        thumb_image = thumb_image.convert("RGBA")
        thumb_image = thumbnail_image(thumb_image, self.size)
        if has_logo:
            logo_image = Image.open(logo_path)
            logo_image = logo_image.convert("RGBA")
            logo_width, logo_height = logo_image.size
            if logo_width > self.min_logo_x:
                logo_image = logo_image.resize((self.min_logo_x, int(
                    logo_height * (self.min_logo_x / logo_width))), resample=Image.BICUBIC)
            elif logo_height > self.min_logo_y:
                logo_image = logo_image.resize(
                    (int(logo_width * (self.min_logo_y / logo_height)), self.min_logo_y), resample=Image.BICUBIC)
            thumb_image = paste_overlay(thumb_image, logo_image)
        thumb_path = os.path.join(self.dest_path, filename)
        thumb_image = thumb_image.convert("RGB")
        thumb_image.save(thumb_path)

    def get_media_url(self, detail):
        for image in detail.get("keyImages", []):
            if image["type"] == self.api_field:
                return image["url"] + "?w=%s&resize=1&h=%s" % (self.size[0], self.size[1])


class DieselGameBoxTall(DieselGameMedia):
    """EGS tall game box"""
    size = (200, 267)
    min_logo_x = 100
    min_logo_y = 100
    dest_path = os.path.join(settings.CACHE_DIR, "egs/game_box_tall")
    api_field = "DieselGameBoxTall"

    def render(self):
        for filename in os.listdir(self.dest_path):
            self._render_filename(filename)


class DieselGameBox(DieselGameBoxTall):
    """EGS game box"""
    size = (316, 178)
    min_logo_x = 300
    min_logo_y = 150
    dest_path = os.path.join(settings.CACHE_DIR, "egs/game_box")
    api_field = "DieselGameBox"


class DieselGameBoxLogo(DieselGameMedia):
    """EGS game box"""
    size = (200, 100)
    file_pattern = "%s.png"
    visible = False
    dest_path = os.path.join(settings.CACHE_DIR, "egs/game_logo")
    api_field = "DieselGameBoxLogo"


class EGSGame(ServiceGame):
    """Service game for Epic Games Store"""
    service = "egs"

    @classmethod
    def new_from_api(cls, egs_game):
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
    icon = "egs"
    online = True
    runner = "wine"
    client_installer = "epic-games-store-latest"
    medias = {
        "game_box": DieselGameBox,
        "box_tall": DieselGameBoxTall,
    }
    extra_medias = {
        "logo": DieselGameBoxLogo,
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
        self.session = requests.session()
        self.session.headers['User-Agent'] = self.user_agent
        if os.path.exists(self.token_path):
            with open(self.token_path) as token_file:
                self.session_data = json.loads(token_file.read())
        else:
            self.session_data = {}

    @property
    def http_basic_auth(self):
        return requests.auth.HTTPBasicAuth(
            '34a02cf8f4414e29b15921876da36f9a',
            'daafbccc737745039dffe53d94fc76cf'
        )

    def is_connected(self):
        return self.is_authenticated()

    def login_callback(self, content):
        """Once the user logs in in a browser window, Epic redirects
        to a page containing a Session ID which we can use to finish the authentication.
        Store session ID and exchange token to auth file"""
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

        self.start_session(response.json()['code'])
        self.emit("service-login")

    def resume_session(self):
        self.session.headers['Authorization'] = 'bearer %s' % self.session_data["access_token"]
        response = self.session.get('%s/account/api/oauth/verify' % self.oauth_url)
        if response.status_code >= 500:
            response.raise_for_status()

        response_content = response.json()
        if 'errorMessage' in response_content:
            raise RuntimeError(response_content)
        return response_content

    def start_session(self, exchange_code=None):
        if exchange_code:
            grant_type = 'exchange_code'
            token = exchange_code

        else:
            grant_type = 'refresh_token'
            token = self.session_data["refresh_token"]

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
        if 'error' in response_content:
            raise RuntimeError(response_content)
        with open(self.token_path, "w") as auth_file:
            auth_file.write(json.dumps(response_content, indent=2))
        self.session_data = response_content

    def get_game_details(self, asset):
        namespace = asset["namespace"]
        catalog_item_id = asset["catalogItemId"]
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
        # Merge the details with the initial asset to keep 'appName'
        asset.update(response.json()[catalog_item_id])
        return asset

    def get_library(self):
        self.resume_session()
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
            game_details = self.get_game_details(asset)
            games.append(game_details)
        return games

    def load(self):
        """Load the list of games"""
        if self.is_loading:
            logger.warning("EGS games are already loading")
            return
        self.is_loading = True
        try:
            library = self.get_library()
        except Exception as ex:  # pylint=disable:broad-except
            self.is_loading = False
            logger.error("Failed to load EGS library: %s", ex)
            return
        egs_games = []
        for game in library:
            egs_game = EGSGame.new_from_api(game)
            egs_game.save()
            egs_games.append(egs_game)
        self.is_loading = False
        return egs_games

    def install_from_egs(self, egs_game, manifest):
        """Create a new Lutris game based on an existing EGS install"""
        app_name = manifest["AppName"]
        logger.info("Installing %s", app_name)
        service_game = ServiceGameCollection.get_game("egs", app_name)
        if not service_game:
            logger.error("Can't find the game %s", app_name)
            return
        lutris_game_id = slugify(service_game["name"]) + "-" + self.id
        existing_game = get_game_by_field(lutris_game_id, "installer_slug")
        if existing_game:
            return
        game_config = LutrisConfig(game_config_id=egs_game["configpath"]).game_level
        game_config["game"]["args"] = get_launch_arguments(app_name)
        configpath = write_game_config(lutris_game_id, game_config)
        game_id = add_game(
            name=service_game["name"],
            runner=egs_game["runner"],
            slug=slugify(service_game["name"]),
            directory=egs_game["directory"],
            installed=1,
            installer_slug=lutris_game_id,
            configpath=configpath,
            service=self.id,
            service_id=app_name,
        )
        return game_id

    def add_installed_games(self):
        """Scan an existing EGS install for games"""
        egs_game = get_game_by_field("epic-games-store", "slug")
        if not egs_game:
            logger.error("EGS is not installed in Lutris")
            return

        egs_prefix = egs_game["directory"].split("drive_c")[0]
        logger.info("EGS detected in %s", egs_prefix)
        if not system.path_exists(os.path.join(egs_prefix, "drive_c")):
            logger.error("Invalid install of EGS at %s", egs_prefix)
            return
        egs_launcher = EGSLauncher(egs_prefix)
        for manifest in egs_launcher.iter_manifests():
            self.install_from_egs(egs_game, manifest)
        logger.debug("All EGS games imported")

    def generate_installer(self, db_game, egs_db_game):
        egs_game = Game(egs_db_game["id"])
        egs_exe = egs_game.config.game_config["exe"]
        if not os.path.isabs(egs_exe):
            egs_exe = os.path.join(egs_game.config.game_config["prefix"], egs_exe)
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
                        "executable": egs_exe,
                        "args": get_launch_arguments(db_game["appid"], "install"),
                        "prefix": egs_game.config.game_config["prefix"]
                    }}
                ]
            }
        }

    def install(self, db_game):
        egs_game = get_game_by_field(self.client_installer, "installer_slug")
        application = Gio.Application.get_default()
        if not egs_game or not egs_game["installed"]:
            installers = get_installers(
                game_slug=self.client_installer,
            )
            application.show_installer_window(installers)
        else:
            application.show_installer_window(
                [self.generate_installer(db_game, egs_game)],
                service=self,
                appid=db_game["appid"]
            )


def get_launch_arguments(app_name, action="launch"):
    return (
        "-opengl"
        " -SkipBuildPatchPrereq"
        " -com.epicgames.launcher://apps/%s?action=%s"
    ) % (app_name, action)
