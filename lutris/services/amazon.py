"""Module for handling the Amazon service"""
import os
from gettext import gettext as _

from lutris import settings
from lutris.services.base import OnlineService
from lutris.services.service_media import ServiceMedia


class AmazonBanner(ServiceMedia):
    """Game logo"""
    service = "amazon"
    size = (200, 112)
    dest_path = os.path.join(settings.CACHE_DIR, "amazon/banners")
    file_pattern = "%s.jpg"
    api_field = "image"
    url_pattern = "%s"


class AmazonService(OnlineService):
    """Service class for Amazon"""

    id = "amazon"
    name = _("Amazon Prime Gaming")
    icon = "amazon"
    has_extras = False
    drm_free = False
    medias = {
        "banner": AmazonBanner
    }
    default_format = "banner"

    marketplace_id = "ATVPDKIKX0DER"
    amazon_api = "https://api.amazon.com"
    amazon_sds = "https://sds.amazon.com"
    amazon_gaming_graphql = "https://gaming.amazon.com/graphql"

    redirect_uri = "https://www.amazon.com/?openid.assoc_handle=amzn_sonic_games_launcher"

    cookies_path = os.path.join(settings.CACHE_DIR, ".amazon.auth")
    user_path = os.path.join(settings.CACHE_DIR, ".amazon.user")
    cache_path = os.path.join(settings.CACHE_DIR, "amazon-library.json")

    locale = "en-US"

    @property
    def credential_files(self):
        return [self.user_path]

    @property
    def login_url(self):
        """Return authentication URL"""
        return None

    def login_callback(self, url):
        """Get authentication token from Amazon"""

    def is_connected(self):
        """Return whether the user is authenticated and if the service is available"""
        return False

    def load(self):
        """Load the user game library from the Amazon API"""
        return None
