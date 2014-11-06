from lutris.external.humblebundle import HumbleApi
from gi.repository import GnomeKeyring


class Client(object):
    keyring_name = None

    def __init__(self, login, password):
        self.api = HumbleApi()
        self.api.login(login, password)

    def store_credentials(self, username, password):
        # See https://bitbucket.org/kang/python-keyring-lib/src/8aadf61db38c70a5fe76fbe013df25fa62c03a8d/keyring/backends/Gnome.py?at=default
        service = "HumbleBundle"
        attrs = GnomeKeyring.Attribute.list_new()
        GnomeKeyring.Attribute.list_append_string(attrs, 'username', username)
        GnomeKeyring.Attribute.list_append_string(attrs, 'password', password)
        GnomeKeyring.Attribute.list_append_string(attrs, 'application',
                                                  'Lutris')
        result = GnomeKeyring.item_create_sync(
            self.keyring_name, GnomeKeyring.ItemType.NETWORK_PASSWORD,
            "%s credentials for %s" % (service, username),
            attrs, password, True
        )[0]
        if result == GnomeKeyring.Result.CANCELLED:
            # XXX
            return False
        elif result != GnomeKeyring.Result.OK:
            # XXX
            return False

    def _get_gamekeys(self):
        return self.api.get_gamekeys()

    def get_order(self, gamekey):
        return self.api.get_order(gamekey)
