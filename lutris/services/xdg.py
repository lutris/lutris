"""Get games installed as desktop applications."""

import os
import shlex
import subprocess
import re

from gi.repository import Gio
from lutris import pga
from lutris.util import system
from lutris.util.log import logger
from lutris.util.strings import slugify
from lutris.config import make_game_config_id, LutrisConfig

NAME = "Desktop games"

IGNORED_GAMES = (
    "lutris", "mame", "dosbox", "playonlinux", "org.gnome.Games", "retroarch",
    "steam", "steam-runtime", "steam-valve", "steam-native", "PlayOnLinux",
    "fs-uae-arcade", "PCSX2", "ppsspp", "qchdman", "qmc2-sdlmame", "qmc2-arcade",
    "sc-controller", "epsxe"
)

IGNORED_EXECUTABLES = (
    "lutris", "steam"
)

IGNORED_CATEGORIES = (
    "Emulator", "Development", "Utility"
)


def mark_as_installed(appid, runner_name, game_info):
    for key in ['name', 'slug']:
        assert game_info[key]
    logger.info("Setting %s as installed" % game_info['name'])
    config_id = (game_info.get('config_path') or make_game_config_id(game_info['slug']))
    game_id = pga.add_or_update(
        name=game_info['name'],
        runner=runner_name,
        slug=game_info['slug'],
        installed=1,
        configpath=config_id,
        installer_slug=game_info['installer_slug']
    )

    config = LutrisConfig(
        runner_slug=runner_name,
        game_config_id=config_id,
    )
    config.raw_game_config.update({
        'appid': appid,
        'exe': game_info['exe'],
        'args': game_info['args']
    })
    config.raw_system_config.update({
        'disable_runtime': True
    })
    config.save()
    return game_id


def mark_as_uninstalled(game_info):
    assert 'id' in game_info
    assert 'name' in game_info
    logger.info('Setting %s as uninstalled' % game_info['name'])
    game_id = pga.add_or_update(
        id=game_info['id'],
        runner='',
        installed=0
    )
    return game_id


def sync_with_lutris():
    apps = get_games()
    desktop_games_in_lutris = pga.get_desktop_games()
    slugs_in_lutris = set([str(game['slug']) for game in desktop_games_in_lutris])

    seen_slugs = set()
    for app in apps:
        game_info = None
        name = app[0]
        appid = app[1]
        slug = slugify(name)

        # if it fails to get slug from the name
        if not slug:
            slug = slugify(appid)

        if not name or not slug or not appid:
            logger.error("Failed to load desktop game "
                         "\"" + str(name) + "\" "
                         "(app: " + str(appid) + ", slug: " + slug + ")")
            continue
        else:
            logger.debug("Found desktop game "
                         "\"" + str(name) + "\" "
                         "(app: " + str(appid) + ", slug: " + slug + ")")

        seen_slugs.add(slug)

        if slug not in slugs_in_lutris:
            game_info = {
                'name': name,
                'slug': slug,
                'config_path': slug + '-desktopapp',
                'installer_slug': 'desktopapp',
                'exe': app[2],
                'args': app[3]
            }
            mark_as_installed(appid, 'linux', game_info)

    unavailable_slugs = slugs_in_lutris.difference(seen_slugs)
    for slug in unavailable_slugs:
        for game in desktop_games_in_lutris:
            if game['slug'] == slug:
                mark_as_uninstalled(game)


def get_games():
    """Return the list of games stored in the XDG menu."""
    game_list = []

    apps = Gio.AppInfo.get_all()
    for app in apps:
        if app.get_nodisplay() or app.get_is_hidden():
            continue

        # Check app has an executable
        if not app.get_executable():
            continue

        appid = os.path.splitext(app.get_id())[0]
        exe = None
        args = []

        # must be in Game category
        categories = app.get_categories()
        if not categories:
            continue
        categories = list(filter(None, categories.lower().split(';')))
        if 'game' not in categories:
            continue

        # contains a blacklisted category
        ok = True
        for category in categories:
            if category in map(str.lower, IGNORED_CATEGORIES):
                ok = False
        if not ok:
            continue

        # game is blacklisted
        if appid.lower() in map(str.lower, IGNORED_GAMES):
            continue

        # executable is blacklisted
        if app.get_executable().lower() in IGNORED_EXECUTABLES:
            continue

        cli = shlex.split(app.get_commandline())
        exe = cli[0]
        args = cli[1:]
        # remove %U etc. and change %% to % in arguments
        args = list(map(lambda arg: re.sub('%[^%]', '', arg).replace('%%', '%'), args))

        args = subprocess.list2cmdline(args)

        if not exe.startswith('/'):
            exe = system.find_executable(exe)
        game_list.append((app.get_display_name(), appid, exe, args))
    return game_list
