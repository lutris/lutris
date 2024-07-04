"""Module for handling the Amazon service"""

import base64
import hashlib
import json
import lzma
import os
import secrets
import struct
import time
import urllib
import uuid
from collections import defaultdict
from gettext import gettext as _
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlencode, urlparse

import yaml

from lutris import settings
from lutris.exceptions import AuthenticationError, UnavailableGameError
from lutris.installer import AUTO_WIN32_EXE
from lutris.installer.installer_file import InstallerFile
from lutris.installer.installer_file_collection import InstallerFileCollection
from lutris.services.base import SERVICE_LOGIN, OnlineService
from lutris.services.service_game import ServiceGame
from lutris.services.service_media import ServiceMedia
from lutris.util import system
from lutris.util.amazon.sds_proto2 import CompressionAlgorithm, HashAlgorithm, Manifest, ManifestHeader
from lutris.util.http import HTTPError, Request
from lutris.util.log import logger
from lutris.util.strings import slugify


class AmazonBanner(ServiceMedia):
    """Game logo"""

    service = "amazon"
    size = (200, 112)
    dest_path = os.path.join(settings.CACHE_DIR, "amazon/banners")
    file_patterns = ["%s.jpg"]
    api_field = "image"
    url_pattern = "%s"

    def get_media_url(self, details: Dict[str, Any]) -> Optional[str]:
        return details["product"]["productDetail"]["details"]["logoUrl"]


class AmazonGame(ServiceGame):
    """Representation of a Amazon game"""

    service = "amazon"

    @classmethod
    def new_from_amazon_game(cls, amazon_game):
        """Return a Amazon game instance from the API info"""
        service_game = AmazonGame()
        service_game.appid = str(amazon_game["id"])
        service_game.slug = slugify(amazon_game["product"]["title"])
        service_game.name = amazon_game["product"]["title"]
        service_game.details = json.dumps(amazon_game)
        return service_game


