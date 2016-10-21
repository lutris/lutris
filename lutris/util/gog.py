import os
import gi
gi.require_version('GnomeKeyring', '1.0')
from gi.repository import GnomeKeyring
from lutris import settings
from lutris.util.http import Request


class GogApi:
    root_url = 'https://www.gog.com'

    def login(self, username, password):
        request = Request(self.root_url)
        request.get()
        with open('response.html', 'wb') as response_file:
            response_file.write(request.content)
        print('ok')


class GogService:
    name = "GOG"
    login_url = "https://login.gog.com/login"
    login_success_url = "https://login.gog.com/account"
    credentials_path = os.path.join(settings.CACHE_DIR, '.gog.auth')

    def __init__(self):
        self.api = GogApi()

    def login(self, username, password):
        self.api.login(username, password)

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
