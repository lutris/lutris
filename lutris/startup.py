"""Check to run at program start"""

import os
import shutil
import sqlite3
import threading
from gettext import gettext as _

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import GdkPixbuf

from lutris import runners, settings
from lutris.database.games import get_games
from lutris.database.schema import syncdb
from lutris.game import Game
from lutris.runners.json import load_json_runners
from lutris.runners.yaml import load_yaml_runners
from lutris.services import DEFAULT_SERVICES
from lutris.util.graphics import vkquery
from lutris.util.graphics.gpu import preload_gpus
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import logger
from lutris.util.path_cache import build_path_cache
from lutris.util.system import create_folder
from lutris.util.wine.dxvk import REQUIRED_VULKAN_API_VERSION


def init_dirs():
    """Creates Lutris directories"""
    directories = [
        settings.CONFIG_DIR,
        settings.RUNNERS_CONFIG_DIR,
        settings.GAME_CONFIG_DIR,
        settings.DATA_DIR,
        settings.ICON_PATH,
        settings.BANNER_PATH,
        settings.COVERART_PATH,
        settings.RUNNER_DIR,
        settings.RUNTIME_DIR,
        settings.CACHE_DIR,
        settings.SHADER_CACHE_DIR,
        settings.INSTALLER_CACHE_DIR,
        settings.TMP_DIR,
    ]
    for directory in directories:
        create_folder(directory)
    _clear_tmp_dir()


def _clear_tmp_dir():
    """Remove leftover files from previous Lutris runs.

    Nothing in TMP_DIR is expected to survive across runs; files there
    are return-code files from game launches and download temporaries
    that should have been cleaned up but may not have been (e.g. if
    Lutris crashed).
    """
    try:
        for entry in os.listdir(settings.TMP_DIR):
            path = os.path.join(settings.TMP_DIR, entry)
            try:
                if os.path.isdir(path) and not os.path.islink(path):
                    shutil.rmtree(path)
                else:
                    os.unlink(path)
            except OSError as ex:
                logger.debug("Could not remove %s: %s", path, ex)
    except OSError as ex:
        logger.debug("Could not list temp directory %s: %s", settings.TMP_DIR, ex)


def check_libs(all_components=False):
    """Checks that required libraries are installed on the system.

    This is purely diagnostic logging and is run on a background thread
    at startup so the expensive ldconfig parse doesn't block the UI.
    """
    try:
        missing_libs = LINUX_SYSTEM.get_missing_libs()
        if all_components:
            components = LINUX_SYSTEM.requirements
        else:
            components = LINUX_SYSTEM.critical_requirements

        for req in components:
            for index, arch in enumerate(LINUX_SYSTEM.runtime_architectures):
                for lib in missing_libs[req][index]:
                    logger.error("%s %s missing (needed by %s)", arch, lib, req.lower())
    except Exception:
        logger.exception("Library check failed")


def check_vulkan():
    """Reports if Vulkan is enabled on the system"""
    if os.environ.get("LUTRIS_NO_VKQUERY"):
        return
    if not vkquery.is_vulkan_supported():
        logger.warning("Vulkan is not available or your system isn't Vulkan capable")
    else:
        required_api_version = REQUIRED_VULKAN_API_VERSION
        library_api_version = vkquery.get_vulkan_api_version()
        if library_api_version and library_api_version < required_api_version:
            logger.warning(
                "Vulkan reports an API version of %s. %s is required for the latest DXVK.",
                vkquery.format_version(library_api_version),
                vkquery.format_version(required_api_version),
            )

        devices = vkquery.get_device_info()

        if devices and devices[0].api_version < required_api_version:
            logger.warning(
                "Vulkan reports that the '%s' device has API version of %s. %s is required for the latest DXVK.",
                devices[0].name,
                vkquery.format_version(devices[0].api_version),
                vkquery.format_version(required_api_version),
            )


def check_gnome():
    required_names = ["svg", "png", "jpeg"]
    format_names = [f.get_name() for f in GdkPixbuf.Pixbuf.get_formats()]
    for required in required_names:
        if required not in format_names:
            logger.error("'%s' PixBuf support is not installed.", required.upper())


def fill_missing_platforms():
    """Sets the platform on games where it's missing.
    This should never happen.
    """
    pga_games = get_games(filters={"installed": 1})
    for pga_game in pga_games:
        if pga_game.get("platform") or not pga_game["runner"]:
            continue
        game = Game(game_id=pga_game["id"])
        game.set_platform_from_runner()
        if game.platform:
            logger.info("Platform for %s set to %s", game.name, game.platform)
            game.save_platform()


def run_all_checks() -> None:
    """Run all startup checks"""
    preload_gpus()
    # check_libs is purely diagnostic logging; run it in the background
    # so the expensive ldconfig parse doesn't block startup.
    threading.Thread(target=check_libs, daemon=True).start()
    check_vulkan()
    check_gnome()
    fill_missing_platforms()
    build_path_cache()


def init_lutris():
    """Run full initialization of Lutris"""
    runners.inject_runners(load_json_runners())
    runners.inject_runners(load_yaml_runners())
    init_dirs()
    try:
        syncdb()
    except sqlite3.DatabaseError as err:
        raise RuntimeError(
            _("Failed to open database file in %s. Try renaming this file and relaunch Lutris") % settings.DB_PATH
        ) from err
    for service in DEFAULT_SERVICES:
        if not settings.read_setting(service, section="services"):
            settings.write_setting(service, True, section="services")
