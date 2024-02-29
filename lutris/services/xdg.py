"""XDG applications service"""
import json
import os
import re
import shlex
import subprocess
from gettext import gettext as _

from gi.repository import Gio

from lutris import settings
from lutris.database.games import get_games_where
from lutris.services.base import BaseService
from lutris.services.service_game import ServiceGame
from lutris.services.service_media import ServiceMedia
from lutris.util import system
from lutris.util.log import logger
from lutris.util.strings import slugify


def get_appid(app):
    """Get the appid for the game"""
    try:
        return os.path.splitext(app.get_id())[0]
    except UnicodeDecodeError:
        logger.exception(
            "Failed to read ID for app %s (non UTF-8 encoding). Reverting to executable name.",
            app,
        )
        return app.get_executable()


class XDGMedia(ServiceMedia):
    service = "xdg"
    source = "local"
    size = (64, 64)
    dest_path = os.path.join(settings.CACHE_DIR, "xdg/icons")
    file_patterns = ["%s.png"]


class XDGService(BaseService):
    id = "xdg"
    name = _("Local")
    icon = "linux"
    runner = "linux"
    online = False
    local = True
    medias = {"icon": XDGMedia}

    ignored_games = ("lutris",)
    ignored_executables = ("lutris", "steam")
    ignored_categories = ("Emulator", "Development", "Utility")

    @classmethod
    def iter_xdg_games(cls):
        """Iterates through XDG games only"""
        for app in Gio.AppInfo.get_all():
            if cls._is_importable(app):
                yield app

    @property
    def lutris_games(self):
        """Iterates through Lutris games imported from XDG"""
        for game in get_games_where(runner=XDGGame.runner, installer_slug=XDGGame.installer_slug, installed=1):
            yield game

    @classmethod
    def _is_importable(cls, app):
        """Returns whether a XDG game is importable to Lutris"""
        appid = get_appid(app)
        executable = app.get_executable() or ""
        if any(
            [
                app.get_nodisplay() or app.get_is_hidden(),  # App is hidden
                not executable,  # Check app has an executable
                appid.startswith("net.lutris"),  # Skip lutris created shortcuts
                appid.lower() in map(str.lower, cls.ignored_games),  # game blacklisted
                executable.lower() in cls.ignored_executables,  # exe blacklisted
            ]
        ):
            return False

        # must be in Game category
        categories = app.get_categories() or ""
        categories = list(filter(None, categories.lower().split(";")))
        if "game" not in categories:
            return False

        # contains a blacklisted category
        ignored_categories = set(c.casefold() for c in cls.ignored_categories)
        if any(c for c in categories if c in ignored_categories):
            return False
        return True

    def match_games(self):
        """XDG games aren't on the lutris website"""
        return

    def load(self):
        """Return the list of games stored in the XDG menu."""
        xdg_games = [XDGGame.new_from_xdg_app(app) for app in self.iter_xdg_games()]
        for game in xdg_games:
            game.save()
        return xdg_games

    def generate_installer(self, db_game):
        details = json.loads(db_game["details"])
        return {
            "name": db_game["name"],
            "version": "XDG",
            "slug": db_game["slug"],
            "game_slug": self.get_installed_slug(db_game),
            "runner": self.get_installed_runner_name(db_game),
            "script": {
                "game": {
                    "exe": details["exe"],
                    "args": details["args"],
                    "working_dir": details["path"],
                },
                "system": {"disable_runtime": True},
            },
        }

    def get_installed_runner_name(self, db_game):
        return self.runner

    def get_game_directory(self, installer):
        """Pull install location from installer"""
        return os.path.dirname(installer["script"]["game"]["exe"])


class XDGGame(ServiceGame):
    """XDG game (Linux game with a desktop launcher)"""

    service = "xdg"
    runner = "linux"
    installer_slug = "desktopapp"

    @staticmethod
    def get_app_icon(xdg_app):
        """Return the name of the icon for an XDG app if one if set"""
        icon = xdg_app.get_icon()
        if not icon:
            return ""
        return icon.to_string()

    @classmethod
    def new_from_xdg_app(cls, xdg_app):
        """Create a service game from a XDG entry"""
        service_game = cls()
        service_game.name = xdg_app.get_display_name()
        service_game.icon = cls.get_app_icon(xdg_app)
        service_game.appid = get_appid(xdg_app)
        service_game.slug = cls.get_slug(xdg_app)
        exe, args = cls.get_command_args(xdg_app)
        path = cls.get_desktop_entry_path(xdg_app)
        service_game.details = json.dumps(
            {
                "exe": exe,
                "args": args,
                "path": path,
            }
        )
        return service_game

    @staticmethod
    def get_desktop_entry_path(xdg_app):
        """Retrieve the Path variable from the .desktop file"""

        # I expect we'll only see DesktopAppInfos here, but just in case
        # we get something else, we'll make sure.
        if hasattr(xdg_app, "get_string"):
            return xdg_app.get_string("Path")
        return None

    @staticmethod
    def get_command_args(app):
        """Return a tuple with absolute command path and an argument string"""
        command = shlex.split(app.get_commandline())
        # remove %U etc. and change %% to % in arguments
        args = list(map(lambda arg: re.sub("%[^%]", "", arg).replace("%%", "%"), command[1:]))
        exe = command[0]
        if not exe.startswith("/"):
            exe = system.find_executable(exe)
        return exe, subprocess.list2cmdline(args)

    @staticmethod
    def get_slug(xdg_app):
        """Get the slug from the game name"""
        return slugify(xdg_app.get_display_name()) or slugify(get_appid(xdg_app))
