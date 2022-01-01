"""Wine runner"""
# pylint: disable=too-many-lines
import os
import shlex
from gettext import gettext as _

from lutris import runtime, settings
from lutris.gui.dialogs import FileDialog
from lutris.runners.commands.wine import (  # noqa: F401 pylint: disable=unused-import
    create_prefix, delete_registry_key, eject_disc, install_cab_component, open_wine_terminal, set_regedit,
    set_regedit_file, winecfg, wineexec, winekill, winetricks
)
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.display import DISPLAY_MANAGER
from lutris.util.graphics.vkquery import is_vulkan_supported
from lutris.util.jobs import thread_safe_call
from lutris.util.log import logger
from lutris.util.strings import parse_version, split_arguments
from lutris.util.wine.d3d_extras import D3DExtrasManager
from lutris.util.wine.dgvoodoo2 import dgvoodoo2Manager
from lutris.util.wine.dxvk import DXVKManager
from lutris.util.wine.dxvk_nvapi import DXVKNVAPIManager
from lutris.util.wine.prefix import DEFAULT_DLL_OVERRIDES, WinePrefixManager, find_prefix
from lutris.util.wine.vkd3d import VKD3DManager
from lutris.util.wine.wine import (
    POL_PATH, WINE_DIR, WINE_PATHS, detect_arch, display_vulkan_error, esync_display_limit_warning,
    esync_display_version_warning, fsync_display_support_warning, fsync_display_version_warning, get_default_version,
    get_overrides_env, get_proton_paths, get_real_executable, get_wine_version, get_wine_versions, is_esync_limit_set,
    is_fsync_supported, is_gstreamer_build, is_version_esync, is_version_fsync
)

