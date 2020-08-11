"""Communicates between third party services games and Lutris games"""
from lutris.database.games import add_or_update
from lutris.util.strings import slugify


class ServiceGame:

    """Representation of a game from a 3rd party service"""

    store = NotImplemented
    installer_slug = NotImplemented

    def __init__(self):
        self.appid = None  # External ID of the game on the 3rd party service
        self.game_id = None  # Internal Lutris ID
        self.runner = None  # Name of the runner
        self.name = None  # Name
        self.slug = None  # Game slug
        self.logo = None  # Game logo
        self.icon = None  # Game icon
        self.details = None  # Additional details for the game

    @property
    def config_id(self):
        """Returns the ID to use for the lutris config file"""
        return self.slug + "-" + self.installer_slug

    @property
    def steamid(self):
        """Return the SteamID, this is a special case since Steam's appid's are
        a field in the game table. Keeping this here allows to reuse the install method.
        """
        if hasattr(self, "appid") and self.runner and "steam" in self.runner:
            return int(self.appid)
        return None

    def install(self, updated_info=None):
        """Add an installed game to the library

        Params:
            updated_info (dict): Optional dictonary containing existing data not to overwrite
        """
        if updated_info:
            name = updated_info["name"]
            slug = updated_info["slug"]
        else:
            name = self.name
            slug = self.slug
        self.game_id = add_or_update(
            id=self.game_id,
            name=name,
            runner=self.runner,
            slug=slug,
            steamid=self.steamid,
            installed=1,
            configpath=self.config_id,
            installer_slug=self.installer_slug,
        )
        self.create_config()
        return self.game_id

    def uninstall(self):
        """Uninstall a game from Lutris"""
        return add_or_update(id=self.game_id, installed=0)

    def create_config(self):
        """Implement this in subclasses to properly create the game config"""

    def as_dict(self):
        """Return the data in a format compatible with lutris views"""
        return {
            "id": self.appid,
            "name": self.name,
            "slug": self.slug or slugify(self.name),
            "runner": self.runner,
            "steamid": self.steamid,
            "installed": 1,
            "year": None,
            "platform": None,
            "lastplayed": None,
            "installed_at": None,
            "playtime": None,
            "icon": self.icon,
        }
