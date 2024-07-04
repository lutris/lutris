"""Wine runner"""

# pylint: disable=too-many-lines
import os
import shlex
from gettext import gettext as _
from typing import Any, Dict, Optional, Tuple

from lutris import runtime, settings
from lutris.api import format_runner_version, normalize_version_architecture
from lutris.config import LutrisConfig
from lutris.database.games import get_game_by_field
from lutris.exceptions import (
    EsyncLimitError,
    FsyncUnsupportedError,
    MisconfigurationError,
    MissingExecutableError,
    MissingGameExecutableError,
    UnspecifiedVersionError,
)
from lutris.game import Game
from lutris.gui.dialogs import FileDialog
from lutris.runners.commands.wine import (  # noqa: F401 pylint: disable=unused-import
    create_prefix,
    delete_registry_key,
    eject_disc,
    install_cab_component,
    open_wine_terminal,
    set_regedit,
    set_regedit_file,
    winecfg,
    wineexec,
    winekill,
    winetricks,
)
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.display import DISPLAY_MANAGER, get_default_dpi
from lutris.util.graphics import drivers, vkquery
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import logger
from lutris.util.strings import split_arguments
from lutris.util.wine import proton
from lutris.util.wine.d3d_extras import D3DExtrasManager
from lutris.util.wine.dgvoodoo2 import dgvoodoo2Manager
from lutris.util.wine.dxvk import REQUIRED_VULKAN_API_VERSION, DXVKManager
from lutris.util.wine.dxvk_nvapi import DXVKNVAPIManager
from lutris.util.wine.extract_icon import PEFILE_AVAILABLE, ExtractIcon
from lutris.util.wine.prefix import DEFAULT_DLL_OVERRIDES, WinePrefixManager, find_prefix
from lutris.util.wine.vkd3d import VKD3DManager
from lutris.util.wine.wine import (
    WINE_DEFAULT_ARCH,
    WINE_DIR,
    WINE_PATHS,
    detect_arch,
    get_default_wine_runner_version_info,
    get_default_wine_version,
    get_installed_wine_versions,
    get_overrides_env,
    get_real_executable,
    get_system_wine_version,
    get_wine_path_for_version,
    is_esync_limit_set,
    is_fsync_supported,
    is_gstreamer_build,
)


def _get_prefix_warning(config, _option_key):
    if config.get("prefix"):
        return None

    exe = config.get("exe")
    if exe and find_prefix(exe):
        return None

    return _("<b>Warning</b> Some Wine configuration options cannot be applied, if no prefix can be found.")


def _get_dxvk_warning(config, option_key):
    if drivers.is_outdated():
        driver_info = drivers.get_nvidia_driver_info()
        return _(
            "<b>Warning</b> Your NVIDIA driver is outdated.\n"
            "You are currently running driver %s which does not "
            "fully support all features for Vulkan and DXVK games."
        ) % (driver_info["version"],)

    return None


def _get_simple_vulkan_support_error(config, option_key, feature):
    if os.environ.get("LUTRIS_NO_VKQUERY"):
        return None
    if config.get(option_key) and not LINUX_SYSTEM.is_vulkan_supported():
        return (
            _("<b>Error</b> Vulkan is not installed or is not supported by your system, " "%s is not available.")
            % feature
        )
    return None


def _get_dxvk_version_warning(config, _option_key):
    if os.environ.get("LUTRIS_NO_VKQUERY"):
        return None
    if config.get("dxvk") and LINUX_SYSTEM.is_vulkan_supported():
        version = config.get("dxvk_version")
        if version and not version.startswith("v1."):
            library_api_version = vkquery.get_vulkan_api_version()
            if library_api_version and library_api_version < REQUIRED_VULKAN_API_VERSION:
                return _(
                    "<b>Warning</b> Lutris has detected that Vulkan API version %s is installed, "
                    "but to use the latest DXVK version, %s is required."
                ) % (vkquery.format_version(library_api_version), vkquery.format_version(REQUIRED_VULKAN_API_VERSION))

            devices = vkquery.get_device_info()

            if devices and devices[0].api_version < REQUIRED_VULKAN_API_VERSION:
                return _(
                    "<b>Warning</b> Lutris has detected that the best device available ('%s') supports Vulkan API %s, "
                    "but to use the latest DXVK version, %s is required."
                ) % (
                    devices[0].name,
                    vkquery.format_version(devices[0].api_version),
                    vkquery.format_version(REQUIRED_VULKAN_API_VERSION),
                )

    return None


def _get_esync_warning(config, _option_key):
    if config.get("esync"):
        limits_set = is_esync_limit_set()
        if not limits_set:
            return _(
                "<b>Warning</b> Your limits are not set correctly. Please increase them as described here:\n"
                "<a href='https://github.com/lutris/docs/blob/master/HowToEsync.md'>"
                "How-to-Esync (https://github.com/lutris/docs/blob/master/HowToEsync.md)</a>"
            )
    return ""


def _get_fsync_warning(config, _option_key):
    if config.get("fsync"):
        fsync_supported = is_fsync_supported()
        if not fsync_supported:
            return _("<b>Warning</b> Your kernel is not patched for fsync.")
        return ""


