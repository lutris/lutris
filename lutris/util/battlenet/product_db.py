"""Custom protobuf decoder for Battle.net product.db

Replaces the google-protobuf dependency with a lightweight decoder
using the same pattern as lutris.util.amazon.protobuf_decoder.
Only the fields actually used by BlizzardProductDbParser are defined.
"""

from lutris.util.amazon.protobuf_decoder import (
    Message,
    PrimativeType,
    type_bool,
)


class type_utf8_string(PrimativeType):
    """String type that decodes bytes to UTF-8, unlike the Amazon
    type_string which returns raw bytes."""

    wire_type = 2

    @staticmethod
    def decode(data):
        return data.decode("utf-8")


class BaseProductState(Message):
    installed = None
    playable = None
    current_version_str = None

    def __init__(self):
        self.__lookup__ = [
            ("optional", type_bool, "installed", 1),
            ("optional", type_bool, "playable", 2),
            ("optional", type_utf8_string, "current_version_str", 7),
        ]


class CachedProductState(Message):
    base_product_state = None

    def __init__(self):
        self.__lookup__ = [
            ("optional", BaseProductState, "base_product_state", 1),
        ]


class UserSettings(Message):
    install_path = None
    play_region = None

    def __init__(self):
        self.__lookup__ = [
            ("optional", type_utf8_string, "install_path", 1),
            ("optional", type_utf8_string, "play_region", 2),
        ]


class ProductInstall(Message):
    uid = None
    product_code = None
    settings = None
    cached_product_state = None

    def __init__(self):
        self.__lookup__ = [
            ("optional", type_utf8_string, "uid", 1),
            ("optional", type_utf8_string, "product_code", 2),
            ("optional", UserSettings, "settings", 3),
            ("optional", CachedProductState, "cached_product_state", 4),
        ]


class ProductDb(Message):
    product_installs = None

    def __init__(self):
        self.__lookup__ = [
            ("repeated", ProductInstall, "product_installs", 1),
        ]
