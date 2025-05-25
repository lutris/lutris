# Copyright (C) 2013-2017 Oliver Ainsworth
# Original source: https://github.com/serverstf/python-valve

"""Provides utilities for representing SteamIDs
See: https://developer.valvesoftware.com/wiki/SteamID
"""

import re
import urllib.parse
import warnings

UNIVERSE_INDIVIDUAL = 0  #:
UNIVERSE_PUBLIC = 1  #:
UNIVERSE_BETA = 2  #:
UNIVERSE_INTERNAL = 3  #:
UNIVERSE_DEV = 4  #:
UNIVERSE_RC = 5  #:

UNIVERSES = [
    UNIVERSE_INDIVIDUAL,
    UNIVERSE_PUBLIC,
    UNIVERSE_BETA,
    UNIVERSE_INTERNAL,
    UNIVERSE_DEV,
    UNIVERSE_RC,
]

TYPE_INVALID = 0  #:
TYPE_INDIVIDUAL = 1  #:
TYPE_MULTISEAT = 2  #:
TYPE_GAME_SERVER = 3  #:
TYPE_ANON_GAME_SERVER = 4  #:
TYPE_PENDING = 5  #:
TYPE_CONTENT_SERVER = 6  #:
TYPE_CLAN = 7  #:
TYPE_CHAT = 8  #:
TYPE_P2P_SUPER_SEEDER = 9  #:
TYPE_ANON_USER = 10  #:

ACCOUNT_TYPES = [
    TYPE_INVALID,
    TYPE_INDIVIDUAL,
    TYPE_MULTISEAT,
    TYPE_GAME_SERVER,
    TYPE_ANON_GAME_SERVER,
    TYPE_PENDING,
    TYPE_CONTENT_SERVER,
    TYPE_CLAN,
    TYPE_CHAT,
    TYPE_P2P_SUPER_SEEDER,
    TYPE_ANON_USER,
]

TYPE_LETTER_MAP = {
    TYPE_INDIVIDUAL: "U",
    TYPE_CLAN: "g",
    TYPE_CHAT: "T",
}
LETTER_TYPE_MAP = {v: k for k, v in TYPE_LETTER_MAP.items()}

TYPE_URL_PATH_MAP = {
    TYPE_INDIVIDUAL: ["profiles", "id"],
    TYPE_CLAN: ["groups", "gid"],
}

TEXTUAL_ID_REGEX = re.compile(r"^STEAM_(?P<X>\d+):(?P<Y>\d+):(?P<Z>\d+)$")
COMMUNITY32_REGEX = re.compile(
    r".*/(?P<path>{paths})/\[(?P<type>[{type_chars}]):1:(?P<steamid>\d+)\]$".format(
        paths="|".join("|".join(paths) for paths in TYPE_URL_PATH_MAP.values()),
        type_chars="".join(c for c in TYPE_LETTER_MAP.values()),
    )
)
COMMUNITY64_REGEX = re.compile(
    r".*/(?P<path>{paths})/(?P<steamid>\d+)$".format(
        paths="|".join("|".join(paths) for paths in TYPE_URL_PATH_MAP.values())
    )
)


class SteamIDError(ValueError):
    """Raised when parsing or building invalid SteamIDs"""


