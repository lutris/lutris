"""Service game module"""
from lutris import settings
from lutris.database import sql
from lutris.database.services import ServiceGameCollection
from lutris.services.service_media import ServiceMedia

PGA_DB = settings.PGA_DB


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
        existing_game = ServiceGameCollection.get_game(self.service, self.appid)
        if existing_game:
            sql.db_update(PGA_DB, "service_games", game_data, {"id": existing_game["id"]})
        else:
            sql.db_insert(PGA_DB, "service_games", game_data)
