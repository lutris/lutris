import os
import gi
import json
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
    login_url = ("https://login.gog.com/auth?"
                 "client_id={}"
                 "&layout=default"
                 "&redirect_uri=https%3A%2F%2Fwww.gog.com%2Fon_login_success"
                 "&response_type=code".format(client_id))
    login_success_url = "https://www.gog.com/on_login_success"
    credentials_path = os.path.join(settings.CACHE_DIR, '.gog.auth')

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
        print(request.response_headers)
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
    game_details = service.get_game_details("1207659142")
    for installer in game_details['downloads']['installers']:
        if installer['os'] == 'linux':
            for file in installer['files']:
                url = "https://www.gog.com/downlink/{}/{}".format(
                    game_details['slug'],
                    file['id']
                )
                print(service.get_download_info(url))
