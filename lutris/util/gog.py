import os
import gi
gi.require_version('GnomeKeyring', '1.0')
from gi.repository import GnomeKeyring
from lutris import settings
from lutris.util.http import Request
from lutris.util.log import logger
from lutris.util.cookies import WebkitCookieJar


class GogService:
    name = "GOG"
    root_url = 'https://www.gog.com'
    login_url = ("https://login.gog.com/auth?"
                 "client_id=46755278331571209"
                 "&layout=default"
                 "&redirect_uri=https%3A%2F%2Fwww.gog.com%2Fon_login_success"
                 "&response_type=code")
    login_success_url = "https://login.gog.com/account"
    credentials_path = os.path.join(settings.CACHE_DIR, '.gog.auth')

    def load_cookies(self):
        if not os.path.exists(self.credentials_path):
            logger.debug("No cookies found, please authenticate first")
            return
        cookiejar = WebkitCookieJar(self.credentials_path)
        cookiejar.load()
        return cookiejar

    def get_library(self):
        url = self.root_url + '/account/getFilteredProducts?mediaType=1'
        cookies = self.load_cookies()
        request = Request(url, cookies=cookies)
        request.get()
        return request.json

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
