import gi

gi.require_version("GnomeKeyring", "1.0")

from gi.repository import GnomeKeyring

KEYRING_NAME = "??"


def store_credentials(name, username, password):
    # See
    # https://bitbucket.org/kang/python-keyring-lib/src/8aadf61db38c70a5fe76fbe013df25fa62c03a8d/keyring/backends/Gnome.py?at=default # noqa
    attrs = GnomeKeyring.Attribute.list_new()
    GnomeKeyring.Attribute.list_append_string(attrs, "username", username)
    GnomeKeyring.Attribute.list_append_string(attrs, "password", password)
    GnomeKeyring.Attribute.list_append_string(attrs, "application", "Lutris")
    result = GnomeKeyring.item_create_sync(
        KEYRING_NAME,
        GnomeKeyring.ItemType.NETWORK_PASSWORD,
        "%s credentials for %s" % (name, username),
        attrs,
        password,
        True,
    )[0]
    if result == GnomeKeyring.Result.CANCELLED:
        # XXX
        return False
    elif result != GnomeKeyring.Result.OK:
        # XXX
        return False
