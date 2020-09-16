"""Communicates between third party services games and Lutris games"""
import os

from lutris import settings
from lutris.database import sql
from lutris.database.games import add_or_update
from lutris.util import system
from lutris.util.http import download_file
from lutris.util.strings import slugify

PGA_DB = settings.PGA_DB


class ServiceMedia:
    """Information about the service's media format"""
    size = NotImplemented
    small_size = None
    dest_path = NotImplemented
    file_pattern = None
    api_field = NotImplemented
    url_pattern = "%s"

    def get_absolute_path(self, slug):
        return os.path.join(self.dest_path, self.file_pattern % slug)

    def exists(self, slug):
        """Whether the icon for the specified slug exists locally"""
        return system.path_exists(self.get_absolute_path(slug))

    def get_url(self, service_game):
        return self.url_pattern % service_game[self.api_field]

    def download(self, service_game):
        """Downloads the banner if not present"""
        if not system.path_exists(self.dest_path):
            os.makedirs(self.dest_path)
        url = self.get_url(service_game)
        if self.file_pattern:
            image_filename = self.file_pattern % service_game.slug
        image_filename = url.split("/")[-1]
        cache_path = os.path.join(self.dest_path, image_filename)
        if not system.path_exists(cache_path):
            download_file(url, cache_path)
        return cache_path


class ServiceGame:

    """Representation of a game from a 3rd party service"""

    service = NotImplemented
    installer_slug = NotImplemented
    medias = (ServiceMedia, )

    def __init__(self):
        self.appid = None  # External ID of the game on the 3rd party service
        self.game_id = None  # Internal Lutris ID
        self.runner = None  # Name of the runner
        self.name = None  # Name
        self.slug = None  # Game slug
        self.lutris_slug = None  # Slug used by the lutris website
        self.logo = None  # Game logo
        self.logo_url = None  # URL at which the logo can be downloaded
        self.icon = None  # Game icon
        self.icon_url = None  # URL at which the icon can be downloaded
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

    def save(self):
        """Save this game to database"""
        game_data = {
            "service": self.service,
            "appid": self.appid,
            "name": self.name,
            "slug": self.slug,
            "lutris_slug": self.lutris_slug,
            "icon": self.icon,
            "logo": self.logo,
            "details": str(self.details),
        }
        print(game_data)
        sql.db_insert(PGA_DB, "service_games", game_data)

    def as_dict(self):
        """Return the data in a format compatible with lutris views"""
        return {
            "id": self.appid,
            "name": self.name,
            "slug": self.slug or slugify(self.name),
            "lutris_slug": self.lutris_slug,
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