class SteamID:
    """Represents a SteamID

    A SteamID is broken up into four components: a 32 bit account number,
    a 20 bit "instance" identifier, a 4 bit account type and an 8 bit
    "universe" identifier.

    There are 10 known accounts types as listed below. Generally you won't
    encounter types other than "individual" and "group".

    +----------------+---------+---------------+---------------------------+
    | Type           | Numeric | Can be mapped | Constant                  |
    |                | value   | to URL        |                           |
    +================+=========+===============+===========================+
    | Invalid        | 0       | No            | ``TYPE_INVALID``          |
    +----------------+---------+---------------+---------------------------+
    | Individual     | 1       | Yes           | ``TYPE_INDIVIDUAL``       |
    +----------------+---------+---------------+---------------------------+
    | Multiseat      | 2       | No            | ``TYPE_MULTISEAT``        |
    +----------------+---------+---------------+---------------------------+
    | Game server    | 3       | No            | ``TYPE_GAME_SERVER``      |
    +----------------+---------+---------------+---------------------------+
    | Anonymous game | 4       | No            | ``TYPE_ANON_GAME_SERVER`` |
    | server         |         |               |                           |
    +----------------+---------+---------------+---------------------------+
    | Pending        | 5       | No            | ``TYPE_PENDING``          |
    +----------------+---------+---------------+---------------------------+
    | Content server | 6       | No            | ``TYPE_CONTENT_SERVER``   |
    +----------------+---------+---------------+---------------------------+
    | Group          | 7       | Yes           | ``TYPE_CLAN``             |
    +----------------+---------+---------------+---------------------------+
    | Chat           | 8       | No            | ``TYPE_CHAT``             |
    +----------------+---------+---------------+---------------------------+
    | "P2P Super     | 9       | No            | ``TYPE_P2P_SUPER_SEEDER`` |
    | Seeder"        |         |               |                           |
    +----------------+---------+---------------+---------------------------+
    | Anonymous user | 10      | No            | ``TYPE_ANON_USER``        |
    +----------------+---------+---------------+---------------------------+


    ``TYPE_``-prefixed constants are provided by the :mod:`valve.steam.id`
    module for the numerical values of each type.

    All SteamIDs can be represented textually as well as by their numerical
    components. This is typically in the STEAM_X:Y:Z form where X, Y, Z are
    the "universe", "instance" and the account number respectively. There are
    two special cases however. If the account type if invalid then "UNKNOWN"
    is the textual representation. Similarly "STEAM_ID_PENDING" is used when
    the type is pending.

    As well as the the textual representation of SteamIDs there are also the
    64 and 32 bit versions which contain the SteamID components encoded into
    integers of corresponding width. However the 32-bit representation also
    includes a letter to indicate account type.
    """

    #: Used for building community URLs
    base_community_url = "http://steamcommunity.com/"

    @classmethod
    def from_community_url(cls, steam_id, universe=UNIVERSE_INDIVIDUAL):
        """Parse a Steam community URL into a :class:`.SteamID` instance

        This takes a Steam community URL for a profile or group and converts
        it to a SteamID. The type of the ID is infered from the type character
        in 32-bit community urls (``[U:1:1]`` for example) or from the URL path
        (``/profile`` or ``/groups``) for 64-bit URLs.

        As there is no way to determine the universe directly from
        URL it must be expliticly set, defaulting to
        :data:`UNIVERSE_INDIVIDUAL`.

        Raises :class:`.SteamIDError` if the URL cannot be parsed.
        """

        url = urllib.parse.urlparse(steam_id)
        match = COMMUNITY32_REGEX.match(url.path)
        if match:
            if match.group("path") not in TYPE_URL_PATH_MAP[LETTER_TYPE_MAP[match.group("type")]]:
                warnings.warn("Community URL ({}) path doesn't match type character".format(url.path))
            steamid = int(match.group("steamid"))
            instance = steamid & 1
            account_number = (steamid - instance) / 2
            return cls(account_number, instance, LETTER_TYPE_MAP[match.group("type")], universe)
        match = COMMUNITY64_REGEX.match(url.path)
        if match:
            steamid = int(match.group("steamid"))
            instance = steamid & 1
            if match.group("path") in TYPE_URL_PATH_MAP[TYPE_INDIVIDUAL]:
                account_number = cls.get_account_number_from_steamid(steamid)
                account_type = TYPE_INDIVIDUAL
            elif match.group("path") in TYPE_URL_PATH_MAP[TYPE_CLAN]:
                account_number = (steamid - instance - 0x0170000000000000) / 2
                account_type = TYPE_CLAN
            return cls(account_number, instance, account_type, universe)
        raise SteamIDError("Invalid Steam community URL ({})".format(url))

    @classmethod
    def from_steamid64(cls, steamid, account_type=TYPE_INDIVIDUAL, universe=UNIVERSE_INDIVIDUAL):
        """Create an instance of SteamID from a SteamID64. Only for normal user accounts."""
        instance = steamid & 1
        account_number = cls.get_account_number_from_steamid(steamid)
        return cls(account_number, instance, account_type, universe)

    @staticmethod
    def get_account_number_from_steamid(steamid):
        """Return account number from 64bit SteamID. For individuals only."""
        instance = steamid & 1
        return (steamid - instance - 0x0110000100000000) / 2

    @classmethod
    def from_text(cls, steam_id, account_type=TYPE_INDIVIDUAL):
        """Parse a SteamID in the STEAM_X:Y:Z form

        Takes a teaxtual SteamID in the form STEAM_X:Y:Z and returns
        a corresponding :class:`.SteamID` instance. The X represents the
        account's 'universe,' Z is the account number and Y is either 1 or 0.

        As the account type cannot be directly inferred from the SteamID
        it must be explicitly specified, defaulting to :data:`TYPE_INDIVIDUAL`.

        The two special IDs ``STEAM_ID_PENDING`` and ``UNKNOWN`` are also
        handled returning SteamID instances with the appropriate
        types set (:data:`TYPE_PENDING` and :data:`TYPE_INVALID` respectively)
        and with all other components of the ID set to zero.
        """

        if steam_id == "STEAM_ID_PENDING":
            return cls(0, 0, TYPE_PENDING, 0)
        if steam_id == "UNKNOWN":
            return cls(0, 0, TYPE_INVALID, 0)
        match = TEXTUAL_ID_REGEX.match(steam_id)
        if not match:
            raise SteamIDError("ID '{}' doesn't match format {}".format(steam_id, TEXTUAL_ID_REGEX.pattern))
        return cls(int(match.group("Z")), int(match.group("Y")), account_type, int(match.group("X")))

    def __init__(self, account_number, instance, account_type, universe):
        if universe not in UNIVERSES:
            raise SteamIDError("Invalid universe {}".format(universe))
        if account_type not in ACCOUNT_TYPES:
            raise SteamIDError("Invalid type {}".format(account_type))
        if account_number < 0 or account_number > (2**32) - 1:
            raise SteamIDError("Account number ({}) out of range".format(account_number))
        if instance not in [1, 0]:
            raise SteamIDError("Expected instance to be 1 or 0, got {}".format(instance))
        self.account_number = int(account_number)  # Z
        self.instance = instance  # Y
        self.account_type = account_type
        self.universe = universe  # X

    @property
    def type_name(self):
        """The account type as a string"""

        return {v: k for k, v in globals().iteritems() if k.startswith("TYPE_")}.get(
            self.account_type, self.account_type
        )

    def __str__(self):
        """The textual representation of the SteamID

        This is in the STEAM_X:Y:Z form and can be parsed by :meth:`.from_text`
        to produce an equivalent :class:`.` instance. Alternately
        ``STEAM_ID_PENDING`` or ``UNKNOWN`` may be returned if the account
        type is :data:`TYPE_PENDING` or :data:`TYPE_INVALID` respectively.

        .. note::
            :meth:`.from_text` will still handle the ``STEAM_ID_PENDING`` and
            ``UNKNOWN`` cases.
        """

        if self.account_type == TYPE_PENDING:
            return "STEAM_ID_PENDING"
        if self.account_type == TYPE_INVALID:
            return "UNKNOWN"
        return "STEAM_{}:{}:{}".format(self.universe, self.instance, self.account_number)

    def __int__(self):
        """The 64 bit representation of the SteamID

        64 bit SteamIDs are only valid for those with the type
        :data:`TYPE_INDIVIDUAL` or :data:`TYPE_CLAN`. For all other types
        :class:`.SteamIDError` will be raised.

        The 64 bit representation is calculated by multiplying the account
        number by two then adding the "instance" and then adding another
        constant which varies based on the account type.

        For :data:`TYPE_INDIVIDUAL` the constant is ``0x0110000100000000``,
        whereas for :data:`TYPE_CLAN` it's ``0x0170000000000000``.
        """

        if self.account_type == TYPE_INDIVIDUAL:
            return (self.account_number * 2) + 0x0110000100000000 + self.instance
        if self.account_type == TYPE_CLAN:
            return (self.account_number * 2) + 0x0170000000000000 + self.instance
        raise SteamIDError("Cannot create 64-bit identifier for SteamID with type {}".format(self.type_name))

    def __eq__(self, other):
        try:
            return (
                self.account_number == other.account_number
                and self.instance == other.instance
                and self.account_type == other.type
                and self.universe == other.universe
            )
        except AttributeError:
            return False  # Should probably raise TypeError

    def __ne__(self, other):
        return not self == other

    def as_32(self):
        """Returns the 32 bit community ID as a string

        This is only applicable for :data:`TYPE_INDIVIDUAL`,
        :data:`TYPE_CLAN` and :data:`TYPE_CHAT` types. For any other types,
        attempting to generate the 32-bit representation will result in
        a :class:`.SteamIDError` being raised.
        """

        try:
            return "[{}:1:{}]".format(TYPE_LETTER_MAP[self.account_type], self.get_32_bit_community_id())
        except KeyError as ex:
            raise SteamIDError(
                "Cannot create 32-bit indentifier for SteamID with type {}".format(self.type_name)
            ) from ex

    def get_32_bit_community_id(self):
        return (self.account_number * 2) + self.instance

    def as_64(self):
        """Returns the 64 bit representation as a string

        This is only possible if the ID type is :data:`TYPE_INDIVIDUAL` or
        :data:`TYPE_CLAN`, otherwise :class:`.SteamIDError` is raised.
        """

        return str(int(self))

    def community_url(self, id64=True):
        """Returns the full URL to the Steam Community page for the SteamID

        This can either be generate a URL from the 64 bit representation
        (the default) or the 32 bit one. Generating community URLs is only
        supported for IDs of type :data:`TYPE_INDIVIDUAL` and
        :data:`TYPE_CLAN`. Attempting to generate a URL for any other type
        will result in a :class:`.SteamIDError` being raised.
        """

        path_func = self.as_64 if id64 else self.as_32
        try:
            return urllib.parse.urljoin(
                self.base_community_url, "/".join((TYPE_URL_PATH_MAP[self.account_type][0], path_func()))
            )
        except KeyError as ex:
            raise SteamIDError("Cannot generate community URL for type {}".format(self.type_name)) from ex