class AmazonService(OnlineService):
    """Service class for Amazon"""

    id = "amazon"
    name = _("Amazon Prime Gaming")
    icon = "amazon"
    runner = "wine"
    has_extras = False
    drm_free = False
    medias = {"banner": AmazonBanner}
    default_format = "banner"

    login_window_width = 400
    login_window_height = 710

    marketplace_id = "ATVPDKIKX0DER"
    user_agent = "com.amazon.agslauncher.win/3.0.9202.1"

    amazon_api = "https://api.amazon.com"
    amazon_sds = "https://sds.amazon.com"
    amazon_gaming_graphql = "https://gaming.amazon.com/graphql"
    amazon_gaming_distribution = "https://gaming.amazon.com/api/distribution/v2/public"

    client_id = None
    serial = None
    verifier = None

    redirect_uri = "https://www.amazon.com/?"

    cookies_path = os.path.join(settings.CACHE_DIR, ".amazon.auth")
    user_path = os.path.join(settings.CACHE_DIR, ".amazon.user")
    cache_path = os.path.join(settings.CACHE_DIR, "amazon-library.json")

    locale = "en-US"

    @property
    def credential_files(self):
        return [self.user_path, self.cookies_path]

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
            user_data["token_obtain_time"] = time.time()

            self.save_user_data(user_data)

            SERVICE_LOGIN.fire(self)

    def is_connected(self):
        """Return whether the user is authenticated and if the service is available"""
        if not self.is_authenticated():
            return False

        return self.check_connection()

    def load(self):
        """Load the user game library from the Amazon API"""
        if not self.is_connected():
            logger.error("User not connected to Amazon")
            return
        games = [AmazonGame.new_from_amazon_game(game) for game in self.get_library()]
        for game in games:
            game.save()
        return games

    def save_user_data(self, user_data):
        """Save the user data file"""
        with open(self.user_path, "w", encoding="utf-8") as user_file:
            user_file.write(json.dumps(user_data))

    def load_user_data(self):
        """Load the user data file"""
        user_data = None

        if not os.path.exists(self.user_path):
            raise AuthenticationError(_("No Amazon user data available, please log in again"))

        with open(self.user_path, "r", encoding="utf-8") as user_file:
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
        """Register current device and return the user data"""
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
        except HTTPError as ex:
            logger.error("Failed http request %s", url)
            raise AuthenticationError(_("Unable to register device, please log in again")) from ex

        res_json = request.json
        logger.info("Successfully registered a device")
        user_data = res_json["response"]["success"]
        return user_data

    def is_token_expired(self):
        """Check if the stored token is expired"""
        user_data = self.load_user_data()

        token_obtain_time = user_data["token_obtain_time"]
        expires_in = user_data["tokens"]["bearer"]["expires_in"]

        if not token_obtain_time or not expires_in:
            raise AuthenticationError(_("Invalid token info found, please log in again"))

        return time.time() > token_obtain_time + int(expires_in)

    def refresh_token(self):
        """Refresh the token"""
        url = f"{self.amazon_api}/auth/token"
        logger.info("Refreshing token")

        user_data = self.load_user_data()

        headers = {
            "Accept": "application/json",
            "Accept-Language": "en_US",
            "User-Agent": self.user_agent,
            "Content-Type": "application/json",
            "charset": "utf-8",
        }

        refresh_token = user_data["tokens"]["bearer"]["refresh_token"]
        request_data = {
            "source_token": refresh_token,
            "source_token_type": "refresh_token",
            "requested_token_type": "access_token",
            "app_name": "AGSLauncher for Windows",
            "app_version": "1.0.0",
        }

        request = Request(url, headers=headers)

        try:
            request.post(json.dumps(request_data).encode())
        except HTTPError as ex:
            logger.error("Failed http request %s", url)
            raise AuthenticationError(_("Unable to refresh token, please log in again")) from ex

        res_json = request.json

        user_data["tokens"]["bearer"]["access_token"] = res_json["access_token"]
        user_data["tokens"]["bearer"]["expires_in"] = res_json["expires_in"]
        user_data["token_obtain_time"] = time.time()

        self.save_user_data(user_data)

    def get_access_token(self):
        """Return the access token and refresh the session if required"""
        if self.is_token_expired():
            self.refresh_token()

        user_data = self.load_user_data()
        access_token = user_data["tokens"]["bearer"]["access_token"]

        return access_token

    def check_connection(self):
        """Check if the connection with Amazon is available"""

        try:
            access_token = self.get_access_token()
        except Exception:
            return False

        headers = {
            "Accept": "application/json",
            "Accept-Language": "en_US",
            "User-Agent": self.user_agent,
            "Authorization": f"bearer {access_token}",
        }

        url = f"{self.amazon_api}/user/profile"
        request = Request(url, headers=headers)

        try:
            request.get()
        except HTTPError:
            # Do not raise exception here, should be managed from the caller
            logger.error("Failed http request %s", url)
            return False

        return True

    def get_library(self):
        """Return the user's library of Amazon games"""
        if system.path_exists(self.cache_path):
            logger.debug("Returning cached Amazon library")
            with open(self.cache_path, "r", encoding="utf-8") as amazon_cache:
                return json.load(amazon_cache)

        access_token = self.get_access_token()

        user_data = self.load_user_data()
        serial = user_data["extensions"]["device_info"]["device_serial_number"]

        games_by_asin = defaultdict(list)
        next_token = None
        while True:
            request_data = self.get_sync_request_data(serial, next_token)

            json_data = self.request_sds(
                "com.amazonaws.gearbox."
                "softwaredistribution.service.model."
                "SoftwareDistributionService.GetEntitlementsV2",
                access_token,
                request_data,
            )

            if not json_data:
                return

            for game_json in json_data["entitlements"]:
                product = game_json["product"]

                asin = product["asin"]
                games_by_asin[asin].append(game_json)

            if "nextToken" not in json_data:
                break

            logger.info("Got next token in response, making next request")
            next_token = json_data["nextToken"]

        # If Amazon gives is the same game with different ids we'll pick the
        # least ID. Probably we should just use ASIN as the ID, but since we didn't
        # do this in the first release of the Amazon integration, we'll maintain compatibility
        # by using the top level ID whenever we can.
        games = [sorted(gl, key=lambda g: g["id"])[0] for gl in games_by_asin.values()]

        with open(self.cache_path, "w", encoding="utf-8") as amazon_cache:
            json.dump(games, amazon_cache)

        return games

    def request_distribution(self, target, token, body):
        headers = {
            "X-Amz-Target": target,
            "x-amzn-token": token,
            "UserAgent": "com.amazon.agslauncher.win/3.0.9202.1",
            "Content-Type": "application/json",
            "Content-Encoding": "amz-1.0",
        }
        request = Request(self.amazon_gaming_distribution, headers=headers)

        try:
            request.post(json.dumps(body).encode())
        except HTTPError as ex:
            # Do not raise exception here, should be managed from the caller
            logger.error("Failed http request %s: %s", self.amazon_gaming_distribution, ex)
            return

        return request.json

    def get_sync_request_data(self, serial, next_token=None, sync_point=None):
        request_data = {
            "Operation": "GetEntitlementsV2",
            "clientId": "Sonic",
            "syncPoint": sync_point,
            "nextToken": next_token,
            "maxResults": 50,
            "productIdFilter": None,
            "keyId": "d5dc8b8b-86c8-4fc4-ae93-18c0def5314d",
            "hardwareHash": hashlib.sha256(serial.encode()).hexdigest().upper(),
        }

        return request_data

    def request_sds(self, target, token, body):
        headers = {
            "X-Amz-Target": target,
            "x-amzn-token": token,
            "User-Agent": self.user_agent,
            "Content-Type": "application/json",
            "Content-Encoding": "amz-1.0",
        }

        url = f"{self.amazon_sds}/amazon/"
        request = Request(url, headers=headers)

        try:
            request.post(json.dumps(body).encode())
        except HTTPError as ex:
            # Do not raise exception here, should be managed from the caller
            logger.error("Failed http request %s: %s", url, ex)
            return

        return request.json

    def get_game_manifest_info(self, game_id):
        """Get a game manifest information"""
        access_token = self.get_access_token()

        request_data = {
            "entitlementId": game_id,
            "Operation": "GetGameDownload",
        }

        response = self.request_distribution(
            "com.amazon.animusdistributionservice.external.AnimusDistributionService.GetGameDownload",
            access_token,
            request_data,
        )

        if not response:
            logger.error("There was an error getting game manifest: %s", game_id)
            raise UnavailableGameError(_("Unable to get game manifest info"))

        return response

    def get_game_manifest(self, manifest_info):
        """Get a game manifest"""
        headers = {
            "User-Agent": self.user_agent,
        }

        url = manifest_info["downloadUrl"]
        url = urllib.parse.urlparse(url)
        url = url._replace(path=url.path + "/manifest.proto")
        url = urllib.parse.urlunparse(url)

        request = Request(url, headers=headers)

        try:
            request.get()
        except HTTPError as ex:
            logger.error("Failed http request %s", url)
            raise UnavailableGameError(_("Unable to get game manifest")) from ex

        content = request.content

        header_size = struct.unpack(">I", content[:4])[0]

        header = ManifestHeader()
        header.decode(content[4 : 4 + header_size])

        if header.compression.algorithm == CompressionAlgorithm.none:
            raw_manifest = content[4 + header_size :]
        elif header.compression.algorithm == CompressionAlgorithm.lzma:
            raw_manifest = lzma.decompress(content[4 + header_size :])
        else:
            logger.error("Unknown compression algorithm found in manifest")
            raise UnavailableGameError(_("Unknown compression algorithm found in manifest"))

        manifest = Manifest()
        manifest.decode(raw_manifest)

        return manifest

    def get_file_patch(self, access_token, game_id, version, file_hashes):
        request_data = {
            "Operation": "GetPatches",
            "versionId": version,
            "fileHashes": file_hashes,
            "deltaEncodings": ["FUEL_PATCH", "NONE"],
            "adgGoodId": game_id,
        }

        response = self.request_sds(
            "com.amazonaws.gearbox." "softwaredistribution.service.model." "SoftwareDistributionService.GetPatches",
            access_token,
            request_data,
        )

        if not response:
            logger.error("There was an error getting patches: %s", game_id)
            raise UnavailableGameError(_("Unable to get the patches of game"), game_id)
        return response

    def get_game_patches(self, game_id, version, file_list):
        """Get game files"""
        access_token = self.get_access_token()

        def get_batches(to_batch, batch_size):
            i = 0
            while i < len(to_batch):
                yield to_batch[i : i + batch_size]
                i += batch_size

        batches = get_batches(file_list, 500)
        patches = []

        for batch in batches:
            response = self.get_file_patch(access_token, game_id, version, batch)
            patches += response["patches"]

        return patches

    def structure_manifest_data(self, manifest):
        """Transform the manifest to more convenient data structures"""
        files = []
        directories = []
        hashes = []
        hashpairs = []
        for __, package in enumerate(manifest.packages):
            for __, file in enumerate(package.files):
                file_hash = file.hash.value.hex()

                hashes.append(file_hash)
                files.append({"path": file.path.decode().replace("\\", "/"), "size": file.size, "url": None})

                hashpairs.append(
                    {
                        "sourceHash": None,
                        "targetHash": {"value": file_hash, "algorithm": HashAlgorithm.get_name(file.hash.algorithm)},
                    }
                )
            for __, directory in enumerate(package.dirs):
                if directory.path is not None:
                    directories.append(directory.path.decode().replace("\\", "/"))

        file_dict = dict(zip(hashes, files))

        return file_dict, directories, hashpairs

    def get_game_files(self, game_id):
        """Get the game file list"""

        manifest_info = self.get_game_manifest_info(game_id)
        manifest = self.get_game_manifest(manifest_info)

        file_dict, directories, hashpairs = self.structure_manifest_data(manifest)

        for file_hash, file in file_dict.items():
            url = manifest_info["downloadUrl"]
            url = urllib.parse.urlparse(url)
            url = url._replace(path=url.path + "/files/" + file_hash)
            url = urllib.parse.urlunparse(url)
            file["url"] = url

        return file_dict, directories

    def get_exe_and_game_args(self, fuel_url):
        """Get and parse the fuel.json file"""
        headers = {
            "User-Agent": self.user_agent,
        }

        request = Request(fuel_url, headers=headers)

        try:
            request.get()
        except HTTPError as ex:
            logger.error("Failed http request %s", fuel_url)
            raise UnavailableGameError(_("Unable to get fuel.json file.")) from ex

        try:
            res_yaml_text = request.text
            res_json = yaml.safe_load(res_yaml_text)
        except Exception as ex:
            # Maybe it can be parsed as plain JSON. May as well try it.
            try:
                logger.exception("Unparesable yaml response from %s:\n%s", fuel_url, res_yaml_text)
                res_json = json.loads(res_yaml_text)
            except Exception:
                raise UnavailableGameError(_("Invalid response from Amazon APIs")) from ex

        if res_json["Main"] is None or res_json["Main"]["Command"] is None:
            return None, None

        game_cmd = res_json["Main"]["Command"].replace("\\", "/")
        game_args = ""

        if "Args" in res_json["Main"] and res_json["Main"]["Args"]:
            for arg in res_json["Main"]["Args"]:
                game_args += arg if game_args == "" else " " + arg

        return game_cmd, game_args

    def get_game_cmd_line(self, fuel_url):
        """Get the executable path and the arguments for run the game"""
        game_cmd = None
        game_args = None

        if fuel_url is not None:
            game_cmd, game_args = self.get_exe_and_game_args(fuel_url)

        if game_cmd is None:
            game_cmd = AUTO_WIN32_EXE

        if game_args is None:
            game_args = ""

        return game_cmd, game_args

    def get_installer_files(self, installer, _installer_file_id, _selected_extras):
        try:
            file_dict, __ = self.get_game_files(installer.service_appid)
        except HTTPError as err:
            raise UnavailableGameError(_("Couldn't load the downloads for this game")) from err

        files = []
        for file_hash, file in file_dict.items():
            file_name = os.path.basename(file["path"])
            files.append(
                InstallerFile(
                    installer.game_slug, file_hash, {"url": file["url"], "filename": file_name, "size": file["size"]}
                )
            )
        # return should be a list of files, so we return a list containing a InstallerFileCollection
        file_collection = InstallerFileCollection(installer.game_slug, "amazongame", files)
        return [file_collection], []

    def get_installed_slug(self, db_game):
        details = json.loads(db_game["details"])
        return slugify(details["product"]["title"])

    def generate_installer(self, db_game):
        """Generate a installer for the Amazon game"""
        details = json.loads(db_game["details"])
        game_id = details["id"]

        manifest_info = self.get_game_manifest_info(game_id)
        manifest = self.get_game_manifest(manifest_info)

        file_dict, directories, hashpairs = self.structure_manifest_data(manifest)

        installer = [
            {"task": {"name": "create_prefix"}},
            {"mkdir": "$GAMEDIR/drive_c/game"},
            {"autosetup_amazon": {"files": file_dict, "directories": directories}},
        ]

        # try to get fuel file that contain the main exe
        fuel_file = [k for k, v in file_dict.items() if "fuel.json" in v["path"]]
        fuel_url = None
        if fuel_file:
            fuel_url = manifest_info["downloadUrl"]
            fuel_url = urllib.parse.urlparse(fuel_url)
            fuel_url = fuel_url._replace(path=fuel_url.path + "/files/" + list(fuel_file)[0])
            fuel_url = urllib.parse.urlunparse(fuel_url)

        game_cmd, game_args = self.get_game_cmd_line(fuel_url)
        logger.info("game cmd line: %s %s", game_cmd, game_args)

        return {
            "name": details["product"]["title"],
            "version": _("Amazon Prime Gaming"),
            "slug": slugify(details["product"]["title"]),
            "game_slug": slugify(details["product"]["title"]),
            "runner": self.get_installed_runner_name(db_game),
            "script": {
                "game": {
                    "exe": f"$GAMEDIR/drive_c/game/{game_cmd}",
                    "args": game_args,
                    "prefix": "$GAMEDIR",
                    "working_dir": "$GAMEDIR/drive_c/game",
                },
                "system": {},
                "files": [{"amazongame": "N/A:Select the installer from Amazon Games"}],
                "installer": installer,
            },
        }

    def get_installed_runner_name(self, db_game):
        return self.runner
