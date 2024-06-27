"""itch.io service"""

import datetime
import json
import os
from gettext import gettext as _
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urlencode

from lutris import settings
from lutris.database import games as games_db
from lutris.exceptions import UnavailableGameError
from lutris.installer import AUTO_ELF_EXE, AUTO_WIN32_EXE
from lutris.installer.installer_file import InstallerFile
from lutris.runners import get_runner_human_name
from lutris.services.base import SERVICE_LOGIN, OnlineService
from lutris.services.service_game import ServiceGame
from lutris.services.service_media import ServiceMedia
from lutris.util import linux
from lutris.util.downloader import Downloader
from lutris.util.http import HTTPError, Request, UnauthorizedAccessError
from lutris.util.log import logger
from lutris.util.strings import slugify


class ItchIoCover(ServiceMedia):
    """itch.io game cover"""

    service = "itchio"
    size = (315, 250)
    dest_path = os.path.join(settings.CACHE_DIR, "itchio/cover")
    file_patterns = ["%s.png"]

    def get_media_url(self, details: Dict[str, Any]) -> Optional[str]:
        """Extract cover from API"""
        # Animated (gif) covers have an extra field with a png version of the cover
        if "still_cover_url" in details:
            if details["still_cover_url"]:
                return details["still_cover_url"]
        if "cover_url" in details:
            if details["cover_url"]:
                return details["cover_url"]
        else:
            logger.warning("No field 'cover_url' in API game %s", details)
        return None


class ItchIoCoverMedium(ItchIoCover):
    """itch.io game cover, at 60% size"""

    size = (189, 150)


class ItchIoCoverSmall(ItchIoCover):
    """itch.io game cover, at 30% size"""

    size = (95, 75)


class ItchIoGame(ServiceGame):
    """itch.io Game"""

    service = "itchio"

    @classmethod
    def new(cls, igame):
        """Return a Itch.io game instance from the API info"""
        service_game = ItchIoGame()
        service_game.appid = str(igame["id"])
        service_game.slug = slugify(igame["title"])
        service_game.name = igame["title"]
        service_game.details = json.dumps(igame)
        return service_game


class ItchIoGameTraits:
    """Game Traits Helper Class"""

    def __init__(self, traits):
        self._traits = traits
        self.windows = bool("p_windows" in traits)
        self.linux = bool("p_linux" in traits)
        self.can_be_bought = bool("can_be_bought" in traits)
        self.has_demo = bool("has_demo" in traits)

    def has_supported_platform(self):
        return self.windows or self.linux


