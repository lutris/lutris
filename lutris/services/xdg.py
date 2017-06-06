"""XDG applications service"""

import os
import stat
import shutil
import shlex
import subprocess
import re

from textwrap import dedent

from gi.repository import Gio, GLib

from lutris import pga
from lutris.util import system
from lutris.util.log import logger
from lutris.util.strings import slugify
from lutris.config import make_game_config_id, LutrisConfig
from lutris.settings import CACHE_DIR


NAME = "Desktop games"
INSTALLER_SLUG = 'desktopapp'

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
    logger.info('Uninstalling %s' % game_info['name'])
    return pga.add_or_update(
        id=game_info['id'],
        installed=0
    )


def sync_with_lutris():
    desktop_games = {
        game['slug']: game
        for game in pga.get_games_where(runner='linux',
                                        installer_slug=INSTALLER_SLUG,
                                        installed=1)
    }
    seen = set()

    for name, appid, exe, args in get_games():
        slug = slugify(name) or slugify(appid)
        if not all([name, slug, appid]):
            logger.error("Failed to load desktop game \"{}\" (app: {}, slug: {})".format(name, appid, slug))
            continue
        else:
            logger.info("Found desktop game \"{}\" (app: {}, slug: {})".format(name, appid, slug))
        seen.add(slug)

        if slug not in desktop_games.keys():
            game_info = {
                'name': name,
                'slug': slug,
                'config_path': slug + '-' + INSTALLER_SLUG,
                'installer_slug': INSTALLER_SLUG,
                'exe': exe,
                'args': args
            }
            mark_as_installed(appid, 'linux', game_info)

    for slug in set(desktop_games.keys()).difference(seen):
        mark_as_uninstalled(desktop_games[slug])


def iter_xdg_apps():
    for app in Gio.AppInfo.get_all():
        yield app


def get_games():
    """Return the list of games stored in the XDG menu."""
    game_list = []

    for app in iter_xdg_apps():
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


def get_xdg_basename(game_slug, game_id, legacy=False):
    if legacy:
        filename = "{}.desktop".format(game_slug)
    else:
        filename = "{}-{}.desktop".format(game_slug, game_id)
    return filename


def create_launcher(game_slug, game_id, game_name, desktop=False, menu=False):
    """Create a .desktop file."""
    desktop_dir = (
        GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DESKTOP)
    )
    launcher_content = dedent(
        """
        [Desktop Entry]
        Type=Application
        Name={}
        Icon={}
        Exec=lutris lutris:rungameid/{}
        Categories=Game
        """.format(game_name, 'lutris_{}'.format(game_slug), game_id)
    )

    launcher_filename = get_xdg_basename(game_slug, game_id, legacy=False)
    tmp_launcher_path = os.path.join(CACHE_DIR, launcher_filename)
    tmp_launcher = open(tmp_launcher_path, "w")
    tmp_launcher.write(launcher_content)
    tmp_launcher.close()
    os.chmod(tmp_launcher_path, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC |
             stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP)

    if desktop:
        shutil.copy(tmp_launcher_path,
                    os.path.join(desktop_dir, launcher_filename))
    if menu:
        menu_path = os.path.join(GLib.get_user_data_dir(), 'applications')
        shutil.copy(tmp_launcher_path,
                    os.path.join(menu_path, launcher_filename))
    os.remove(tmp_launcher_path)


def get_launcher_path(game_slug, game_id):
    """Return the path of a XDG game launcher.
    When legacy is set, it will return the old path with only the slug,
    otherwise it will return the path with slug + id
    """
    desktop_dir = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DESKTOP)

    legacy_launcher_path = os.path.join(
        desktop_dir, get_xdg_basename(game_slug, game_id, legacy=True)
    )
    # First check if legacy path exists, for backward compatibility
    if system.path_exists(legacy_launcher_path):
        return legacy_launcher_path
    # Otherwise return new path, whether it exists or not
    return os.path.join(
        desktop_dir, get_xdg_basename(game_slug, game_id, legacy=False)
    )


def get_menu_launcher_path(game_slug, game_id):
    """Return the path to a XDG menu launcher, prioritizing legacy paths if
    they exist
    """
    menu_dir = os.path.join(GLib.get_user_data_dir(), 'applications')
    menu_path = os.path.join(
        menu_dir, get_xdg_basename(game_slug, game_id, legacy=True)
    )
    if system.path_exists(menu_path):
        return menu_path
    return os.path.join(
        menu_dir, get_xdg_basename(game_slug, game_id, legacy=False)
    )


def desktop_launcher_exists(game_slug, game_id):
    return system.path_exists(get_launcher_path(game_slug, game_id))


def menu_launcher_exists(game_slug, game_id):
    return system.path_exists(get_menu_launcher_path(game_slug, game_id))


def remove_launcher(game_slug, game_id, desktop=False, menu=False):
    """Remove existing .desktop file."""
    if desktop:
        launcher_path = get_launcher_path(game_slug, game_id)
        if system.path_exists(launcher_path):
            os.remove(launcher_path)

    if menu:
        menu_path = get_menu_launcher_path(game_slug, game_id)
        if system.path_exists(menu_path):
            os.remove(menu_path)
