"""XDG applications service"""

import os
import shlex
import subprocess
import re
from collections import namedtuple

from gi.repository import Gio

from lutris import pga
from lutris.util import system
from lutris.util.log import logger
from lutris.util.strings import slugify
from lutris.config import make_game_config_id, LutrisConfig


NAME = "Desktop games"
ICON = "linux"
INSTALLER_SLUG = "desktopapp"

IGNORED_GAMES = (
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

IGNORED_EXECUTABLES = ("lutris", "steam")

IGNORED_CATEGORIES = ("Emulator", "Development", "Utility")


def mark_as_installed(appid, runner_name, game_info):
    for key in ["name", "slug"]:
        assert game_info[key]
    logger.info("Setting %s as installed", game_info["name"])
    config_id = game_info.get("config_path") or make_game_config_id(game_info["slug"])
    game_id = pga.add_or_update(
        name=game_info["name"],
        runner=runner_name,
        slug=game_info["slug"],
        installed=1,
        configpath=config_id,
        installer_slug=game_info["installer_slug"],
    )

    config = LutrisConfig(runner_slug=runner_name, game_config_id=config_id)
    config.raw_game_config.update(
        {"appid": appid, "exe": game_info["exe"], "args": game_info["args"]}
    )
    config.raw_system_config.update({"disable_runtime": True})
    config.save()
    return game_id


def mark_as_uninstalled(game_info):
    logger.info("Uninstalling %s", game_info["name"])
    return pga.add_or_update(id=game_info["id"], installed=0)


def sync_with_lutris():
    desktop_games = {
        game["slug"]: game
        for game in pga.get_games_where(
            runner="linux", installer_slug=INSTALLER_SLUG, installed=1
        )
    }
    seen = set()

    for xdg_game in load_games():
        name = xdg_game.name
        appid = xdg_game.appid
        slug = slugify(name) or slugify(appid)
        if not all([name, slug, appid]):
            logger.error(
                'Failed to load desktop game "%s" (app: %s, slug: %s)',
                name,
                appid,
                slug,
            )
            continue
        else:
            logger.info(
                'Found desktop game "%s" (app: %s, slug: %s)', name, appid, slug
            )
        seen.add(slug)

        if slug not in desktop_games.keys():
            game_info = {
                "name": name,
                "slug": slug,
                "config_path": slug + "-" + INSTALLER_SLUG,
                "installer_slug": INSTALLER_SLUG,
                "exe": xdg_game.exe,
                "args": xdg_game.args,
            }
            mark_as_installed(appid, "linux", game_info)

    for slug in set(desktop_games.keys()).difference(seen):
        mark_as_uninstalled(desktop_games[slug])


def iter_xdg_apps():
    for app in Gio.AppInfo.get_all():
        yield app


XDGShortcut = namedtuple('XDGShortcut', ['appid', 'name', 'icon', 'exe', 'args'])


def load_games():
    """Return the list of games stored in the XDG menu."""
    game_list = []

    for app in iter_xdg_apps():
        if app.get_nodisplay() or app.get_is_hidden():
            continue

        # Check app has an executable
        if not app.get_executable():
            continue

        try:
            appid = os.path.splitext(app.get_id())[0]
        except UnicodeDecodeError:
            logger.error(
                "Failed to read ID for app %s (non UTF-8 encoding). Reverting to executable name.",
                app,
            )
            appid = app.get_executable()

        # Skip lutris created shortcuts
        if appid.startswith("net.lutris"):
            continue

        # must be in Game category
        categories = app.get_categories()
        if not categories:
            continue
        categories = list(filter(None, categories.lower().split(";")))
        if "game" not in categories:
            continue

        # contains a blacklisted category
        has_blacklisted = bool(
            [
                category
                for category in categories
                if category in map(str.lower, IGNORED_CATEGORIES)
            ]
        )
        if has_blacklisted:
            continue

        # game is blacklisted
        if appid.lower() in map(str.lower, IGNORED_GAMES):
            continue

        # executable is blacklisted
        if app.get_executable().lower() in IGNORED_EXECUTABLES:
            logger.debug("Skipping %s with executable %s", appid, app.get_executable())
            continue

        cli = shlex.split(app.get_commandline())
        exe = cli[0]
        args = cli[1:]
        # remove %U etc. and change %% to % in arguments
        args = list(map(lambda arg: re.sub("%[^%]", "", arg).replace("%%", "%"), args))

        args = subprocess.list2cmdline(args)
        if not exe.startswith("/"):
            exe = system.find_executable(exe)
        game_list.append(XDGShortcut(
            appid=appid,
            name=app.get_display_name(),
            icon=app.get_icon().to_string(),
            exe=exe,
            args=args
        ))
    return game_list