def _get_virtual_desktop_warning(config, _option_key):
    message = _("Wine virtual desktop is no longer supported")
    if config.get("Desktop"):
        version = str(config.get("version")).casefold()
        if "-ge-" in version or "proton" in version:
            message += "\n"
            message += _("Virtual desktops cannot be enabled in Proton or GE Wine versions.")
    return message


class wine(Runner):
    description = _("Runs Windows games")
    human_name = _("Wine")
    platforms = [_("Windows")]
    multiple_versions = True
    entry_point_option = "exe"

    game_options = [
        {
            "option": "exe",
            "type": "file",
            "label": _("Executable"),
            "help": _("The game's main EXE file"),
        },
        {
            "option": "args",
            "type": "string",
            "label": _("Arguments"),
            "help": _("Windows command line arguments used when launching the game"),
            "validator": shlex.split,
        },
        {
            "option": "working_dir",
            "type": "directory_chooser",
            "label": _("Working directory"),
            "help": _(
                "The location where the game is run from.\n"
                "By default, Lutris uses the directory of the "
                "executable."
            ),
        },
        {
            "option": "prefix",
            "type": "directory_chooser",
            "label": _("Wine prefix"),
            "warning": _get_prefix_warning,
            "help": _(
                "The prefix used by Wine.\n"
                "It's a directory containing a set of files and "
                "folders making up a confined Windows environment."
            ),
        },
        {
            "option": "arch",
            "type": "choice",
            "label": _("Prefix architecture"),
            "choices": [(_("Auto"), "auto"), (_("32-bit"), "win32"), (_("64-bit"), "win64")],
            "default": "auto",
            "help": _("The architecture of the Windows environment"),
        },
    ]

    reg_prefix = "HKEY_CURRENT_USER/Software/Wine"
    reg_keys = {
        "Audio": r"%s/Drivers" % reg_prefix,
        "MouseWarpOverride": r"%s/DirectInput" % reg_prefix,
        "Desktop": "MANAGED",
        "WineDesktop": "MANAGED",
        "ShowCrashDialog": "MANAGED",
    }

    core_processes = (
        "services.exe",
        "winedevice.exe",
        "plugplay.exe",
        "explorer.exe",
        "rpcss.exe",
        "rundll32.exe",
        "wineboot.exe",
    )

    def __init__(self, config=None, prefix=None, working_dir=None, wine_arch=None):  # noqa: C901
        super().__init__(config)
        self._prefix = prefix
        self._working_dir = working_dir
        self._wine_arch = wine_arch
        self.dll_overrides = DEFAULT_DLL_OVERRIDES.copy()  # we'll modify this, so we better copy it

        def get_wine_version_choices():
            version_choices = [(_("Custom (select executable below)"), "custom")]
            labels = {
                "winehq-devel": _("WineHQ Devel ({})"),
                "winehq-staging": _("WineHQ Staging ({})"),
                "wine-development": _("Wine Development ({})"),
                "system": _("System ({})"),
            }
            versions = get_installed_wine_versions()
            for version in versions:
                if version in labels:
                    version_number = get_system_wine_version(WINE_PATHS[version])
                    label = labels[version].format(version_number)
                else:
                    label = version
                version_choices.append((label, version))
            return version_choices

        self.runner_options = [
            {
                "option": "version",
                "label": _("Wine version"),
                "type": "choice",
                "choices": get_wine_version_choices,
                "default": get_default_wine_version,
                "help": _(
                    "The version of Wine used to launch the game.\n"
                    "Using the last version is generally recommended, "
                    "but some games work better on older versions."
                ),
            },
            {
                "option": "custom_wine_path",
                "label": _("Custom Wine executable"),
                "type": "file",
                "advanced": True,
                "help": _("The Wine executable to be used if you have " 'selected "Custom" as the Wine version.'),
            },
            {
                "option": "system_winetricks",
                "label": _("Use system winetricks"),
                "type": "bool",
                "default": False,
                "advanced": True,
                "help": _("Switch on to use /usr/bin/winetricks for winetricks."),
            },
            {
                "option": "dxvk",
                "section": _("Graphics"),
                "label": _("Enable DXVK"),
                "type": "bool",
                "default": True,
                "warning": _get_dxvk_warning,
                "error": lambda c, k: _get_simple_vulkan_support_error(c, k, _("DXVK")),
                "active": True,
                "help": _(
                    "Use DXVK to "
                    "increase compatibility and performance in Direct3D 11, 10 "
                    "and 9 applications by translating their calls to Vulkan."
                ),
            },
            {
                "option": "dxvk_version",
                "section": _("Graphics"),
                "label": _("DXVK version"),
                "advanced": True,
                "type": "choice_with_entry",
                "condition": LINUX_SYSTEM.is_vulkan_supported(),
                "choices": DXVKManager().version_choices,
                "default": DXVKManager().version,
                "warning": _get_dxvk_version_warning,
            },
            {
                "option": "vkd3d",
                "section": _("Graphics"),
                "label": _("Enable VKD3D"),
                "type": "bool",
                "error": lambda c, k: _get_simple_vulkan_support_error(c, k, _("VKD3D")),
                "default": True,
                "active": True,
                "help": _(
                    "Use VKD3D to enable support for Direct3D 12 " "applications by translating their calls to Vulkan."
                ),
            },
            {
                "option": "vkd3d_version",
                "section": _("Graphics"),
                "label": _("VKD3D version"),
                "advanced": True,
                "type": "choice_with_entry",
                "condition": LINUX_SYSTEM.is_vulkan_supported(),
                "choices": VKD3DManager().version_choices,
                "default": VKD3DManager().version,
            },
            {
                "option": "d3d_extras",
                "section": _("Graphics"),
                "label": _("Enable D3D Extras"),
                "type": "bool",
                "default": True,
                "advanced": True,
                "help": _(
                    "Replace Wine's D3DX and D3DCOMPILER libraries with alternative ones. "
                    "Needed for proper functionality of DXVK with some games."
                ),
            },
            {
                "option": "d3d_extras_version",
                "section": _("Graphics"),
                "label": _("D3D Extras version"),
                "advanced": True,
                "type": "choice_with_entry",
                "choices": D3DExtrasManager().version_choices,
                "default": D3DExtrasManager().version,
            },
            {
                "option": "dxvk_nvapi",
                "section": _("Graphics"),
                "label": _("Enable DXVK-NVAPI / DLSS"),
                "type": "bool",
                "error": lambda c, k: _get_simple_vulkan_support_error(c, k, _("DXVK-NVAPI / DLSS")),
                "default": True,
                "advanced": True,
                "help": _("Enable emulation of Nvidia's NVAPI and add DLSS support, if available."),
            },
            {
                "option": "dxvk_nvapi_version",
                "section": _("Graphics"),
                "label": _("DXVK NVAPI version"),
                "advanced": True,
                "type": "choice_with_entry",
                "choices": DXVKNVAPIManager().version_choices,
                "default": DXVKNVAPIManager().version,
            },
            {
                "option": "dgvoodoo2",
                "section": _("Graphics"),
                "label": _("Enable dgvoodoo2"),
                "type": "bool",
                "default": False,
                "advanced": False,
                "help": _(
                    "dgvoodoo2 is an alternative translation layer for rendering old games "
                    "that utilize D3D1-7 and Glide APIs. As it translates to D3D11, it's "
                    "recommended to use it in combination with DXVK. Only 32-bit apps are supported."
                ),
            },
            {
                "option": "dgvoodoo2_version",
                "section": _("Graphics"),
                "label": _("dgvoodoo2 version"),
                "advanced": True,
                "type": "choice_with_entry",
                "choices": dgvoodoo2Manager().version_choices,
                "default": dgvoodoo2Manager().version,
            },
            {
                "option": "esync",
                "label": _("Enable Esync"),
                "type": "bool",
                "warning": _get_esync_warning,
                "active": True,
                "default": True,
                "help": _(
                    "Enable eventfd-based synchronization (esync). "
                    "This will increase performance in applications "
                    "that take advantage of multi-core processors."
                ),
            },
            {
                "option": "fsync",
                "label": _("Enable Fsync"),
                "type": "bool",
                "default": is_fsync_supported(),
                "warning": _get_fsync_warning,
                "active": True,
                "help": _(
                    "Enable futex-based synchronization (fsync). "
                    "This will increase performance in applications "
                    "that take advantage of multi-core processors. "
                    "Requires kernel 5.16 or above."
                ),
            },
            {
                "option": "fsr",
                "label": _("Enable AMD FidelityFX Super Resolution (FSR)"),
                "type": "bool",
                "default": True,
                "help": _(
                    "Use FSR to upscale the game window to native resolution.\n"
                    "Requires Lutris Wine FShack >= 6.13 and setting the game to a lower resolution.\n"
                    "Does not work with games running in borderless window mode or that perform their own upscaling."
                ),
            },
            {
                "option": "battleye",
                "label": _("Enable BattlEye Anti-Cheat"),
                "type": "bool",
                "default": True,
                "help": _(
                    "Enable support for BattlEye Anti-Cheat in supported games\n"
                    "Requires Lutris Wine 6.21-2 and newer or any other compatible Wine build.\n"
                ),
            },
            {
                "option": "eac",
                "label": _("Enable Easy Anti-Cheat"),
                "type": "bool",
                "default": True,
                "help": _(
                    "Enable support for Easy Anti-Cheat in supported games\n"
                    "Requires Lutris Wine 7.2 and newer or any other compatible Wine build.\n"
                ),
            },
            {
                "option": "Desktop",
                "section": _("Virtual Desktop"),
                "label": _("Windowed (virtual desktop)"),
                "type": "bool",
                "advanced": True,
                "warning": _get_virtual_desktop_warning,
                "default": False,
                "help": _(
                    "Run the whole Windows desktop in a window.\n"
                    "Otherwise, run it fullscreen.\n"
                    "This corresponds to Wine's Virtual Desktop option."
                ),
            },
            {
                "option": "WineDesktop",
                "section": _("Virtual Desktop"),
                "label": _("Virtual desktop resolution"),
                "type": "choice_with_entry",
                "advanced": True,
                "choices": DISPLAY_MANAGER.get_resolutions,
                "help": _("The size of the virtual desktop in pixels."),
            },
            {
                "option": "Dpi",
                "section": _("DPI"),
                "label": _("Enable DPI Scaling"),
                "type": "bool",
                "advanced": True,
                "default": False,
                "help": _(
                    "Enables the Windows application's DPI scaling.\n"
                    "Otherwise, the Screen Resolution option in 'Wine configuration' controls this."
                ),
            },
            {
                "option": "ExplicitDpi",
                "section": _("DPI"),
                "label": _("DPI"),
                "type": "string",
                "advanced": True,
                "help": _(
                    "The DPI to be used if 'Enable DPI Scaling' is turned on.\n"
                    "If blank or 'auto', Lutris will auto-detect this."
                ),
            },
            {
                "option": "MouseWarpOverride",
                "label": _("Mouse Warp Override"),
                "type": "choice",
                "choices": [
                    (_("Enable"), "enable"),
                    (_("Disable"), "disable"),
                    (_("Force"), "force"),
                ],
                "default": "enable",
                "advanced": True,
                "help": _(
                    "Override the default mouse pointer warping behavior\n"
                    "<b>Enable</b>: (Wine default) warp the pointer when the "
                    "mouse is exclusively acquired \n"
                    "<b>Disable</b>: never warp the mouse pointer \n"
                    "<b>Force</b>: always warp the pointer"
                ),
            },
            {
                "option": "Audio",
                "label": _("Audio driver"),
                "type": "choice",
                "advanced": True,
                "choices": [
                    (_("Auto"), "auto"),
                    ("ALSA", "alsa"),
                    ("PulseAudio", "pulse"),
                    ("OSS", "oss"),
                ],
                "default": "auto",
                "help": _(
                    "Which audio backend to use.\n"
                    "By default, Wine automatically picks the right one "
                    "for your system."
                ),
            },
            {
                "option": "overrides",
                "type": "mapping",
                "label": _("DLL overrides"),
                "help": _("Sets WINEDLLOVERRIDES when launching the game."),
            },
            {
                "option": "show_debug",
                "label": _("Output debugging info"),
                "type": "choice",
                "choices": [
                    (_("Disabled"), "-all"),
                    (_("Enabled"), ""),
                    (_("Inherit from environment"), "inherit"),
                    (_("Show FPS"), "+fps"),
                    (_("Full (CAUTION: Will cause MASSIVE slowdown)"), "+all"),
                ],
                "default": "-all",
                "help": _("Output debugging information in the game log " "(might affect performance)"),
            },
            {
                "option": "ShowCrashDialog",
                "label": _("Show crash dialogs"),
                "type": "bool",
                "default": False,
                "advanced": True,
            },
            {
                "option": "autoconf_joypad",
                "type": "bool",
                "label": _("Autoconfigure joypads"),
                "advanced": True,
                "default": False,
                "help": _(
                    "Automatically disables one of Wine's detected joypad " "to avoid having 2 controllers detected"
                ),
            },
            {
                "option": "sandbox",
                "type": "bool",
                "section": _("Sandbox"),
                "label": _("Create a sandbox for Wine folders"),
                "default": True,
                "advanced": True,
                "help": _(
                    "Do not use $HOME for desktop integration folders.\n"
                    "By default, it will use the directories in the confined "
                    "Windows environment."
                ),
            },
            {
                "option": "sandbox_dir",
                "type": "directory_chooser",
                "section": _("Sandbox"),
                "label": _("Sandbox directory"),
                "warn_if_non_writable_parent": True,
                "help": _("Custom directory for desktop integration folders."),
                "advanced": True,
            },
        ]

    @property
    def runner_warning(self):
        if not get_system_wine_version():
            return _(
                "<b>Warning</b> Wine is not installed on your system\n\n"
                "Having Wine installed on your system guarantees that "
                "Wine builds from Lutris will have all required dependencies.\nPlease "
                "follow the instructions given in the <a "
                "href='https://github.com/lutris/docs/blob/master/WineDependencies.md'>Lutris Wiki</a> to "
                "install Wine."
            )

    @property
    def context_menu_entries(self):
        """Return the contexual menu entries for wine"""
        return [
            ("wineexec", _("Run EXE inside Wine prefix"), self.run_wineexec),
            ("wineshell", _("Open Bash terminal"), self.run_wine_terminal),
            ("wineconsole", _("Open Wine console"), self.run_wineconsole),
            (None, "-", None),
            ("winecfg", _("Wine configuration"), self.run_winecfg),
            ("wine-regedit", _("Wine registry"), self.run_regedit),
            ("winecpl", _("Wine Control Panel"), self.run_winecpl),
            ("winetaskmgr", _("Wine Task Manager"), self.run_taskmgr),
            (None, "-", None),
            ("winetricks", _("Winetricks"), self.run_winetricks),
        ]

    @property
    def prefix_path(self):
        """Return the absolute path of the Wine prefix. Falls back to default WINE prefix."""
        _prefix_path = self._prefix or self.game_config.get("prefix") or os.environ.get("WINEPREFIX")
        if not _prefix_path and self.game_config.get("exe"):
            # Find prefix from game if we have one
            _prefix_path = find_prefix(self.game_exe)
        if _prefix_path:
            _prefix_path = os.path.expanduser(_prefix_path)  # just in case!
        return _prefix_path

    @property
    def game_exe(self):
        """Return the game's executable's path, which may not exist. None
        if there is no exe path defined."""
        exe = self.game_config.get("exe")
        if not exe:
            logger.error("The game doesn't have an executable")
            return None
        exe = os.path.expanduser(exe)  # just in case!
        if os.path.isabs(exe):
            return system.fix_path_case(exe)
        if not self.game_path:
            logger.warning("The game has an executable, but not a game path")
            return None
        return system.fix_path_case(os.path.join(self.game_path, exe))

    @property
    def working_dir(self):
        """Return the working directory to use when running the game."""
        _working_dir = self._working_dir or self.game_config.get("working_dir")
        if _working_dir:
            return os.path.expanduser(_working_dir)
        if self.game_exe:
            game_dir = os.path.dirname(self.game_exe)
            if os.path.isdir(game_dir):
                return game_dir
        return super().working_dir

    @property
    def nvidia_shader_cache_path(self):
        """WINE should give each game its own shader cache if possible."""
        return self.game_path or self.shader_cache_dir

    @property
    def wine_arch(self):
        """Return the wine architecture.

        Get it from the config or detect it from the prefix"""
        arch = self._wine_arch or self.game_config.get("arch") or "auto"
        if arch not in ("win32", "win64"):
            prefix_path = self.prefix_path
            if prefix_path:
                arch = detect_arch(prefix_path, self.get_executable())
            else:
                arch = WINE_DEFAULT_ARCH
        return arch

    def get_runner_version(self, version: str = None) -> Optional[Dict[str, str]]:
        if not version:
            default_version_info = get_default_wine_runner_version_info()
            default_version = format_runner_version(default_version_info) if default_version_info else None
            version = self.read_version_from_config(default=default_version)

        if version in WINE_PATHS:
            return {"version": version}

        return super().get_runner_version(version)

    def read_version_from_config(self, default: str = None) -> str:
        """Return the Wine version to use. use_default can be set to false to
        force the installation of a specific wine version. If no version is configured,
        we return the default supplied, or the4 global Wine default if none is."""

        # We must use the config levels to avoid getting a default if the setting
        # is not set; we'll fall back to get_default_version()

        for level in [self.config.game_level, self.config.runner_level]:
            if "wine" in level:
                runner_version = level["wine"].get("version")
                if runner_version:
                    return runner_version

        if default:
            return default

        return get_default_wine_version()

    def get_path_for_version(self, version: str) -> str:
        """Return the absolute path of a wine executable for a given version"""
        return get_wine_path_for_version(version, config=self.runner_config)

    def resolve_config_path(self, path, relative_to=None):
        # Resolve paths with tolerance for Windows-isms;
        # first try to fix mismatched casing, and then if that
        # finds no file or directory, try again after swapping in
        # slashes for backslashes.

        resolved = super().resolve_config_path(path, relative_to)
        resolved = system.fix_path_case(resolved)

        if not os.path.exists(resolved) and "\\" in path:
            fixed = path.replace("\\", "/")
            fixed_resolved = super().resolve_config_path(fixed, relative_to)
            fixed_resolved = system.fix_path_case(fixed_resolved)
            return fixed_resolved

        return resolved

    def get_executable(self, version: str = None, fallback: bool = True) -> str:
        """Return the path to the Wine executable.
        A specific version can be specified if needed.
        """
        if version is None:
            version = self.read_version_from_config()
        if version == proton.GE_PROTON_LATEST:
            return proton.get_umu_path()

        try:
            wine_path = self.get_path_for_version(version)
        except MissingExecutableError:
            if not fallback:
                raise

        if system.path_exists(wine_path):
            return wine_path

        if not fallback:
            raise MissingExecutableError(_("The Wine executable at '%s' is missing.") % wine_path)

        # Fallback to default version
        default_version = get_default_wine_version()
        wine_path = self.get_path_for_version(default_version)
        if not system.path_exists(wine_path):
            raise MissingExecutableError(_("The Wine executable at '%s' is missing.") % wine_path)

        # Update the version in the config
        if version == self.runner_config.get("version"):
            self.runner_config["version"] = default_version
            # TODO: runner_config is a dict so we have to instanciate a
            # LutrisConfig object to save it.
            # XXX: The version key could be either in the game specific
            # config or the runner specific config. We need to know
            # which one to get the correct LutrisConfig object.
        return wine_path

    def is_installed(self, flatpak_allowed: bool = True, version: str = None, fallback: bool = True) -> bool:
        """Check if Wine is installed.
        If no version is passed, checks if any version of wine is available
        """
        try:
            if version:
                # We don't care where Wine is, but only if it was found at all.
                self.get_executable(version, fallback)
                return True

            return bool(get_installed_wine_versions())
        except MisconfigurationError:
            return False

    def is_installed_for(self, interpreter):
        try:
            version = self.get_installer_runner_version(interpreter.installer, use_api=True)
            return self.is_installed(version=version, fallback=False)
        except MisconfigurationError:
            return False

    def get_installer_runner_version(
        self, installer, use_runner_config: bool = True, use_api: bool = False
    ) -> Optional[str]:
        # If a version is specified in the script choose this one
        version = None
        if installer.script.get(installer.runner):
            version = installer.script[installer.runner].get("version")
            version = normalize_version_architecture(version)
        # If the installer is an extension, use the wine version from the base game
        elif installer.requires:
            db_game = get_game_by_field(installer.requires, field="installer_slug")
            if not db_game:
                db_game = get_game_by_field(installer.requires, field="slug")
            if not db_game:
                raise MisconfigurationError(_("The required game '%s' could not be found.") % installer.requires)
            game = Game(db_game["id"])
            version = game.config.runner_config["version"]

        if not version and use_runner_config:
            # Try to read the version from the saved runner config for Wine.
            try:
                return wine.get_runner_version_and_config()[0]
            except UnspecifiedVersionError:
                pass  # fall back to the API in this case

        if not version and use_api:
            # Try to obtain the default wine version from the Lutris API.
            default_version_info = self.get_runner_version()
            if default_version_info and "version" in default_version_info:
                logger.debug("Default wine version is %s", default_version_info["version"])
                version = format_runner_version(default_version_info)

        return version

    def adjust_installer_runner_config(self, installer_runner_config: Dict[str, Any]) -> None:
        version = installer_runner_config.get("version")
        if version:
            installer_runner_config["version"] = normalize_version_architecture(version)

    @classmethod
    def get_runner_version_and_config(cls) -> Tuple[str, LutrisConfig]:
        runner_config = LutrisConfig(runner_slug="wine")
        if "wine" in runner_config.runner_level:
            config_version = runner_config.runner_level["wine"].get("version")
            if config_version:
                return config_version, runner_config

        raise UnspecifiedVersionError(_("The runner configuration does not specify a Wine version."))

    @classmethod
    def msi_exec(
        cls,
        msi_file,
        quiet=False,
        prefix=None,
        wine_path=None,
        working_dir=None,
        blocking=False,
    ):
        msi_args = "/i %s" % msi_file
        if quiet:
            msi_args += " /q"
        return wineexec(
            "msiexec",
            args=msi_args,
            prefix=prefix,
            wine_path=wine_path,
            working_dir=working_dir,
            blocking=blocking,
        )

    def _run_executable(self, executable):
        """Runs a Windows executable using this game's configuration"""
        wineexec(
            executable,
            wine_path=self.get_executable(),
            prefix=self.prefix_path,
            working_dir=self.prefix_path,
            config=self,
            env=self.get_env(os_env=True),
            runner=self,
        )

    def run_wineexec(self, *args):
        """Ask the user for an arbitrary exe file to run in the game's prefix"""
        dlg = FileDialog(_("Select an EXE or MSI file"), default_path=self.game_path)
        filename = dlg.filename
        if not filename:
            return
        self.prelaunch()
        self._run_executable(filename)

    def run_wineconsole(self, *args):
        """Runs wineconsole inside wine prefix."""
        self.prelaunch()
        self._run_executable("wineconsole")

    def run_winecfg(self, *args):
        """Run winecfg in the current context"""
        self.prelaunch()
        winecfg(
            wine_path=self.get_executable(),
            prefix=self.prefix_path,
            arch=self.wine_arch,
            config=self,
            env=self.get_env(os_env=True),
            runner=self,
        )

    def run_regedit(self, *args):
        """Run regedit in the current context"""
        self.prelaunch()
        self._run_executable("regedit")

    def run_wine_terminal(self, *args):
        terminal = self.system_config.get("terminal_app")
        system_winetricks = self.runner_config.get("system_winetricks")
        open_wine_terminal(
            terminal=terminal,
            wine_path=self.get_executable(),
            prefix=self.prefix_path,
            env=self.get_env(os_env=True),
            system_winetricks=system_winetricks,
        )

    def run_winetricks(self, *args):
        """Run winetricks in the current context"""
        self.prelaunch()
        disable_runtime = not self.use_runtime()
        system_winetricks = self.runner_config.get("system_winetricks")
        if system_winetricks:
            # Don't run the system winetricks with the runtime; let the
            # system be the system
            disable_runtime = True
        winetricks(
            "",
            prefix=self.prefix_path,
            wine_path=self.get_executable(),
            config=self,
            disable_runtime=disable_runtime,
            system_winetricks=system_winetricks,
            env=self.get_env(os_env=True, disable_runtime=disable_runtime),
            runner=self,
        )

    def run_winecpl(self, *args):
        """Execute Wine control panel."""
        self.prelaunch()
        self._run_executable("control")

    def run_taskmgr(self, *args):
        """Execute Wine task manager"""
        self.prelaunch()
        self._run_executable("taskmgr")

    def run_winekill(self, *args):
        """Runs wineserver -k."""

        winekill(
            self.prefix_path,
            arch=self.wine_arch,
            wine_path=self.get_executable(),
            env=self.get_env(),
            initial_pids=self.get_pids(),
        )
        return True

    def set_regedit_keys(self):
        """Reset regedit keys according to config."""
        prefix_manager = WinePrefixManager(self.prefix_path)
        # Those options are directly changed with the prefix manager and skip
        # any calls to regedit.
        managed_keys = {
            "ShowCrashDialog": prefix_manager.set_crash_dialogs,
            "Desktop": prefix_manager.set_virtual_desktop,
            "WineDesktop": prefix_manager.set_desktop_size,
        }
        for key, path in self.reg_keys.items():
            value = self.runner_config.get(key) or "auto"
            if not value or value == "auto" and key not in managed_keys:
                prefix_manager.clear_registry_subkeys(path, key)
            elif key in self.runner_config:
                if key in managed_keys:
                    # Do not pass fallback 'auto' value to managed keys
                    if value == "auto":
                        value = None
                    if (
                        value
                        and key in ("Desktop", "WineDesktop")
                        and ("wine-ge" in self.get_executable().lower() or "proton" in self.get_executable().lower())
                    ):
                        logger.warning("Wine Virtual Desktop can't be used with Wine-GE and Proton")
                        value = None
                    managed_keys[key](value)
                    continue
                # Convert numeric strings to integers so they are saved as dword
                if value.isdigit():
                    value = int(value)

                prefix_manager.set_registry_key(path, key, value)

        # We always configure the DPI, because if the user turns off DPI scaling, but it
        # had been on the only way to implement that is to save 96 DPI into the registry.
        prefix_manager.set_dpi(self.get_dpi())

    def get_dpi(self):
        """Return the DPI to be used by Wine; returns None to allow Wine's own
        setting to govern."""
        if bool(self.runner_config.get("Dpi")):
            explicit_dpi = self.runner_config.get("ExplicitDpi")
            if explicit_dpi == "auto":
                explicit_dpi = None
            else:
                try:
                    explicit_dpi = int(explicit_dpi)
                except:
                    explicit_dpi = None
            return explicit_dpi or get_default_dpi()

        return None

    def prelaunch(self):
        if not get_system_wine_version():
            logger.warning("Wine is not installed on your system; required dependencies may be missing.")

        prefix_path = self.prefix_path
        if prefix_path:
            if not system.path_exists(os.path.join(prefix_path, "user.reg")):
                logger.warning("No valid prefix detected in %s, creating one...", prefix_path)
                create_prefix(prefix_path, wine_path=self.get_executable(), arch=self.wine_arch, runner=self)

            prefix_manager = WinePrefixManager(prefix_path)
            if self.runner_config.get("autoconf_joypad", False):
                prefix_manager.configure_joypads()
            prefix_manager.create_user_symlinks()
            self.sandbox(prefix_manager)
            self.set_regedit_keys()

            for manager, enabled in self.get_dll_managers().items():
                manager.setup(enabled)

    def get_dll_managers(self, enabled_only=False):
        """Returns the DLL managers in a dict; the keys are the managers themselves,
        and the values are the enabled flags for them. If 'enabled_only' is true,
        only enabled managers are returned, so disabled managers are not created."""
        manager_classes = [
            (DXVKManager, "dxvk", "dxvk_version"),
            (VKD3DManager, "vkd3d", "vkd3d_version"),
            (DXVKNVAPIManager, "dxvk_nvapi", "dxvk_nvapi_version"),
            (D3DExtrasManager, "d3d_extras", "d3d_extras_version"),
            (dgvoodoo2Manager, "dgvoodoo2", "dgvoodoo2_version"),
        ]

        managers = {}
        for manager_class, enabled_option, version_option in manager_classes:
            enabled = bool(self.runner_config.get(enabled_option))
            version = self.runner_config.get(version_option)
            if enabled or not enabled_only:
                manager = manager_class(self.prefix_path, arch=self.wine_arch, version=version)

                if not manager.can_enable():
                    enabled = False
                    if enabled_only:
                        continue

                managers[manager] = enabled

        return managers

    def get_dll_overrides(self):
        """Return the DLLs overriden at runtime"""
        try:
            overrides = self.runner_config["overrides"]
        except KeyError:
            overrides = {}
        if not isinstance(overrides, dict):
            logger.warning("DLL overrides is not a mapping: %s", overrides)
            overrides = {}
        return overrides

    def get_env(self, os_env=False, disable_runtime=False):
        """Return environment variables used by the game"""
        # Always false to runner.get_env, the default value
        # of os_env is inverted in the wine class,
        # the OS env is read later.
        env = super().get_env(os_env, disable_runtime=disable_runtime)
        show_debug = self.runner_config.get("show_debug", "-all")
        if show_debug != "inherit":
            env["WINEDEBUG"] = show_debug
        if show_debug == "-all":
            env["DXVK_LOG_LEVEL"] = "none"
        env["WINEARCH"] = self.wine_arch
        wine_exe = self.get_executable()
        wine_config_version = self.read_version_from_config()
        env["WINE"] = wine_exe
        env["WINE_MONO_CACHE_DIR"] = os.path.join(WINE_DIR, wine_config_version, "mono")
        env["WINE_GECKO_CACHE_DIR"] = os.path.join(WINE_DIR, wine_config_version, "gecko")

        # We don't want to override gstreamer for proton, it has it's own version
        if not proton.is_proton_path(WINE_DIR) and is_gstreamer_build(wine_exe):
            path_64 = os.path.join(WINE_DIR, wine_config_version, "lib64/gstreamer-1.0/")
            path_32 = os.path.join(WINE_DIR, wine_config_version, "lib/gstreamer-1.0/")
            if os.path.exists(path_64) or os.path.exists(path_32):
                env["GST_PLUGIN_SYSTEM_PATH_1_0"] = path_64 + ":" + path_32

        if self.prefix_path:
            env["WINEPREFIX"] = self.prefix_path

        if not ("WINEESYNC" in env and env["WINEESYNC"] == "1"):
            env["WINEESYNC"] = "1" if self.runner_config.get("esync") else "0"

        if not ("WINEFSYNC" in env and env["WINEFSYNC"] == "1"):
            env["WINEFSYNC"] = "1" if self.runner_config.get("fsync") else "0"

        if self.runner_config.get("fsr"):
            env["WINE_FULLSCREEN_FSR"] = "1"

        if self.runner_config.get("dxvk_nvapi"):
            env["DXVK_NVAPIHACK"] = "0"
            env["DXVK_ENABLE_NVAPI"] = "1"

        if self.runner_config.get("battleye"):
            env["PROTON_BATTLEYE_RUNTIME"] = os.path.join(settings.RUNTIME_DIR, "battleye_runtime")

        if self.runner_config.get("eac"):
            env["PROTON_EAC_RUNTIME"] = os.path.join(settings.RUNTIME_DIR, "eac_runtime")

        for dll_manager in self.get_dll_managers(enabled_only=True):
            self.dll_overrides.update(dll_manager.get_enabling_dll_overrides())

        overrides = self.get_dll_overrides()
        if overrides:
            self.dll_overrides.update(overrides)

        env["WINEDLLOVERRIDES"] = get_overrides_env(self.dll_overrides)

        return env

    def finish_env(self, env: Dict[str, str], game) -> None:
        super().finish_env(env, game)

        wine_exe = self.get_executable()

        if proton.is_proton_path(wine_exe):
            game_id = proton.get_game_id(game, env)
            proton.update_proton_env(wine_exe, env, game_id=game_id)

    def get_runtime_env(self):
        """Return runtime environment variables with path to wine for Lutris builds"""
        wine_path = None
        try:
            exe = self.get_executable()
            if WINE_DIR:
                wine_path = os.path.dirname(os.path.dirname(exe))
            for proton_path in proton.get_proton_paths():
                if proton_path in exe:
                    wine_path = os.path.dirname(os.path.dirname(exe))
        except MisconfigurationError:
            wine_path = None

        return runtime.get_env(
            version="Ubuntu-18.04",
            prefer_system_libs=self.system_config.get("prefer_system_libs", True),
            wine_path=wine_path,
        )

    def get_pids(self, wine_path=None):
        """Return a list of pids of processes using the current wine exe."""
        try:
            exe = wine_path or self.get_executable()
        except MisconfigurationError:
            return set()
        if proton.is_proton_path(exe):
            logger.debug("Tracking PIDs of Proton games is not possible at the moment")
            return set()
        if not exe.startswith("/"):
            exe = system.find_required_executable(exe)
        pids = system.get_pids_using_file(exe)
        if self.wine_arch == "win64" and os.path.basename(exe) == "wine":
            pids = pids | system.get_pids_using_file(exe + "64")

        # Add wineserver PIDs to the mix (at least one occurence of fuser not
        # picking the games's PID from wine/wine64 but from wineserver for some
        # unknown reason.
        pids = pids | system.get_pids_using_file(os.path.join(os.path.dirname(exe), "wineserver"))
        return pids

    def sandbox(self, wine_prefix):
        try:
            if self.runner_config.get("sandbox", True):
                wine_prefix.enable_desktop_integration_sandbox(desktop_dir=self.runner_config.get("sandbox_dir"))
            else:
                wine_prefix.restore_desktop_integration()
        except Exception as ex:
            logger.exception("Failed to setup desktop integration, the prefix may not be valid: %s", ex)

    def play(self):  # pylint: disable=too-many-return-statements # noqa: C901
        game_exe = self.game_exe
        arguments = self.game_config.get("args", "")
        launch_info = {"env": self.get_env(os_env=False)}
        using_dxvk = self.runner_config.get("dxvk")

        if using_dxvk:
            # Set this to 1 to enable access to more RAM for 32bit applications
            launch_info["env"]["WINE_LARGE_ADDRESS_AWARE"] = "1"

        if not game_exe or not system.path_exists(game_exe):
            raise MissingGameExecutableError(filename=game_exe)

        if launch_info["env"].get("WINEESYNC") == "1":
            limit_set = is_esync_limit_set()

            if not limit_set:
                raise EsyncLimitError()

        if launch_info["env"].get("WINEFSYNC") == "1":
            fsync_supported = is_fsync_supported()

            if not fsync_supported:
                raise FsyncUnsupportedError()

        command = self.get_command()

        game_exe, args, _working_dir = get_real_executable(game_exe, self.working_dir)
        command.append(game_exe)
        if args:
            command = command + args

        if arguments:
            for arg in split_arguments(arguments):
                command.append(arg)
        launch_info["command"] = command
        return launch_info

    def force_stop_game(self, game):
        """Kill WINE with kindness, or at least with -k. This seems to leave a process
        alive for some reason, but the caller will detect this and SIGKILL it."""
        self.run_winekill()

    def extract_icon(self, game_slug):
        """Extracts the 128*128 icon from EXE and saves it, if not resizes the biggest icon found.
        returns true if an icon is saved, false if not"""

        try:
            wantedsize = (128, 128)
            pathtoicon = settings.ICON_PATH + "/lutris_" + game_slug + ".png"
            exe = self.game_exe
            if not exe or os.path.exists(pathtoicon) or not PEFILE_AVAILABLE:
                return False

            extractor = ExtractIcon(self.game_exe)
            groups = extractor.get_group_icons()

            if not groups:
                return False

            icons = []
            biggestsize = (0, 0)
            biggesticon = -1
            for i in range(len(groups[0])):
                icons.append(extractor.export(groups[0], i))
                if icons[i].size > biggestsize:
                    biggesticon = i
                    biggestsize = icons[i].size
                elif icons[i].size == wantedsize:
                    icons[i].save(pathtoicon)
                    return True

            if biggesticon >= 0:
                resized = icons[biggesticon].resize(wantedsize)
                resized.save(pathtoicon)
                return True
            return False
        except Exception as ex:
            logger.exception("Unable to extract icon from %s: %s", exe, ex)
            return False
