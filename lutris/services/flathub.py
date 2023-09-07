import json
import os
import shutil
import subprocess
from gettext import gettext as _
from pathlib import Path

import requests
from gi.repository import Gio

from lutris import settings
from lutris.services.base import BaseService
from lutris.services.service_game import ServiceGame
from lutris.services.service_media import ServiceMedia
from lutris.util import system
from lutris.util.log import logger
from lutris.util.strings import slugify


class FlathubBanner(ServiceMedia):
    """Standard size of a Flathub banner"""
    service = "flathub"
    size = (128, 128)
    dest_path = os.path.join(settings.CACHE_DIR, "flathub/banners")
    file_pattern = "%s.png"
    file_format = "png"
    url_field = 'iconDesktopUrl'

    def get_media_url(self, details):
        return details.get(self.url_field)


class FlathubGame(ServiceGame):
    """Representation of a Flathub game"""
    service = "flathub"

    @classmethod
    def new_from_flathub_game(cls, flathub_game):
        """Return a Flathub game instance from the API info"""
        service_game = FlathubGame()
        service_game.appid = flathub_game["flatpakAppId"]
        service_game.slug = slugify(flathub_game["name"])
        service_game.lutris_slug = slugify(flathub_game["name"])
        service_game.name = flathub_game["name"]
        service_game.details = {
            "summary": flathub_game["summary"],
            "version": flathub_game["currentReleaseVersion"]
        }
        service_game.runner = "flatpak"
        service_game.details = json.dumps(flathub_game)
        return service_game


class FlathubService(BaseService):
    """Service class for Flathub"""

    id = "flathub"
    name = _("Flathub")
    icon = "flathub"
    medias = {
        "banner": FlathubBanner
    }
    default_format = "banner"
    api_url = "https://flathub.org/api/v1/apps/category/Game"
    cache_path = os.path.join(settings.CACHE_DIR, "flathub-library.json")

    branch = "stable"
    arch = "x86_64"
    install_type = "system"  # can be either system (default) or user
    install_locations = {
        "system": "var/lib/flatpak/app/",
        "user": f"{Path.home()}/.local/share/flatpak/app/"
    }
    runner = "flatpak"
    game_class = FlathubGame

    def wipe_game_cache(self):
        """Wipe the game cache, allowing it to be reloaded"""
        if system.path_exists(self.cache_path):
            logger.debug("Deleting %s cache %s", self.id, self.cache_path)
            os.remove(self.cache_path)
        super().wipe_game_cache()

    def get_flatpak_cmd(self):
        flatpak_abspath = shutil.which("flatpak")
        if flatpak_abspath:
            return [flatpak_abspath]
        flatpak_spawn_abspath = shutil.which("flatpak-spawn")
        if flatpak_spawn_abspath:
            return [flatpak_spawn_abspath, "--host", "flatpak"]
        raise RuntimeError("No flatpak or flatpak-spawn found")

    def load(self):
        """Load the available games from Flathub"""
        response = requests.get(self.api_url, timeout=5)
        entries = response.json()
        flathub_games = []
        for game in entries:
            flathub_games.append(FlathubGame.new_from_flathub_game(game))
        for game in flathub_games:
            game.save()
        return flathub_games

    def install(self, db_game):
        """Install a Flathub game"""
        app_id = db_game["appid"]
        logger.debug("Installing %s from service %s", app_id, self.id)
        # Check if Flathub repo is active on the system
        if not self.is_flathub_remote_active():
            logger.error("Flathub is not configured on the system. Visit https://flatpak.org/setup/ for instructions.")
            return
        # Install the game
        service_installers = self.get_installers_from_api(app_id)
        if not service_installers:
            service_installers = [self.generate_installer(db_game)]
        application = Gio.Application.get_default()
        application.show_installer_window(service_installers, service=self, appid=app_id)

    def get_installed_apps(self):
        """Get list of installed Flathub apps"""
        try:
            flatpak_cmd = self.get_flatpak_cmd()
            process = subprocess.run(flatpak_cmd + ["list", "--app", "--columns=application"],
                                     capture_output=True, check=True, encoding="utf-8", text=True, timeout=5.0)
            return process.stdout.splitlines() or []
        except (TimeoutError, subprocess.CalledProcessError) as err:
            logger.exception("Error occurred while getting installed flatpak apps: %s", err)
            return []

    def is_flathub_remote_active(self):
        """Check if Flathub is configured and enabled as a flatpak repository"""
        remotes = self.get_active_remotes()
        if not remotes:
            logger.warning("Remotes not found, Flathub considered installed")
            return True
        for remote in remotes:
            if 'flathub' in remote.values():
                return True
        return False

    def get_active_remotes(self):
        """Get a list of dictionaries containing name, title and url"""
        try:
            flatpak_cmd = self.get_flatpak_cmd()
            process = subprocess.run(flatpak_cmd + ["remotes", "--columns=name,title,url"],
                                     capture_output=True, check=True, encoding="utf-8", text=True, timeout=5.0)
            entries = []
            for line in process.stdout.splitlines():
                cols = line.split("\t")
                entries.append({
                    "name": cols[0].lower(),
                    "title": cols[1].lower(),
                    "url": cols[2]
                })
            return entries
        except (TimeoutError, subprocess.CalledProcessError) as err:
            logger.exception("Error occurred while getting installed flatpak apps: %s", err)
            return []

    def generate_installer(self, db_game):
        # TODO: Add options for user to select arch, branch and install_type
        flatpak_cmd = self.get_flatpak_cmd()
        return {
            "appid": db_game["appid"],
            "game_slug": slugify(db_game["name"]),
            "slug": slugify(db_game["name"]) + "-" + self.id,
            "name": db_game["name"],
            "version": "Flathub",
            "runner": self.runner,
            "script": {
                "game": {
                    "appid": db_game["appid"],
                    "arch": self.arch,
                    "branch": self.branch,
                    "install_type": self.install_type
                },
                "system": {
                    "disable_runtime": True
                },
                "require-binaries": flatpak_cmd[0],
                "installer": [
                    {
                        "execute":
                        {
                            "file": flatpak_cmd[0],
                            "args": " ".join(flatpak_cmd[1:]) + f" install --app --noninteractive flathub "
                                    f"app/{db_game['appid']}/{self.arch}/{self.branch}",
                            "disable_runtime": True
                        }
                    }
                ]
            }
        }

    def get_game_directory(self, _installer):
        install_type, application, arch, branch = (_installer["script"]["game"][key] for key in
                                                   ("install_type", "application", "arch", "branch"))
        return os.path.join(self.install_locations[install_type], application, arch, branch)

    # def add_installed_games(self):
    #     process = subprocess.run(["flatpak", "list", "--app", "--columns=application,arch,branch,installation,name"],
    #                              capture_output=True, check=True, encoding="utf-8", text=True)
    #     for line in process.stdout.splitlines():
    #         cols = line.split("\t")
