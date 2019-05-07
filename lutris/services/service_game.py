"""Communicates between third party services games and Lutris games"""
from lutris import pga


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
        self.icon = None  # Game icon / logo
        self.details = None  # Additional details for the game

    @classmethod
    def new_from_lutris_id(cls, game_id):
        """Create a ServiceGame from its Lutris ID"""
        service_game = cls()
        service_game.game_id = game_id
        return service_game

    @property
    def config_id(self):
        """Returns the ID to use for the lutris config file"""
        return self.slug + "-" + self.installer_slug

    def install(self):
        """Add an installed game to the library"""
        self.game_id = pga.add_or_update(
            id=self.game_id,
            name=self.name,
            runner=self.runner,
            slug=self.slug,
            installed=1,
            configpath=self.config_id,
            installer_slug=self.installer_slug,
        )
        self.create_config()
        return self.game_id

    def uninstall(self):
        """Uninstall a game from Lutris"""
        return pga.add_or_update(id=self.game_id, installed=0)

    def create_config(self):
        """Implement this in subclasses to properly create the game config"""
        raise NotImplementedError
