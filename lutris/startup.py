"""Check to run at program start"""
import os
import sqlite3
from gettext import gettext as _
from typing import Dict, Set

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from gi.repository import GdkPixbuf

from lutris import runners, settings
from lutris.database.games import get_games
from lutris.database.schema import syncdb
from lutris.game import Game
from lutris.runners.json import load_json_runners
from lutris.scanners.lutris import build_path_cache
from lutris.services import DEFAULT_SERVICES
from lutris.util.display import display_gpu_info, get_gpus_info
from lutris.util.graphics import drivers, vkquery
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import logger
from lutris.util.system import create_folder, preload_vulkan_gpu_names
from lutris.util.wine.dxvk import REQUIRED_VULKAN_API_VERSION


def init_dirs():
    """Creates Lutris directories, returns set of any it created."""
    directories = [
        settings.CONFIG_DIR,
        os.path.join(settings.CONFIG_DIR, "runners"),
        os.path.join(settings.CONFIG_DIR, "games"),
        settings.DATA_DIR,
        settings.ICON_PATH,
        os.path.join(settings.CACHE_DIR, "banners"),
        os.path.join(settings.CACHE_DIR, "coverart"),
        os.path.join(settings.DATA_DIR, "runners"),
        settings.RUNTIME_DIR,
        settings.CACHE_DIR,
        settings.SHADER_CACHE_DIR,
        os.path.join(settings.CACHE_DIR, "installer"),
        os.path.join(settings.CACHE_DIR, "tmp"),
    ]
    created = set()
    for directory in directories:
        if not os.path.exists(directory):
            create_folder(directory)
            created.add(directory)
    return created


def get_drivers():
    """Report on the currently running driver"""
    driver_info = {}
    if drivers.is_nvidia():
        driver_info = drivers.get_nvidia_driver_info()
        # pylint: disable=logging-format-interpolation
        logger.info("Using {vendor} drivers {version} for {arch}".format(**driver_info["nvrm"]))
        gpus = drivers.get_nvidia_gpu_ids()
        for gpu_id in gpus:
            gpu_info = drivers.get_nvidia_gpu_info(gpu_id)
            logger.info("GPU: %s", gpu_info.get("Model"))
    elif LINUX_SYSTEM.glxinfo:
        # pylint: disable=no-member
        if hasattr(LINUX_SYSTEM.glxinfo, "GLX_MESA_query_renderer"):
            driver_info = {
                "vendor": LINUX_SYSTEM.glxinfo.opengl_vendor,
                "version": LINUX_SYSTEM.glxinfo.GLX_MESA_query_renderer.version,
                "device": LINUX_SYSTEM.glxinfo.GLX_MESA_query_renderer.device
            }
            logger.info(
                "Running %s Mesa driver %s on %s",
                LINUX_SYSTEM.glxinfo.opengl_vendor,
                LINUX_SYSTEM.glxinfo.GLX_MESA_query_renderer.version,
                LINUX_SYSTEM.glxinfo.GLX_MESA_query_renderer.device,
            )
    else:
        logger.warning("glxinfo is not available on your system, unable to detect driver version")
    return driver_info


def check_libs(all_components=False):
    """Checks that required libraries are installed on the system"""
    missing_libs = LINUX_SYSTEM.get_missing_libs()
    if all_components:
        components = LINUX_SYSTEM.requirements
    else:
        components = LINUX_SYSTEM.critical_requirements

    for req in components:
        for index, arch in enumerate(LINUX_SYSTEM.runtime_architectures):
            for lib in missing_libs[req][index]:
                logger.error("%s %s missing (needed by %s)", arch, lib, req.lower())


def check_vulkan():
    """Reports if Vulkan is enabled on the system"""
    if not vkquery.is_vulkan_supported():
        logger.warning("Vulkan is not available or your system isn't Vulkan capable")
    else:
        required_api_version = REQUIRED_VULKAN_API_VERSION
        library_api_version = vkquery.get_vulkan_api_version()
        if library_api_version and library_api_version < required_api_version:
            logger.warning("Vulkan reports an API version of %s. "
                           "%s is required for the latest DXVK.",
                           vkquery.format_version(library_api_version),
                           vkquery.format_version(required_api_version))

        devices = vkquery.get_device_info()

        if devices and devices[0].api_version < required_api_version:
            logger.warning("Vulkan reports that the '%s' device has API version of %s. "
                           "%s is required for the latest DXVK.",
                           devices[0].name,
                           vkquery.format_version(devices[0].api_version),
                           vkquery.format_version(required_api_version))


def check_gnome():
    required_names = ['svg', 'png', 'jpeg']
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


def run_all_checks():
    """Run all startup checks"""
    driver_info = get_drivers()
    gpus_info = get_gpus_info()
    for gpu_id, gpu_info in gpus_info.items():
        display_gpu_info(gpu_id, gpu_info)
    check_libs()
    check_vulkan()
    check_gnome()
    preload_vulkan_gpu_names(len(gpus_info) > 1)
    fill_missing_platforms()
    build_path_cache()
    return {
        "drivers": driver_info,
        "gpus": gpus_info
    }


def init_lutris() -> Dict[str, Set[str]]:
    """Run full initialization of Lutris.

    Returns a dict summarizing changes made. This summary can be used to trigger further
    initialization down the line, since it detects when a directory was a missing or a
    new service has been seen."""
    runners.inject_runners(load_json_runners())
    created_directories = init_dirs()
    try:
        syncdb()
    except sqlite3.DatabaseError as err:
        raise RuntimeError(
            _("Failed to open database file in %s. Try renaming this file and relaunch Lutris") %
            settings.PGA_DB
        ) from err

    service_settings_added = set()
    for service in DEFAULT_SERVICES:
        if not settings.read_setting(service, section="services"):
            service_settings_added.add(service)
            settings.write_setting(service, True, section="services")

    return {
        "created_directories": created_directories,
        "service_settings_added": service_settings_added
    }
