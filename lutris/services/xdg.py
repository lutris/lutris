"""XDG applications service"""

import os
import shlex
import subprocess
import re

from gi.repository import Gio

from lutris import pga
from lutris.util import system
from lutris.util.log import logger
from lutris.util.strings import slugify
from lutris.config import LutrisConfig
from lutris.services.service_game import ServiceGame

NAME = "Desktop games"
ICON = "linux"
ONLINE = False


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


class XDGGame(ServiceGame):
    """XDG game (Linux game with a desktop launcher)"""
    store = "xdg"
    runner = "linux"
    installer_slug = "desktopapp"

    @classmethod
    def new_from_xdg_app(cls, xdg_app):
        """Create a service game from a XDG entry"""
        service_game = cls()
        service_game.name = xdg_app.get_display_name()
        service_game.icon = xdg_app.get_icon().to_string()
        service_game.appid = get_appid(xdg_app)
        service_game.slug = cls.get_slug(xdg_app)
        service_game.runner = "linux"
        exe, args = cls.get_command_args(xdg_app)
        service_game.details = {
            "exe": exe,
            "args": args,
        }
        return service_game

    def create_config(self):
        """Create a Lutris config for the current game"""
        config = LutrisConfig(runner_slug=self.runner, game_config_id=self.config_id)
        config.raw_game_config.update({
            "appid": self.appid,
            "exe": self.details["exe"],
            "args": self.details["args"]
        })
        config.raw_system_config.update({"disable_runtime": True})
        config.save()

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


class XDGSyncer:
    """Sync games available in a XDG compliant menu to Lutris"""
    ignored_games = (
        "lutris",
        "mame",
        "dosbox",
        "playonlinux",
        "org.gnome.Games",
        "com.github.tkashkin.gamehub",
        "retroarch",
        "steam",
        "steam-runtime",
        "steam-valve",
        "steam-native",
        "PlayOnLinux",
        "fs-uae-arcade",
        "PCSX2",
        "ppsspp",
        "qchdman",
        "qmc2-sdlmame",
        "qmc2-arcade",
        "sc-controller",
        "epsxe",
        "lsi-settings",
    )
    ignored_executables = ("lutris", "steam")
    ignored_categories = ("Emulator", "Development", "Utility")

    @classmethod
    def iter_xdg_games(cls):
        """Iterates through XDG games only"""
        for app in Gio.AppInfo.get_all():
            if cls.is_importable(app):
                yield app

    @classmethod
    def iter_lutris_games(cls):
        """Iterates through Lutris games imported from XDG"""
        for game in pga.get_games_where(runner=XDGGame.runner,
                                        installer_slug=XDGGame.installer_slug,
                                        installed=1):
            yield game

    @classmethod
    def is_importable(cls, app):
        """Returns whether a XDG game is importable to Lutris"""
        appid = get_appid(app)
        executable = app.get_executable() or ''
        if any([
                app.get_nodisplay() or app.get_is_hidden(),  # App is hidden
                not executable,  # Check app has an executable
                appid.startswith("net.lutris"),  # Skip lutris created shortcuts
                appid.lower() in map(str.lower, cls.ignored_games),  # game blacklisted
                executable.lower() in cls.ignored_executables,  # exe blacklisted
        ]):
            return False

        # must be in Game category
        categories = app.get_categories() or ''
        categories = list(filter(None, categories.lower().split(";")))
        if "game" not in categories:
            return False

        # contains a blacklisted category
        if bool([
                category
                for category in categories
                if category in map(str.lower, cls.ignored_categories)
        ]):
            return False
        return True

    @classmethod
    def load(cls, force_reload=False):
        """Return the list of games stored in the XDG menu."""
        return [
            XDGGame.new_from_xdg_app(app)
            for app in cls.iter_xdg_games()
        ]

    @classmethod
    def sync(cls, games, full=False):
        """Sync the given games to the lutris library

        Params:
            games (list): List of ServiceGames to sync

        Return:
            tuple: 2-tuple of added and removed game ID lists
        """
        installed_games = {game["slug"]: game for game in cls.iter_lutris_games()}
        available_games = set()
        added_games = []
        removed_games = []
        for xdg_game in games:
            available_games.add(xdg_game.slug)
            if xdg_game.slug not in installed_games.keys():
                game_id = xdg_game.install()
                added_games.append(game_id)

        if not full:
            return added_games

        for slug in set(installed_games.keys()).difference(available_games):
            game_id = installed_games[slug]["id"]
            removed_games.append(game_id)
            service_game = XDGGame.new_from_lutris_id(game_id)
            service_game.uninstall()
        return added_games, removed_games


SYNCER = XDGSyncer