MIN_SAFE_VERSION = "5.0"  # Wine installers must run with at least this version


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
            "validator": shlex.split
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
            "help": _(
                'The prefix used by Wine.\n'
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
        "ShowCrashDialog": "MANAGED"
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

    def __init__(self, config=None):  # noqa: C901
        super().__init__(config)
        self.dll_overrides = DEFAULT_DLL_OVERRIDES

        def get_wine_version_choices():
            version_choices = [(_("Custom (select executable below)"), "custom")]
            labels = {
                "winehq-devel": _("WineHQ Devel ({})"),
                "winehq-staging": _("WineHQ Staging ({})"),
                "wine-development": _("Wine Development ({})"),
                "system": _("System ({})"),
            }
            versions = get_wine_versions()
            for version in versions:
                if version in labels:
                    version_number = get_wine_version(WINE_PATHS[version])
                    label = labels[version].format(version_number)
                else:
                    label = version
                version_choices.append((label, version))
            return version_choices

        def esync_limit_callback(widget, option, config):
            limits_set = is_esync_limit_set()
            wine_path = self.get_path_for_version(config["version"])
            wine_ver = is_version_esync(wine_path)
            response = True

            if not wine_ver:
                response = thread_safe_call(esync_display_version_warning)

            if not limits_set:
                thread_safe_call(esync_display_limit_warning)
                response = False

            return widget, option, response

        def fsync_support_callback(widget, option, config):
            fsync_supported = is_fsync_supported()
            wine_path = self.get_path_for_version(config["version"])
            wine_ver = is_version_fsync(wine_path)
            response = True

            if not wine_ver:
                response = thread_safe_call(fsync_display_version_warning)

            if not fsync_supported:
                thread_safe_call(fsync_display_support_warning)
                response = False

            return widget, option, response

        def dxvk_vulkan_callback(widget, option, config):
            response = True
            if not is_vulkan_supported():
                if not thread_safe_call(display_vulkan_error):
                    response = False
            return widget, option, response

        self.runner_options = [
            {
                "option": "version",
                "label": _("Wine version"),
                "type": "choice",
                "choices": get_wine_version_choices,
                "default": get_default_version(),
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
                "help": _("The Wine executable to be used if you have "
                          'selected "Custom" as the Wine version.'),
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
                "label": _("Enable DXVK"),
                "type": "extended_bool",
                "callback": dxvk_vulkan_callback,
                "callback_on": True,
                "default": True,
                "active": True,
                "help": _(
                    "Use DXVK to "
                    "increase compatibility and performance in Direct3D 11, 10 "
                    "and 9 applications by translating their calls to Vulkan."),
            },
            {
                "option": "dxvk_version",
                "label": _("DXVK version"),
                "advanced": True,
                "type": "choice_with_entry",
                "choices": DXVKManager().version_choices,
                "default": DXVKManager().version,
            },

            {
                "option": "vkd3d",
                "label": _("Enable VKD3D"),
                "type": "extended_bool",
                "callback": dxvk_vulkan_callback,
                "callback_on": True,
                "default": True,
                "active": True,
                "help": _(
                    "Use VKD3D to enable support for Direct3D 12 "
                    "applications by translating their calls to Vulkan."),
            },
            {
                "option": "vkd3d_version",
                "label": _("VKD3D version"),
                "advanced": True,
                "type": "choice_with_entry",
                "choices": VKD3DManager().version_choices,
                "default": VKD3DManager().version,
            },
            {
                "option": "d3d_extras",
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
                "label": _("D3D Extras version"),
                "advanced": True,
                "type": "choice_with_entry",
                "choices": D3DExtrasManager().version_choices,
                "default": D3DExtrasManager().version,
            },
            {
                "option": "dxvk_nvapi",
                "label": _("Enable DXVK-NVAPI / DLSS"),
                "type": "bool",
                "default": True,
                "advanced": True,
                "help": _(
                    "Enable emulation of Nvidia's NVAPI and add DLSS support, if available."
                ),
            },
            {
                "option": "dxvk_nvapi_version",
                "label": _("DXVK NVAPI version"),
                "advanced": True,
                "type": "choice_with_entry",
                "choices": DXVKNVAPIManager().version_choices,
                "default": DXVKNVAPIManager().version,
            },
            {
                "option": "dgvoodoo2",
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
                "label": _("dgvoodoo2 version"),
                "advanced": True,
                "type": "choice_with_entry",
                "choices": dgvoodoo2Manager().version_choices,
                "default": dgvoodoo2Manager().version,
            },
            {
                "option": "esync",
                "label": _("Enable Esync"),
                "type": "extended_bool",
                "callback": esync_limit_callback,
                "callback_on": True,
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
                "type": "extended_bool",
                "callback": fsync_support_callback,
                "callback_on": True,
                "active": True,
                "help": _(
                    "Enable futex-based synchronization (fsync). "
                    "This will increase performance in applications "
                    "that take advantage of multi-core processors. "
                    "Requires a custom kernel with the fsync patchset."
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
                "default": False,
                "help": _(
                    "Enable support for BattlEye Anti-Cheat in supported games\n"
                    "Requires Lutris Wine 6.21-2 and newer or any other compatible Wine build.\n"
                ),
            },
            {
                "option": "Desktop",
                "label": _("Windowed (virtual desktop)"),
                "type": "bool",
                "default": False,
                "help": _(
                    "Run the whole Windows desktop in a window.\n"
                    "Otherwise, run it fullscreen.\n"
                    "This corresponds to Wine's Virtual Desktop option."
                ),
            },
            {
                "option": "WineDesktop",
                "label": _("Virtual desktop resolution"),
                "type": "choice_with_entry",
                "choices": DISPLAY_MANAGER.get_resolutions,
                "help": _("The size of the virtual desktop in pixels."),
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
                "help": _("Output debugging information in the game log "
                          "(might affect performance)"),
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
                "help":
                _("Automatically disables one of Wine's detected joypad "
                  "to avoid having 2 controllers detected"),
            },
            {
                "option": "sandbox",
                "type": "bool",
                "label": _("Create a sandbox for Wine folders"),
                "default": True,
                "advanced": True,
                "help": _(
                    "Do not use $HOME for desktop integration folders.\n"
                    "By default, it use the directories in the confined "
                    "Windows environment."
                ),
            },
            {
                "option": "sandbox_dir",
                "type": "directory_chooser",
                "label": _("Sandbox directory"),
                "help": _("Custom directory for desktop integration folders."),
                "advanced": True,
            },
        ]

    @property
    def context_menu_entries(self):
        """Return the contexual menu entries for wine"""
        menu_entries = [("wineexec", _("Run EXE inside Wine prefix"), self.run_wineexec)]
        if "Proton" not in self.get_version():
            menu_entries.append(("winecfg", _("Wine configuration"), self.run_winecfg))
        menu_entries += [
            ("wineshell", _("Open Bash terminal"), self.run_wine_terminal),
            ("wineconsole", _("Open Wine console"), self.run_wineconsole),
            ("wine-regedit", _("Wine registry"), self.run_regedit),
            ("winekill", _("Kill all Wine processes"), self.run_winekill),
            ("winetricks", _("Winetricks"), self.run_winetricks),
            ("winecpl", _("Wine Control Panel"), self.run_winecpl),
        ]
        return menu_entries

    @property
    def prefix_path(self):
        """Return the absolute path of the Wine prefix"""
        _prefix_path = self.game_config.get("prefix") \
            or os.environ.get("WINEPREFIX") \
            or find_prefix(self.game_exe)
        if not _prefix_path:
            logger.warning(
                "Wine prefix not provided, defaulting to ~/.wine."
                " This is probably not the intended behavior."
            )
            _prefix_path = "~/.wine"
        return os.path.expanduser(_prefix_path)

    @property
    def game_exe(self):
        """Return the game's executable's path, which may not exist. None
        if there is no exe path defined."""
        exe = self.game_config.get("exe")
        if not exe:
            logger.warning("The game doesn't have an executable")
            return None
        if os.path.isabs(exe):
            return system.fix_path_case(exe)
        if not self.game_path:
            logger.warning("The game has an executable, but not a game path")
            return None
        return system.fix_path_case(os.path.join(self.game_path, exe))

    @property
    def working_dir(self):
        """Return the working directory to use when running the game."""
        option = self.game_config.get("working_dir")
        if option:
            return option
        if self.game_exe:
            game_dir = os.path.dirname(self.game_exe)
            if os.path.isdir(game_dir):
                return game_dir
        return super().working_dir

    @property
    def wine_arch(self):
        """Return the wine architecture.

        Get it from the config or detect it from the prefix"""
        arch = self.game_config.get("arch") or "auto"
        if arch not in ("win32", "win64"):
            arch = detect_arch(self.prefix_path, self.get_executable())
        return arch

    def get_version(self, use_default=True):
        """Return the Wine version to use. use_default can be set to false to
        force the installation of a specific wine version"""
        runner_version = self.runner_config.get("version")
        if runner_version:
            return runner_version
        if use_default:
            return get_default_version()

    def get_path_for_version(self, version):
        """Return the absolute path of a wine executable for a given version"""
        # logger.debug("Getting path for Wine %s", version)
        if version in WINE_PATHS:
            return system.find_executable(WINE_PATHS[version])
        if "Proton" in version:
            for proton_path in get_proton_paths():
                if os.path.isfile(os.path.join(proton_path, version, "dist/bin/wine")):
                    return os.path.join(proton_path, version, "dist/bin/wine")
        if version.startswith("PlayOnLinux"):
            version, arch = version.split()[1].rsplit("-", 1)
            return os.path.join(POL_PATH, "wine", "linux-" + arch, version, "bin/wine")
        if version == "custom":
            return self.runner_config.get("custom_wine_path", "")
        return os.path.join(WINE_DIR, version, "bin/wine")

    def get_executable(self, version=None, fallback=True):
        """Return the path to the Wine executable.
        A specific version can be specified if needed.
        """
        if version is None:
            version = self.get_version()
        if not version:
            return

        wine_path = self.get_path_for_version(version)
        if system.path_exists(wine_path):
            return wine_path

        if fallback:
            # Fallback to default version
            default_version = get_default_version()
            wine_path = self.get_path_for_version(default_version)
            if wine_path:
                # Update the version in the config
                if version == self.runner_config.get("version"):
                    self.runner_config["version"] = default_version
                    # TODO: runner_config is a dict so we have to instanciate a
                    # LutrisConfig object to save it.
                    # XXX: The version key could be either in the game specific
                    # config or the runner specific config. We need to know
                    # which one to get the correct LutrisConfig object.
            return wine_path

    def is_installed(self, version=None, fallback=True, min_version=None):
        """Check if Wine is installed.
        If no version is passed, checks if any version of wine is available
        """
        if version:
            return system.path_exists(self.get_executable(version, fallback))

        wine_versions = get_wine_versions()
        if min_version:
            min_version_list, _, _ = parse_version(min_version)
            for wine_version in wine_versions:
                version_list, _, _ = parse_version(wine_version)
                if version_list > min_version_list:
                    return True
            logger.warning("Wine %s or higher not found", min_version)
        return bool(wine_versions)

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
        )

    def run_regedit(self, *args):
        """Run regedit in the current context"""
        self.prelaunch()
        self._run_executable("regedit")

    def run_wine_terminal(self, *args):
        terminal = self.system_config.get("terminal_app")
        open_wine_terminal(
            terminal=terminal,
            wine_path=self.get_executable(),
            prefix=self.prefix_path,
            env=self.get_env(os_env=True)
        )

    def run_winetricks(self, *args):
        """Run winetricks in the current context"""
        self.prelaunch()
        winetricks(
            "", prefix=self.prefix_path, wine_path=self.get_executable(), config=self, env=self.get_env(os_env=True)
        )

    def run_winecpl(self, *args):
        """Execute Wine control panel."""
        self.prelaunch()
        self._run_executable("control")

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
                    managed_keys[key](value)
                    continue
                # Convert numeric strings to integers so they are saved as dword
                if value.isdigit():
                    value = int(value)

                prefix_manager.set_registry_key(path, key, value)

    def setup_dlls(self, manager_class, enable, version):
        """Enable or disable DLLs"""
        dll_manager = manager_class(
            self.prefix_path,
            arch=self.wine_arch,
            version=version,
        )
        # manual version only sets the dlls to native
        if dll_manager.version.lower() != "manual":
            if enable:
                dll_manager.enable()
            else:
                dll_manager.disable()

        if enable:
            for dll in dll_manager.managed_dlls:
                # We have to make sure that the dll exists before setting it to native
                if dll_manager.dll_exists(dll):
                    self.dll_overrides[dll] = "n"

    def prelaunch(self):
        if not system.path_exists(os.path.join(self.prefix_path, "user.reg")):
            create_prefix(self.prefix_path, arch=self.wine_arch)
        prefix_manager = WinePrefixManager(self.prefix_path)
        if self.runner_config.get("autoconf_joypad", False):
            prefix_manager.configure_joypads()
        self.sandbox(prefix_manager)
        self.set_regedit_keys()

        self.setup_dlls(
            DXVKManager,
            bool(self.runner_config.get("dxvk")),
            self.runner_config.get("dxvk_version")
        )
        self.setup_dlls(
            VKD3DManager,
            bool(self.runner_config.get("vkd3d")),
            self.runner_config.get("vkd3d_version")
        )
        self.setup_dlls(
            DXVKNVAPIManager,
            bool(self.runner_config.get("dxvk_nvapi")),
            self.runner_config.get("dxvk_nvapi_version")
        )
        self.setup_dlls(
            D3DExtrasManager,
            bool(self.runner_config.get("d3d_extras")),
            self.runner_config.get("d3d_extras_version")
        )
        self.setup_dlls(
            dgvoodoo2Manager,
            bool(self.runner_config.get("dgvoodoo2")),
            self.runner_config.get("dgvoodoo2_version")
        )
        return True

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

    def get_env(self, os_env=False):
        """Return environment variables used by the game"""
        # Always false to runner.get_env, the default value
        # of os_env is inverted in the wine class,
        # the OS env is read later.
        env = super().get_env(False)
        if os_env:
            env.update(os.environ.copy())
        show_debug = self.runner_config.get("show_debug", "-all")
        if show_debug != "inherit":
            env["WINEDEBUG"] = show_debug
        env["WINEARCH"] = self.wine_arch
        env["WINE"] = self.get_executable()
        if is_gstreamer_build(self.get_executable()):
            path_64 = os.path.join(WINE_DIR, self.get_version(), "lib64/gstreamer-1.0/")
            path_32 = os.path.join(WINE_DIR, self.get_version(), "lib/gstreamer-1.0/")
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

        if self.runner_config.get("battleye"):
            env["PROTON_BATTLEYE_RUNTIME"] = os.path.join(settings.RUNTIME_DIR, "battleye_runtime")

        overrides = self.get_dll_overrides()
        if overrides:
            self.dll_overrides.update(overrides)
        env["WINEDLLOVERRIDES"] = get_overrides_env(self.dll_overrides)
        return env

    def get_runtime_env(self):
        """Return runtime environment variables with path to wine for Lutris builds"""
        wine_path = self.get_executable()
        wine_root = None
        if WINE_DIR:
            wine_root = os.path.dirname(os.path.dirname(wine_path))
        for proton_path in get_proton_paths():
            if proton_path in wine_path:
                wine_root = os.path.dirname(os.path.dirname(wine_path))
        return runtime.get_env(
            version="Ubuntu-18.04",
            prefer_system_libs=self.system_config.get("prefer_system_libs", True),
            wine_path=wine_root,
        )

    def get_pids(self, wine_path=None):
        """Return a list of pids of processes using the current wine exe."""
        if wine_path:
            exe = wine_path
        else:
            exe = self.get_executable()
        if not exe.startswith("/"):
            exe = system.find_executable(exe)
        pids = system.get_pids_using_file(exe)
        if self.wine_arch == "win64" and os.path.basename(exe) == "wine":
            pids = pids | system.get_pids_using_file(exe + "64")

        # Add wineserver PIDs to the mix (at least one occurence of fuser not
        # picking the games's PID from wine/wine64 but from wineserver for some
        # unknown reason.
        pids = pids | system.get_pids_using_file(os.path.join(os.path.dirname(exe), "wineserver"))
        return pids

    def sandbox(self, wine_prefix):
        if self.runner_config.get("sandbox", True):
            wine_prefix.desktop_integration(desktop_dir=self.runner_config.get("sandbox_dir"))
        else:
            wine_prefix.desktop_integration(restore=True)

    def play(self):  # pylint: disable=too-many-return-statements # noqa: C901
        game_exe = self.game_exe
        arguments = self.game_config.get("args", "")
        launch_info = {"env": self.get_env(os_env=False)}
        using_dxvk = self.runner_config.get("dxvk")

        if using_dxvk:
            # Set this to 1 to enable access to more RAM for 32bit applications
            launch_info["env"]["WINE_LARGE_ADDRESS_AWARE"] = "1"
            if not is_vulkan_supported():
                if not display_vulkan_error(True):
                    return {"error": "VULKAN_NOT_FOUND"}

        if not game_exe or not system.path_exists(game_exe):
            return {"error": "FILE_NOT_FOUND", "file": game_exe}

        if launch_info["env"].get("WINEESYNC") == "1":
            limit_set = is_esync_limit_set()
            wine_ver = is_version_esync(self.get_executable())

            if not limit_set and not wine_ver:
                esync_display_version_warning(True)
                esync_display_limit_warning()
                return {"error": "ESYNC_LIMIT_NOT_SET"}
            if not is_esync_limit_set():
                esync_display_limit_warning()
                return {"error": "ESYNC_LIMIT_NOT_SET"}
            if not wine_ver:
                if not esync_display_version_warning(True):
                    return {"error": "NON_ESYNC_WINE_VERSION"}

        if launch_info["env"].get("WINEFSYNC") == "1":
            fsync_supported = is_fsync_supported()
            wine_ver = is_version_fsync(self.get_executable())

            if not fsync_supported and not wine_ver:
                fsync_display_version_warning(True)
                fsync_display_support_warning()
                return {"error": "FSYNC_NOT_SUPPORTED"}
            if not fsync_supported:
                fsync_display_support_warning()
                return {"error": "FSYNC_NOT_SUPPORTED"}
            if not wine_ver:
                if not fsync_display_version_warning(True):
                    return {"error": "NON_FSYNC_WINE_VERSION"}

        command = [self.get_executable()]

        game_exe, args, _working_dir = get_real_executable(game_exe, self.working_dir)
        command.append(game_exe)
        if args:
            command = command + args

        if arguments:
            for arg in split_arguments(arguments):
                command.append(arg)
        launch_info["command"] = command
        return launch_info

    @staticmethod
    def parse_wine_path(path, prefix_path=None):
        """Take a Windows path, return the corresponding Linux path."""
        if not prefix_path:
            prefix_path = os.path.expanduser("~/.wine")

        path = path.replace("\\\\", "/").replace("\\", "/")

        if path[1] == ":":  # absolute path
            drive = os.path.join(prefix_path, "dosdevices", path[:2].lower())
            if os.path.islink(drive):  # Try to resolve the path
                drive = os.readlink(drive)
            return os.path.join(drive, path[3:])

        if path[0] == "/":  # drive-relative path. C is as good a guess as any..
            return os.path.join(prefix_path, "drive_c", path[1:])

        # Relative path
        return path
