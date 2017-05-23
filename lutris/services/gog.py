import os
import gi
from urllib.parse import urlencode, urlparse, parse_qsl
gi.require_version('GnomeKeyring', '1.0')
from gi.repository import GnomeKeyring
from lutris import settings
from lutris.util.http import Request
from lutris.util.log import logger
from lutris.util.cookies import WebkitCookieJar
from lutris.gui.dialogs import WebConnectDialog


NAME = "GOG"


class GogService:
    name = "GOG"
    root_url = 'https://www.gog.com'
    api_url = 'https://api.gog.com'

    client_id = "46899977096215655"
    client_secret = "9d85c43b1482497dbbce61f6e4aa173a433796eeae2ca8c5f6129f2dc4de46d9"
    redirect_uri = "https://embed.gog.com/on_login_success?origin=client"

    login_success_url = "https://www.gog.com/on_login_success"
    credentials_path = os.path.join(settings.CACHE_DIR, '.gog.auth')

    @property
    def login_url(self):
        params = {
            'client_id': self.client_id,
            'layout': 'client2',
            'redirect_uri': self.redirect_uri,
            'response_type': 'code'
        }
        return "https://auth.gog.com/auth?" + urlencode(params)

    def request_token(self, url):
        parsed_url = urlparse(url)
        response_params = dict(parse_qsl(parsed_url.query))
        if 'code' not in response_params:
            logger.error("code not received from GOG")
            return
        params = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
            'code': response_params['code'],
            'redirect_uri': self.redirect_uri
        }
        url = "https://auth.gog.com/token?" + urlencode(params)
        request = Request(url)
        request.get()
        return request.json

    def load_cookies(self):
        if not os.path.exists(self.credentials_path):
            logger.debug("No cookies found, please authenticate first")
            return
        cookiejar = WebkitCookieJar(self.credentials_path)
        cookiejar.load()
        return cookiejar

    def make_request(self, url):
        cookies = self.load_cookies()
        request = Request(url, cookies=cookies)
        request.get()
        return request.json

    def get_user_data(self):
        url = 'https://embed.gog.com/userData.json'
        return self.make_request(url)

    def get_library(self):
        url = self.root_url + '/account/getFilteredProducts?mediaType=1'
        return self.make_request(url)

    def get_game_details(self, product_id):
        url = '{}/products/{}?expand=downloads'.format(
            self.api_url,
            product_id
        )
        return self.make_request(url)

    def get_download_info(self, downlink):
        return self.make_request(downlink)

    def store_credentials(self, username, password):
        # See
        # https://bitbucket.org/kang/python-keyring-lib/src/8aadf61db38c70a5fe76fbe013df25fa62c03a8d/keyring/backends/Gnome.py?at=default # noqa
        attrs = GnomeKeyring.Attribute.list_new()
        GnomeKeyring.Attribute.list_append_string(attrs, 'username', username)
        GnomeKeyring.Attribute.list_append_string(attrs, 'password', password)
        GnomeKeyring.Attribute.list_append_string(attrs, 'application', 'Lutris')
        result = GnomeKeyring.item_create_sync(
            self.keyring_name, GnomeKeyring.ItemType.NETWORK_PASSWORD,
            "%s credentials for %s" % (self.name, username),
            attrs, password, True
        )[0]
        if result == GnomeKeyring.Result.CANCELLED:
            # XXX
            return False
        elif result != GnomeKeyring.Result.OK:
            # XXX
            return False


def is_connected():
    service = GogService()
    user_data = service.get_user_data()
    return user_data and 'username' in user_data


def connect(parent=None):
    service = GogService()
    dialog = WebConnectDialog(service, parent)
    dialog.run()


def get_games():
    service = GogService()
    #games = service.get_library()
    #with open('gog-games.json', 'w') as games_file:
    #    games_file.write(json.dumps(games, indent=2))
    #
    game_details = service.get_game_details("1430740694")
    for installer in game_details['downloads']['installers']:
        if installer['os'] == 'linux':
            from pprint import pprint
            pprint(installer)
            # for file in installer['files']:

            #     url = "https://www.gog.com/downlink/{}/{}".format(
            #         game_details['slug'],
            #         file['id']
            #     )
            #     print(service.get_download_info(url))
