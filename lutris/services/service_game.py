"""Communicates between third party services games and Lutris games"""
import json
import os

from lutris import settings
from lutris.database import sql
from lutris.database.services import ServiceGameCollection
from lutris.util import system
from lutris.util.http import download_file

PGA_DB = settings.PGA_DB


class ServiceMedia:
    """Information about the service's media format"""

    service = NotImplemented
    size = NotImplemented
    source = "remote"  # set to local if the files don't need to be downloaded
    small_size = None
    dest_path = None
    file_pattern = NotImplemented
    api_field = NotImplemented
    url_pattern = "%s"

    def __init__(self):
        if self.dest_path and not system.path_exists(self.dest_path):
            os.makedirs(self.dest_path)

    def get_filename(self, slug):
        return self.file_pattern % slug

    def get_absolute_path(self, slug):
        """Return the abolute path of a local media"""
        return os.path.join(self.dest_path, self.get_filename(slug))

    def exists(self, slug):
        """Whether the icon for the specified slug exists locally"""
        return system.path_exists(self.get_absolute_path(slug))

    def get_url(self, service_game):
        return self.url_pattern % service_game[self.api_field]

    def get_media_urls(self):
        """Return URLs for icons and logos from a service"""
        if self.source == "local":
            return {}
        service_games = ServiceGameCollection.get_for_service(self.service)
        medias = {}
        for game in service_games:
            if not game["details"]:
                continue
            details = json.loads(game["details"])
            medias[game["slug"]] = self.url_pattern % details[self.api_field]
        return medias

    def download(self, slug, url):
        """Downloads the banner if not present"""
        if not url:
            return
        cache_path = os.path.join(self.dest_path, self.get_filename(slug))
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
        self.icon = None  # Game icon
        self.details = None  # Additional details for the game

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
        sql.db_insert(PGA_DB, "service_games", game_data)
