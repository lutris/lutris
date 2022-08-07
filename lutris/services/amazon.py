"""Module for handling the Amazon service"""
import base64
import hashlib
import json
import os
import secrets
import time
import uuid
from gettext import gettext as _
from urllib.parse import parse_qs, urlencode, urlparse

from lutris import settings
from lutris.services.base import OnlineService
from lutris.services.service_media import ServiceMedia
from lutris.util.http import HTTPError, Request
from lutris.util.log import logger


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

        self.verifier = self.generate_code_verifier()
        challenge = self.generate_challange(self.verifier)

        self.serial = self.generate_device_serial()
        self.client_id = self.generate_client_id(self.serial)

        arguments = {
            "openid.ns": "http://specs.openid.net/auth/2.0",
            "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
            "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
            "openid.mode": "checkid_setup",
            "openid.oa2.scope": "device_auth_access",
            "openid.ns.oa2": "http://www.amazon.com/ap/ext/oauth/2",
            "openid.oa2.response_type": "code",
            "openid.oa2.code_challenge_method": "S256",
            "openid.oa2.client_id": f"device:{self.client_id}",
            "language": "en_US",
            "marketPlaceId": self.marketplace_id,
            "openid.return_to": "https://www.amazon.com",
            "openid.pape.max_auth_age": 0,
            "openid.assoc_handle": "amzn_sonic_games_launcher",
            "pageId": "amzn_sonic_games_launcher",
            "openid.oa2.code_challenge": challenge,
        }

        return "https://amazon.com/ap/signin?" + urlencode(arguments)

    def login_callback(self, url):
        """Get authentication token from Amazon"""

        if url.find("openid.oa2.authorization_code") > 0:
            logger.info("Got authorization code")

            # Parse auth code
            parsed = urlparse(url)
            query = parse_qs(parsed.query)
            auth_code = query["openid.oa2.authorization_code"][0]

            user_data = self.register_device(auth_code)
            if not user_data:
                return

            user_data["token_obtain_time"] = time.time()

            self.save_user_data(user_data)

            self.emit("service-login")

    def is_connected(self):
        """Return whether the user is authenticated and if the service is available"""
        return False

    def load(self):
        """Load the user game library from the Amazon API"""
        return None

    def save_user_data(self, user_data):
        with open(self.user_path, "w", encoding='utf-8') as user_file:
            user_file.write(json.dumps(user_data))

    def load_user_data(self):
        with open(self.user_path, "r", encoding='utf-8') as user_file:
            user_data = json.load(user_file)
        return user_data

    def generate_code_verifier(self) -> bytes:
        code_verifier = secrets.token_bytes(32)
        code_verifier = base64.urlsafe_b64encode(code_verifier).rstrip(b"=")
        logger.info("Generated code_verifier: %s", code_verifier)
        return code_verifier

    def generate_challange(self, code_verifier: bytes) -> bytes:
        challenge_hash = hashlib.sha256(code_verifier)
        challenge = base64.urlsafe_b64encode(challenge_hash.digest()).rstrip(b"=")
        logger.info("Generated challange: %s", challenge)
        return challenge

    def generate_device_serial(self) -> str:
        serial = uuid.UUID(int=uuid.getnode()).hex.upper()
        logger.info("Generated serial: %s", serial)
        return serial

    def generate_client_id(self, serial) -> str:
        serialEx = f"{serial}#A2UMVHOX7UP4V7"
        clientId = serialEx.encode("ascii")
        clientIdHex = clientId.hex()
        logger.info("Generated client_id: %s", clientIdHex)
        return clientIdHex

    def register_device(self, code):
        logger.info("Registerring a device. ID: %s", self.client_id)
        data = {
            "auth_data": {
                "authorization_code": code,
                "client_domain": "DeviceLegacy",
                "client_id": self.client_id,
                "code_algorithm": "SHA-256",
                "code_verifier": self.verifier.decode("utf-8"),
                "use_global_authentication": False,
            },
            "registration_data": {
                "app_name": "AGSLauncher for Windows",
                "app_version": "1.0.0",
                "device_model": "Windows",
                "device_name": None,
                "device_serial": self.serial,
                "device_type": "A2UMVHOX7UP4V7",
                "domain": "Device",
                "os_version": "10.0.19044.0",
            },
            "requested_extensions": ["customer_info", "device_info"],
            "requested_token_type": ["bearer", "mac_dms"],
            "user_context_map": {},
        }

        url = f"{self.amazon_api}/auth/register"
        request = Request(url)

        try:
            request.post(json.dumps(data).encode())
        except HTTPError:
            logger.error(
                "Failed to request %s, check your Amazon credentials and internet connectivity",
                url,
            )
            return

        res_json = request.json
        logger.info("Succesfully registered a device")
        user_data = res_json["response"]["success"]
        return user_data
