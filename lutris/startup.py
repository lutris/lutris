"""Check to run at program start"""
import os
import sqlite3
from gettext import gettext as _

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from gi.repository import GdkPixbuf

from lutris import runners, settings
from lutris.database.games import delete_game, get_games, get_games_where
from lutris.database.schema import syncdb
from lutris.game import Game
from lutris.gui.dialogs import DontShowAgainDialog
from lutris.runners.json import load_json_runners
from lutris.runtime import RuntimeUpdater
from lutris.scanners.lutris import build_path_cache
from lutris.services import DEFAULT_SERVICES
from lutris.services.lutris import sync_media
from lutris.util.display import USE_DRI_PRIME
from lutris.util.graphics import drivers, vkquery
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import logger
from lutris.util.steam.shortcut import update_all_artwork
from lutris.util.system import create_folder, preload_vulkan_gpu_names
from lutris.util.wine.d3d_extras import D3DExtrasManager
from lutris.util.wine.dgvoodoo2 import dgvoodoo2Manager
from lutris.util.wine.dxvk import REQUIRED_VULKAN_API_VERSION, DXVKManager
from lutris.util.wine.dxvk_nvapi import DXVKNVAPIManager
from lutris.util.wine.vkd3d import VKD3DManager


def init_dirs():
    """Creates Lutris directories"""
    directories = [
        settings.CONFIG_DIR,
        os.path.join(settings.CONFIG_DIR, "runners"),
        os.path.join(settings.CONFIG_DIR, "games"),
        settings.DATA_DIR,
        os.path.join(settings.DATA_DIR, "covers"),
        settings.ICON_PATH,
        os.path.join(settings.CACHE_DIR, "banners"),
        os.path.join(settings.CACHE_DIR, "coverart"),
        os.path.join(settings.DATA_DIR, "runners"),
        os.path.join(settings.DATA_DIR, "lib"),
        settings.RUNTIME_DIR,
        settings.CACHE_DIR,
        settings.SHADER_CACHE_DIR,
        os.path.join(settings.CACHE_DIR, "installer"),
        os.path.join(settings.CACHE_DIR, "tmp"),
    ]
    for directory in directories:
        create_folder(directory)


def check_driver():
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
            logger.info(
                "Running %s Mesa driver %s on %s",
                LINUX_SYSTEM.glxinfo.opengl_vendor,
                LINUX_SYSTEM.glxinfo.GLX_MESA_query_renderer.version,
                LINUX_SYSTEM.glxinfo.GLX_MESA_query_renderer.device,
            )
    else:
        logger.warning("glxinfo is not available on your system, unable to detect driver version")

    for card in drivers.get_gpus():
        # pylint: disable=logging-format-interpolation
        try:
            logger.info("GPU: {PCI_ID} {PCI_SUBSYS_ID} ({DRIVER} drivers)".format(**drivers.get_gpu_info(card)))
        except KeyError:
            logger.error("Unable to get GPU information from '%s'", card)

    if drivers.is_outdated():
        setting = "hide-outdated-nvidia-driver-warning"
        if settings.read_setting(setting) != "True":
            DontShowAgainDialog(
                setting,
                _("Your NVIDIA driver is outdated."),
                secondary_message=_(
                    "You are currently running driver %s which does not "
                    "fully support all features for Vulkan and DXVK games.\n"
                    "Please upgrade your driver as described in our "
                    "<a href='%s'>installation guide</a>"
                ) % (
                    driver_info["nvrm"]["version"],
                    settings.DRIVER_HOWTO_URL,
                )
            )


def check_libs(all_components=False):
    """Checks that required libraries are installed on the system"""
    missing_libs = LINUX_SYSTEM.get_missing_libs()
    if all_components:
        components = LINUX_SYSTEM.requirements
    else:
        components = LINUX_SYSTEM.critical_requirements
    missing_vulkan_libs = []
    for req in components:
        for index, arch in enumerate(LINUX_SYSTEM.runtime_architectures):
            for lib in missing_libs[req][index]:
                if req == "VULKAN":
                    missing_vulkan_libs.append(arch)
                logger.error("%s %s missing (needed by %s)", arch, lib, req.lower())

    if missing_vulkan_libs:
        setting = "dismiss-missing-vulkan-library-warning"
        if settings.read_setting(setting) != "True":
            DontShowAgainDialog(
                setting,
                _("Missing Vulkan libraries"),
                secondary_message=_(
                    "Lutris was unable to detect Vulkan support for "
                    "the %s architecture.\n"
                    "This will prevent many games and programs from working.\n"
                    "To install it, please use the following guide: "
                    "<a href='%s'>Installing Graphics Drivers</a>"
                ) % (
                    _(" and ").join(missing_vulkan_libs),
                    settings.DRIVER_HOWTO_URL,
                )
            )


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
    check_driver()
    check_libs()
    check_vulkan()
    check_gnome()
    preload_vulkan_gpu_names(USE_DRI_PRIME)
    fill_missing_platforms()
    build_path_cache()


def cleanup_games():
    """Delete all uninstalled games that don't have any playtime"""
    removed_games = get_games_where(installed=0)
    for game in removed_games:
        if game["playtime"]:
            continue
        delete_game(game["id"])


def init_lutris():
    """Run full initialization of Lutris"""
    logger.info("Starting Lutris %s", settings.VERSION)
    runners.inject_runners(load_json_runners())
    init_dirs()
    try:
        syncdb()
    except sqlite3.DatabaseError as err:
        raise RuntimeError(
            _("Failed to open database file in %s. Try renaming this file and relaunch Lutris") %
            settings.PGA_DB
        ) from err
    for service in DEFAULT_SERVICES:
        if not settings.read_setting(service, section="services"):
            settings.write_setting(service, True, section="services")
    cleanup_games()


class StartupRuntimeUpdater(RuntimeUpdater):
    """Due to circular reference problems, we need to keep all these interesting
    references here, out of runtime.py"""
    dll_manager_classes = [DXVKManager, DXVKNVAPIManager, VKD3DManager, D3DExtrasManager, dgvoodoo2Manager]

    def __init__(self, force=False):
        super().__init__(force)
        for dll_manager_class in self.dll_manager_classes:
            key = dll_manager_class.__name__
            self.add_update(key, lambda c=dll_manager_class: self._update_dll_manager(c), hours=6)

        self.add_update("media", self._update_media, hours=240)

    def _update_dll_manager(self, dll_manager_class):
        dll_manager = dll_manager_class()
        dll_manager.upgrade()

    def _update_media(self):
        sync_media()
        update_all_artwork()