class ItchIoService(OnlineService):
    """Service class for itch.io"""

    id = "itchio"
    # According to their branding, "itch.io" is supposed to be all lowercase
    name = _("itch.io")
    icon = "itchio"
    online = True
    drm_free = True
    has_extras = True
    medias = {
        "banner_small": ItchIoCoverSmall,
        "banner_med": ItchIoCoverMedium,
        "banner": ItchIoCover,
    }
    default_format = "banner"

    api_url = "https://api.itch.io"
    login_url = "https://itch.io/login"
    redirect_uri = "https://itch.io/my-feed"
    cookies_path = os.path.join(settings.CACHE_DIR, ".itchio.auth")
    cache_path = os.path.join(settings.CACHE_DIR, "itchio/api/")

    key_cache_file = os.path.join(cache_path, "profile/owned-keys.json")
    games_cache_path = os.path.join(cache_path, "games/")
    key_cache = {}

    supported_platforms = ("p_linux", "p_windows")
    extra_types = (
        "soundtrack",
        "book",
        "video",
        "documentation",
        "mod",
        "audio_assets",
        "graphical_assets",
        "sourcecode",
        "other",
    )

    def login_callback(self, url):
        """Called after the user has logged in successfully"""
        SERVICE_LOGIN.fire(self)

    def is_connected(self):
        """Check if service is connected and can call the API"""
        if not self.is_authenticated():
            return False
        try:
            profile = self.fetch_profile()
        except (HTTPError, UnauthorizedAccessError):
            logger.warning("Not connected to itch.io account.")
            return False
        return profile and "user" in profile

    def load(self):
        """Load the user's itch.io library"""
        if not self.is_connected():
            logger.error("User not connected to itch.io")
            return

        library = self.get_games()
        games = []
        seen = set()
        for game in library:
            if game["title"] in seen:
                continue
            _game = ItchIoGame.new(game)
            games.append(_game)
            _game.save()
            seen.add(game["title"])
        return games

    def make_api_request(self, path, query=None):
        """Make API request"""
        url = "{}/{}".format(self.api_url, path)
        if query is not None and isinstance(query, dict):
            url += "?{}".format(urlencode(query, quote_via=quote_plus))
        try:
            request = Request(url, cookies=self.load_cookies())
            request.get()
            return request.json
        except UnauthorizedAccessError:
            # We aren't logged in, so we'll log out! This allows you to
            # log in again.
            self.logout()
            raise

    def fetch_profile(self):
        """Do API request to get users online profile"""
        return self.make_api_request("profile")

    def fetch_owned_keys(self, query=None):
        """Do API request to get games owned by user (paginated)"""
        return self.make_api_request("profile/owned-keys", query)

    def fetch_game(self, game_id):
        """Do API request to get game info"""
        return self.make_api_request(f"games/{game_id}")

    def fetch_uploads(self, game_id, dl_key):
        """Do API request to get downloadables of a game."""
        query = None
        if dl_key is not None:
            query = {"download_key_id": dl_key}
        return self.make_api_request(f"games/{game_id}/uploads", query)

    def fetch_upload(self, upload, dl_key):
        """Do API request to get downloadable of a game"""
        query = None
        if dl_key is not None:
            query = {"download_key_id": dl_key}
        return self.make_api_request(f"uploads/{upload}", query)

    def fetch_build_patches(self, installed, target, dl_key):
        """Do API request to get game patches"""
        query = None
        if dl_key is not None:
            query = {"download_key_id": dl_key}
        return self.make_api_request(f"builds/{installed}/upgrade-paths/{target}", query)

    def get_download_link(self, upload_id, dl_key):
        """Create download link for installation"""
        url = "{}/{}".format(self.api_url, f"uploads/{upload_id}/download")
        if dl_key is not None:
            query = {"download_key_id": dl_key}
            url += "?{}".format(urlencode(query, quote_via=quote_plus))
        return url

    def get_game_cache(self, appid):
        """Create basic cache key based on game slug and appid"""
        return os.path.join(self.games_cache_path, f"{appid}.json")

    def _cache_games(self, games):
        """Store information about owned keys in cache"""
        os.makedirs(self.games_cache_path, exist_ok=True)
        for game in games:
            filename = self.get_game_cache(game["id"])
            key_path = os.path.join(self.games_cache_path, filename)
            with open(key_path, "w", encoding="utf-8") as cache_file:
                json.dump(game, cache_file)

    def get_owned_games(self, force_load=False):
        """Get all owned library keys from itch.io"""
        owned_keys = []
        fresh_data = True

        if (not force_load) and os.path.exists(self.key_cache_file):
            with open(self.key_cache_file, "r", encoding="utf-8") as key_file:
                owned_keys = json.load(key_file)
            fresh_data = False
        else:
            query = {"page": 1}
            # Basic security; I'm pretty sure itch.io will block us before that tho
            safety = 65507
            while safety:
                response = self.fetch_owned_keys(query)
                if isinstance(response["owned_keys"], list):
                    owned_keys += response["owned_keys"]
                    if len(response["owned_keys"]) == int(response["per_page"]):
                        query["page"] += 1
                    else:
                        break
                else:
                    break
                safety -= 1

            os.makedirs(os.path.join(self.cache_path, "profile/"), exist_ok=True)
            with open(self.key_cache_file, "w", encoding="utf-8") as key_file:
                json.dump(owned_keys, key_file)

        games = []
        for key in owned_keys:
            game = key.get("game", {})
            game["download_key_id"] = key["id"]
            games.append(game)

        if fresh_data:
            self._cache_games(games)
        return games

    def get_games(self):
        """Return games from the user's library"""
        games = self.get_owned_games()
        filtered_games = []
        for game in games:
            traits = game.get("traits", {})
            if any(platform in traits for platform in self.supported_platforms):
                filtered_games.append(game)
        return filtered_games

    def get_key(self, appid):
        """Retrieve cache information on a key"""
        if not appid:
            raise ValueError("Missing Itch.io app ID")
        game_filename = self.get_game_cache(appid)
        game = {}

        if os.path.exists(game_filename):
            with open(game_filename, "r", encoding="utf-8") as game_file:
                game = json.load(game_file)
        else:
            try:
                game = self.fetch_game(appid).get("game", {})
                self._cache_games([game])
            except HTTPError:
                return

        traits = game.get("traits", [])
        if "can_be_bought" not in traits:
            # If game can not be bought it can not have a key
            return
        if "download_key_id" in game:
            # Return cached key
            return game["download_key_id"]
        if not game.get("min_price", 0):
            # We have no key but the game can be played for free
            return

        # Reload whole key library to check if a key was added
        library = self.get_owned_games(True)
        game = next((x for x in library if x["id"] == appid), game)

        if "download_key_id" in game:
            return game["download_key_id"]
        return

    def get_extras(self, appid):
        """Return a list of bonus content for itch.io game."""
        key = self.get_key(appid)
        try:
            uploads = self.fetch_uploads(appid, key)
        except HTTPError:
            return []
        all_extras = {}
        extras = []
        for upload in uploads["uploads"]:
            if upload["type"] not in self.extra_types:
                continue
            extras.append(
                {
                    "name": upload.get("filename", "").strip().capitalize(),
                    "type": upload.get("type", "").strip(),
                    "total_size": upload.get("size", 0),
                    "id": str(upload["id"]),
                }
            )
        if extras:
            all_extras["Bonus Content"] = extras
        return all_extras

    def get_installed_slug(self, db_game):
        return db_game["slug"]

    def generate_installer(self, db_game: Dict[str, Any]) -> Dict[str, Any]:
        """Auto generate installer for itch.io game"""
        details = json.loads(db_game["details"])

        if "p_linux" in details["traits"]:
            return self._generate_installer("linux", db_game)
        elif "p_windows" in details["traits"]:
            return self._generate_installer("wine", db_game)

        logger.warning("No supported platforms found")
        return {}

    def generate_installers(self, db_game: Dict[str, Any]) -> List[dict]:
        """Auto generate installer for itch.io game"""
        details = json.loads(db_game["details"])

        installers = []

        if "p_linux" in details["traits"]:
            installers.append(self._generate_installer("linux", db_game))

        if "p_windows" in details["traits"]:
            installers.append(self._generate_installer("wine", db_game))

        if len(installers) > 1:
            for installer in installers:
                runner_human_name = get_runner_human_name(installer["runner"])
                installer["version"] += " " + (runner_human_name or installer["runner"])

        return installers

    def _generate_installer(self, runner, db_game: Dict[str, Any]) -> Dict[str, Any]:
        if runner == "linux":
            game_config = {"exe": AUTO_ELF_EXE}
            script = [
                {"extract": {"file": "itchupload", "dst": "$CACHE"}},
                {"merge": {"src": "$CACHE", "dst": "$GAMEDIR"}},
            ]
        elif runner == "wine":
            game_config = {"exe": AUTO_WIN32_EXE}
            script = [{"task": {"name": "create_prefix"}}, {"install_or_extract": "itchupload"}]
        else:
            logger.warning(f"'{runner}' is not a supported runner for itchio")
            return {}

        return {
            "name": db_game["name"],
            "version": "itch.io",
            "slug": db_game["slug"],
            "game_slug": self.get_installed_slug(db_game),
            "runner": runner,
            "itchid": db_game["appid"],
            "script": {
                "files": [{"itchupload": "N/A:Select the installer from itch.io"}],
                "game": game_config,
                "installer": script,
            },
        }

    def get_installed_runner_name(self, db_game):
        details = json.loads(db_game["details"])

        if "p_linux" in details["traits"]:
            return "linux"
        if "p_windows" in details["traits"]:
            return "wine"

        return ""

    def get_game_platforms(self, db_game: dict) -> List[str]:
        platforms = []
        details = json.loads(db_game["details"])

        if "p_linux" in details["traits"]:
            platforms.append("Linux")

        if "p_windows" in details["traits"]:
            platforms.append("Windows")

        return platforms

    def _check_update_with_db(self, db_game, key, upload=None):
        stamp = 0
        if upload:
            uploads = [upload["upload"] if "upload" in upload else upload]
        else:
            uploads = self.fetch_uploads(db_game["service_id"], key)
            if "uploads" in uploads:
                uploads = uploads["uploads"]

        for _upload in uploads:
            # skip extras
            if _upload["type"] in self.extra_types:
                continue
            ts = self._rfc3999_to_timestamp(_upload["updated_at"])
            if (not stamp) or (ts > stamp):
                stamp = ts

        if stamp:
            dbg = games_db.get_games_where(
                installed_at__lessthan=stamp, service=self.id, service_id=db_game["service_id"]
            )
            return len(dbg)
        return False

    def get_update_installers(self, db_game):
        """Check for updates"""
        patch_installers = []
        key = self.get_key(db_game["service_id"])
        upload = None
        outdated = False
        patch_url = None
        info = {}
        info_filename = os.path.join(db_game["directory"], ".lutrisgame.json")
        if os.path.exists(info_filename):
            with open(info_filename, encoding="utf-8") as info_file:
                info = json.load(info_file)
            if "upload" in info:
                # TODO: Implement wharf patching
                # if "build" in info and info["build"]:
                #     upload = self.fetch_upload(info["upload"], key)
                #     patches = self.fetch_build_patches(info["build"], upload["build_id"], key)
                #     patch_urls = []
                #     for build in patches["upgrade_path"]["builds"]:
                #         patch_urls.append("builds/{}/download/patch/default".format(build["id"]))
                # else:
                # Do overinstall of upload / Full build url
                try:
                    upload = self.fetch_upload(info["upload"], key)
                    upload = upload["upload"] if "upload" in upload else upload
                    patch_url = self.get_download_link(info["upload"], key)
                except HTTPError as error:
                    if error.code == 400:
                        # Bad request probably means the upload was removed
                        logger.info("Upload %s for %s seems to be removed.", info["upload"], db_game["name"])
                        outdated = True

                if upload:
                    ts = self._rfc3999_to_timestamp(upload.get("updated_at", 0))
                    if int(info.get("date", 0)) >= ts:
                        return
                    info["date"] = int(datetime.datetime.now().timestamp())

        # Skip time based checks if we already know it's outdated
        if not outdated:
            outdated = self._check_update_with_db(db_game, key, upload)

        if outdated:
            installer = {
                "version": "itch.io",
                "name": db_game["name"],
                "slug": db_game["installer_slug"],
                "game_slug": self.get_installed_slug(db_game),
                "runner": db_game["runner"],
                "script": {
                    "extends": db_game["installer_slug"],
                    "files": [],
                    "installer": [
                        {"extract": {"file": "itchupload", "dst": "$CACHE"}},
                    ],
                },
            }

            if patch_url:
                installer["script"]["files"] = [
                    {
                        "itchupload": {
                            "url": patch_url,
                            "filename": "update.zip",
                            "downloader": Downloader(patch_url, None, overwrite=True, cookies=self.load_cookies()),
                        }
                    }
                ]
            else:
                installer["script"]["files"] = [{"itchupload": "N/A:Select the installer from itch.io"}]

            if db_game["runner"] == "linux":
                installer["script"]["installer"].append(
                    {"merge": {"src": "$CACHE", "dst": "$GAMEDIR"}},
                )
            elif db_game["runner"] == "wine":
                installer["script"]["installer"].append(
                    {"merge": {"src": "$CACHE", "dst": "$GAMEDIR/drive_c/%s" % db_game["slug"]}}
                )

            if patch_url:
                installer["script"]["installer"].append(
                    {"write_json": {"data": info, "file": info_filename, "merge": True}}
                )

            patch_installers.append(installer)
        return patch_installers

    def get_dlc_installers_runner(self, db_game, runner, only_owned=True):
        """itch.io does currently not officially support dlc"""
        return []

    def get_installer_files(self, installer, installer_file_id, selected_extras):
        """Replace the user provided file with download links from itch.io"""

        key = self.get_key(installer.service_appid)
        try:
            uploads = self.fetch_uploads(installer.service_appid, key)
        except HTTPError as ex:
            raise UnavailableGameError from ex
        filtered = []
        extras = []
        files = []
        extra_files = []
        link = None
        filename = "setup.zip"
        selected_extras_ids = set(x["id"] for x in selected_extras or [])

        file = next(_file.copy() for _file in installer.script_files if _file.id == installer_file_id)
        if not file.url.startswith("N/A"):
            link = file.url

        data = {
            "service": self.id,
            "appid": installer.service_appid,
            "slug": installer.game_slug,
            "runner": installer.runner,
            "date": int(datetime.datetime.now().timestamp()),
        }

        if not link or len(selected_extras_ids) > 0:
            for upload in uploads["uploads"]:
                if selected_extras_ids and (upload["type"] in self.extra_types):
                    extras.append(upload)
                    continue
                # default =  games/tools ("executables")
                if upload["type"] == "default" and (installer.runner in ("linux", "wine")):
                    is_linux = installer.runner == "linux" and "p_linux" in upload["traits"]
                    is_windows = installer.runner == "wine" and "p_windows" in upload["traits"]
                    is_demo = "demo" in upload["traits"]
                    if not (is_linux or is_windows):
                        continue

                    upload["Weight"] = self.get_file_weight(upload["filename"], is_demo)
                    if upload["Weight"] == 0xFF:
                        continue

                    filtered.append(upload)
                    continue
                # TODO: Implement embedded types: flash, unity, java, html
                # I have not found keys for embdedded games
                # but people COULD write custom installers.
                # So far embedded games can be played directly on itch.io

        if len(filtered) > 0 and not link:
            filtered.sort(key=lambda upload: upload["Weight"])
            # Lutris does not support installer selection
            upload = filtered[0]
            data["upload"] = str(upload["id"])
            if "build_id" in upload:
                data["build"] = str(upload["build_id"])

            link = self.get_download_link(upload["id"], key)
            filename = upload["filename"]

        if link:
            # Adding a file with some basic info for e.g. patching
            installer.script["installer"].append(
                {"write_json": {"data": data, "file": "$GAMEDIR/.lutrisgame.json", "merge": False}}
            )

            files.append(
                InstallerFile(
                    installer.game_slug,
                    installer_file_id,
                    {
                        "url": link,
                        "filename": filename or file.filename or "setup.zip",
                        "downloader": Downloader(link, None, overwrite=True, cookies=self.load_cookies()),
                    },
                )
            )

        for extra in extras:
            if str(extra["id"]) not in selected_extras_ids:
                continue
            link = self.get_download_link(extra["id"], key)
            extra_files.append(
                InstallerFile(
                    installer.game_slug,
                    str(extra["id"]),
                    {
                        "url": link,
                        "filename": extra["filename"],
                        "downloader": Downloader(link, None, overwrite=True, cookies=self.load_cookies()),
                    },
                )
            )

        return files, extra_files

    def get_patch_files(self, installer, installer_file_id):
        """Similar to get_installer_files but for patches"""
        # No really, it is the same! so we just call get_installer_files
        # and strip off the extras files.
        files, _extra_files = self.get_installer_files(installer, installer_file_id, [])
        return files

    def get_file_weight(self, name, demo):
        if name.endswith(".rpm"):
            return 0xFF  # Not supported as an extractor
        weight = 0x0
        if name.endswith(".deb"):
            weight |= 0x01
        if linux.LINUX_SYSTEM.is_64_bit:
            if "386" in name or "32" in name:
                weight |= 0x08
        else:
            if "64" in name:
                weight |= 0x10
        if demo:
            weight |= 0x40
        return weight

    def _rfc3999_to_timestamp(self, _s):
        # Python does ootb not fully comply with RFC3999; Cut after seconds
        return datetime.datetime.fromisoformat(_s[: _s.rfind(".")]).timestamp()
