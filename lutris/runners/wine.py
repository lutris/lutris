"""Wine runner"""
# pylint: disable=too-many-arguments
import os
import shlex
import shutil

from lutris import runtime
from lutris.settings import RUNTIME_DIR
from lutris.exceptions import GameConfigError
from lutris.gui.dialogs import FileDialog
from lutris.runners.runner import Runner
from lutris.util.jobs import thread_safe_call
from lutris.util import system
from lutris.util.log import logger
from lutris.util.strings import parse_version, split_arguments
from lutris.util.display import DISPLAY_MANAGER
from lutris.util.graphics.vkquery import is_vulkan_supported
from lutris.util.wine.prefix import WinePrefixManager
from lutris.util.wine.x360ce import X360ce
from lutris.util.wine import dxvk
from lutris.util.wine import nine
from lutris.util.wine.wine import (
    POL_PATH,
    WINE_DIR,
    WINE_PATHS,
    detect_arch,
    display_vulkan_error,
    esync_display_limit_warning,
    esync_display_version_warning,
    get_default_version,
    get_overrides_env,
    get_proton_paths,
    get_real_executable,
    get_system_wine_version,
    get_wine_versions,
    is_esync_limit_set,
    is_version_esync,
)
from lutris.runners.commands.wine import (  # noqa pylint: disable=unused-import
    create_prefix,
    delete_registry_key,
    eject_disc,
    set_regedit,
    set_regedit_file,
    winecfg,
    wineexec,
    winekill,
    winetricks,
    install_cab_component,
)

MIN_SAFE_VERSION = "4.0"  # Wine installers must run with at least this version


class wine(Runner):
    description = "Runs Windows games"
    human_name = "Wine"
    platforms = ["Windows"]
    multiple_versions = True
    game_options = [
        {
            "option": "exe",
            "type": "file",
            "label": "Executable",
            "help": "The game's main EXE file",
        },
        {
            "option": "args",
            "type": "string",
            "label": "Arguments",
            "help": "Windows command line arguments used when launching the game",
            "validator": shlex.split
        },
        {
            "option": "working_dir",
            "type": "directory_chooser",
            "label": "Working directory",
            "help": (
                "The location where the game is run from.\n"
                "By default, Lutris uses the directory of the "
                "executable."
            ),
        },
        {
            "option": "prefix",
            "type": "directory_chooser",
            "label": "Wine prefix",
            "help": (
                'The prefix (also named "bottle") used by Wine.\n'
                "It's a directory containing a set of files and "
                "folders making up a confined Windows environment."
            ),
        },
        {
            "option": "arch",
            "type": "choice",
            "label": "Prefix architecture",
            "choices": [("Auto", "auto"), ("32-bit", "win32"), ("64-bit", "win64")],
            "default": "auto",
            "help": "The architecture of the Windows environment",
        },
    ]

    reg_prefix = "HKEY_CURRENT_USER/Software/Wine"
    reg_keys = {
        "Audio": r"%s/Drivers" % reg_prefix,
        "MouseWarpOverride": r"%s/DirectInput" % reg_prefix,
        "OffscreenRenderingMode": r"%s/Direct3D" % reg_prefix,
        "StrictDrawOrdering": r"%s/Direct3D" % reg_prefix,
        "SampleCount": r"%s/Direct3D" % reg_prefix,
        "Desktop": "MANAGED",
        "WineDesktop": "MANAGED",
        "ShowCrashDialog": "MANAGED",
        "UseXVidMode": "MANAGED",
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

    def __init__(self, config=None):
        super(wine, self).__init__(config)
        self.dll_overrides = {
            "winemenubuilder.exe": "d"
        }

        def get_wine_version_choices():
            version_choices = [("Custom (select executable below)", "custom")]
            labels = {
                "winehq-devel": "WineHQ devel ({})",
                "winehq-staging": "WineHQ staging ({})",
                "wine-development": "Wine Development ({})",
                "system": "System ({})",
            }
            versions = get_wine_versions()
            for version in versions:
                if version in labels.keys():
                    version_number = get_system_wine_version(WINE_PATHS[version])
                    label = labels[version].format(version_number)
                else:
                    label = version
                version_choices.append((label, version))
            return version_choices

        def dxvk_choices(manager_class):
            version_choices = [
                ("Manual", "manual"),
                (manager_class.DXVK_LATEST, manager_class.DXVK_LATEST),
            ]
            for version in manager_class.DXVK_PAST_RELEASES:
                version_choices.append((version, version))
            return version_choices

        def get_dxvk_choices():
            return dxvk_choices(dxvk.DXVKManager)

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

        def dxvk_vulkan_callback(widget, option, config):
            response = True
            if not is_vulkan_supported():
                if not thread_safe_call(display_vulkan_error):
                    response = False
            return widget, option, response

        self.runner_options = [
            {
                "option": "version",
                "label": "Wine version",
                "type": "choice",
                "choices": get_wine_version_choices,
                "default": get_default_version(),
                "help": (
                    "The version of Wine used to launch the game.\n"
                    "Using the last version is generally recommended, "
                    "but some games work better on older versions."
                ),
            },
            {
                "option": "custom_wine_path",
                "label": "Custom Wine executable",
                "type": "file",
                "advanced": True,
                "help": (
                    "The Wine executable to be used if you have "
                    'selected "Custom" as the Wine version.'
                ),
            },
            {
                "option": "system_winetricks",
                "label": "Use system winetricks",
                "type": "bool",
                "default": False,
                "advanced": True,
                "help": "Switch on to use /usr/bin/winetricks for winetricks.",
            },
            {
                "option": "dxvk",
                "label": "Enable DXVK",
                "type": "extended_bool",
                "callback": dxvk_vulkan_callback,
                "callback_on": True,
                "default": True,
                "active": True,
                "help": (
                    "Use DXVK to increase compatibility and performance "
                    "in Direct3D 11 and 10 applications by translating "
                    "their calls to Vulkan."
                ),
            },
            {
                "option": "dxvk_version",
                "label": "DXVK version",
                "advanced": True,
                "type": "choice_with_entry",
                "choices": get_dxvk_choices,
                "default": dxvk.DXVKManager.DXVK_LATEST,
            },
            {
                "option": "vkd3d",
                "label": "Enable VKD3D",
                "type": "bool",
                "default": False,
                "help": (
                    "Enable DX12 support with VKD3D. This requires a compatible Wine build."
                )
            },
            {
                "option": "esync",
                "label": "Enable Esync",
                "type": "extended_bool",
                "callback": esync_limit_callback,
                "callback_on": True,
                "active": True,
                "help": (
                    "Enable eventfd-based synchronization (esync). "
                    "This will increase performance in applications "
                    "that take advantage of multi-core processors."
                ),
            },
            {
                "option": "gallium_nine",
                "label": "Enable Gallium Nine",
                "type": "bool",
                "default": False,
                "condition": nine.NineManager.is_available(),
                "advanced": True,
                "help": (
                    "Gallium Nine allows to run Direct3D 9 applications faster.\n"
                    "Make sure your active graphics card supports Gallium Nine state "
                    "tracker before enabling this option.\n"
                    "Note: This feature is not supported by proprietary Nvidia driver."
                ),
            },
            {
                "option": "x360ce-path",
                "label": "Path to the game's executable, for x360ce support",
                "type": "directory_chooser",
                "help": "Locate the path for the game's executable for x360 support",
                "advanced": True,
            },
            {
                "option": "x360ce-dinput",
                "label": "x360ce dinput 8 mode",
                "type": "bool",
                "default": False,
                "help": "Configure x360ce with dinput8.dll, required for some games",
                "advanced": True,
            },
            {
                "option": "x360ce-xinput9",
                "label": "x360ce xinput 9.1.0 mode",
                "type": "bool",
                "default": False,
                "help": "Configure x360ce with xinput9_1_0.dll, required for some newer games",
                "advanced": True,
            },
            {
                "option": "dumbxinputemu",
                "label": "Use Dumb xinput Emulator (experimental)",
                "type": "bool",
                "default": False,
                "help": "Use the dlls from kozec/dumbxinputemu",
                "advanced": True,
            },
            {
                "option": "xinput-arch",
                "label": "Xinput architecture",
                "type": "choice",
                "choices": [
                    ("Same as wine prefix", ""),
                    ("32 bit", "win32"),
                    ("64 bit", "win64"),
                ],
                "default": "",
                "advanced": True,
            },
            {
                "option": "Desktop",
                "label": "Windowed (virtual desktop)",
                "type": "bool",
                "default": False,
                "help": (
                    "Run the whole Windows desktop in a window.\n"
                    "Otherwise, run it fullscreen.\n"
                    "This corresponds to Wine's Virtual Desktop option."
                ),
            },
            {
                "option": "WineDesktop",
                "label": "Virtual desktop resolution",
                "type": "choice_with_entry",
                "choices": DISPLAY_MANAGER.get_resolutions,
                "help": "The size of the virtual desktop in pixels.",
            },
            {
                "option": "MouseWarpOverride",
                "label": "Mouse Warp Override",
                "type": "choice",
                "choices": [
                    ("Enable", "enable"),
                    ("Disable", "disable"),
                    ("Force", "force"),
                ],
                "default": "enable",
                "advanced": True,
                "help": (
                    "Override the default mouse pointer warping behavior\n"
                    "<b>Enable</b>: (Wine default) warp the pointer when the "
                    "mouse is exclusively acquired \n"
                    "<b>Disable</b>: never warp the mouse pointer \n"
                    "<b>Force</b>: always warp the pointer"
                ),
            },
            {
                "option": "OffscreenRenderingMode",
                "label": "Offscreen Rendering Mode",
                "type": "choice",
                "choices": [("FBO", "fbo"), ("BackBuffer", "backbuffer")],
                "default": "fbo",
                "advanced": True,
                "help": (
                    "Select the offscreen rendering implementation.\n"
                    "<b>FBO</b>: (Wine default) Use framebuffer objects "
                    "for offscreen rendering \n"
                    "<b>Backbuffer</b>: Render offscreen render targets "
                    "in the backbuffer."
                ),
            },
            {
                "option": "StrictDrawOrdering",
                "label": "Strict Draw Ordering",
                "type": "choice",
                "choices": [("Enabled", "enabled"), ("Disabled", "disabled")],
                "default": "disabled",
                "advanced": True,
                "help": (
                    "This option ensures any pending drawing operations are "
                    "submitted to the driver, but at a significant performance "
                    'cost. Set to "enabled" to enable. This setting is deprecated '
                    "since wine-2.6 and will likely be removed after wine-3.0. "
                    'Use "csmt" instead.'
                ),
            },
            {
                "option": "UseGLSL",
                "label": "Use GLSL",
                "type": "choice",
                "choices": [("Enabled", "enabled"), ("Disabled", "disabled")],
                "default": "enabled",
                "advanced": True,
                "help": (
                    'When set to "disabled", this disables the use of GLSL for shaders. '
                    "In general disabling GLSL is not recommended, "
                    "only use this for debugging purposes."
                ),
            },
            {
                "option": "SampleCount",
                "label": "Anti-aliasing Sample Count",
                "type": "choice",
                "choices": [
                    ("Auto", "auto"),
                    ("0", "0"),
                    ("2", "2"),
                    ("4", "4"),
                    ("8", "8"),
                    ("16", "16"),
                ],
                "default": "auto",
                "advanced": True,
                "help": (
                    "Override swapchain sample count. It can be used to force enable multisampling "
                    "with applications that otherwise don't support it, like the similar control "
                    "panel setting available with some GPU drivers. This one might work in more "
                    "cases than the driver setting though. "
                    "Not all applications are compatible with all sample counts. "
                ),
            },
            {
                "option": "UseXVidMode",
                "label": "Use XVidMode to switch resolutions",
                "type": "bool",
                "default": False,
                "advanced": True,
                "help": (
                    'Set this to "Y" to allow wine switch the resolution using XVidMode extension.'
                ),
            },
            {
                "option": "Audio",
                "label": "Audio driver",
                "type": "choice",
                "advanced": True,
                "choices": [
                    ("Auto", "auto"),
                    ("ALSA", "alsa"),
                    ("PulseAudio", "pulse"),
                    ("OSS", "oss"),
                ],
                "default": "auto",
                "help": (
                    "Which audio backend to use.\n"
                    "By default, Wine automatically picks the right one "
                    "for your system."
                ),
            },
            {
                "option": "overrides",
                "type": "mapping",
                "label": "DLL overrides",
                "help": "Sets WINEDLLOVERRIDES when launching the game.",
            },
            {
                "option": "show_debug",
                "label": "Output debugging info",
                "type": "choice",
                "choices": [
                    ("Disabled", "-all"),
                    ("Enabled", ""),
                    ("Inherit from environment", "inherit"),
                    ("Show FPS", "+fps"),
                    ("Full (CAUTION: Will cause MASSIVE slowdown)", "+all"),
                ],
                "default": "-all",
                "help": (
                    "Output debugging information in the game log "
                    "(might affect performance)"
                ),
            },
            {
                "option": "ShowCrashDialog",
                "label": "Show crash dialogs",
                "type": "bool",
                "default": False,
                "advanced": True,
            },
            {
                "option": "autoconf_joypad",
                "type": "bool",
                "label": "Autoconfigure joypads",
                "advanced": True,
                "default": True,
                "help": (
                    "Automatically disables one of Wine's detected joypad "
                    "to avoid having 2 controllers detected"
                ),
            },
            {
                "option": "sandbox",
                "type": "bool",
                "label": "Create a sandbox for wine folders",
                "default": True,
                "advanced": True,
                "help": (
                    "Do not use $HOME for desktop integration folders.\n"
                    "By default, it use the directories in the confined "
                    "Windows environment."
                ),
            },
            {
                "option": "sandbox_dir",
                "type": "directory_chooser",
                "label": "Sandbox directory",
                "help": "Custom directory for desktop integration folders.",
                "advanced": True,
            },
        ]

    @property
    def context_menu_entries(self):
        """Return the contexual menu entries for wine"""
        menu_entries = [("wineexec", "Run EXE inside wine prefix", self.run_wineexec)]
        if "Proton" not in self.get_version():
            menu_entries.append(("winecfg", "Wine configuration", self.run_winecfg))
        menu_entries += [
            ("wineconsole", "Wine console", self.run_wineconsole),
            ("wine-regedit", "Wine registry", self.run_regedit),
            ("winekill", "Kill all wine processes", self.run_winekill),
            ("winetricks", "Winetricks", self.run_winetricks),
            ("winecpl", "Wine Control Panel", self.run_winecpl),
        ]
        return menu_entries

    @property
    def prefix_path(self):
        """Return the absolute path of the Wine prefix"""
        _prefix_path = self.game_config.get("prefix")
        if not _prefix_path:
            logger.warning(
                "Wine prefix not provided, defaulting to $WINEPREFIX then ~/.wine."
                " This is probably not the intended behavior."
            )
            _prefix_path = os.environ.get("WINEPREFIX") or "~/.wine"
        return os.path.expanduser(_prefix_path)

    @property
    def game_exe(self):
        """Return the game's executable's path."""
        exe = self.game_config.get("exe")
        if not exe:
            logger.warning("The game doesn't have an executable")
            return
        if exe and os.path.isabs(exe):
            return exe
        if not self.game_path:
            return
        exe = os.path.join(self.game_path, exe)
        if system.path_exists(exe):
            return exe

    @property
    def working_dir(self):
        """Return the working directory to use when running the game."""
        option = self.game_config.get("working_dir")
        if option:
            return option
        if self.game_exe:
            return os.path.dirname(self.game_exe)
        return super(wine, self).working_dir

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
        if version in WINE_PATHS.keys():
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
        dlg = FileDialog("Select an EXE or MSI file", default_path=self.game_path)
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

    def run_winetricks(self, *args):
        """Run winetricks in the current context"""
        self.prelaunch()
        winetricks(
            "",
            prefix=self.prefix_path,
            wine_path=self.get_executable(),
            config=self,
            env=self.get_env(os_env=True)
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
            "UseXVidMode": prefix_manager.use_xvid_mode,
            "Desktop": prefix_manager.set_virtual_desktop,
            "WineDesktop": prefix_manager.set_desktop_size,
        }

        for key, path in self.reg_keys.items():
            value = self.runner_config.get(key) or "auto"
            if not value or value == "auto" and key not in managed_keys.keys():
                prefix_manager.clear_registry_subkeys(path, key)
            elif key in self.runner_config:
                if key in managed_keys.keys():
                    # Do not pass fallback 'auto' value to managed keys
                    if value == "auto":
                        value = None
                    managed_keys[key](value)
                    continue
                # Convert numeric strings to integers so they are saved as dword
                if value.isdigit():
                    value = int(value)

                prefix_manager.set_registry_key(path, key, value)

    def toggle_dxvk(self, enable, version=None, dxvk_manager: dxvk.DXVKManager = None):
        # manual version only sets the dlls to native
        if version.lower() != "manual":
            if enable:
                if not dxvk_manager.is_available():
                    logger.info("DXVK %s is not available yet, downloading...")
                    dxvk_manager.download()
                dxvk_manager.enable()
            else:
                dxvk_manager.disable()

        if enable:
            for dll in dxvk_manager.dxvk_dlls:
                # We have to make sure that the dll exists before setting it to native
                if dxvk_manager.dxvk_dll_exists(dll):
                    self.dll_overrides[dll] = "n"

    def setup_dxvk(self, base_name, dxvk_manager: dxvk.DXVKManager = None):
        if not dxvk_manager:
            return
        try:
            self.toggle_dxvk(
                bool(self.runner_config.get(base_name)),
                version=dxvk_manager.version,
                dxvk_manager=dxvk_manager,
            )
        except dxvk.UnavailableDXVKVersion:
            raise GameConfigError(
                "Unable to get " + base_name.upper() + " %s" % dxvk_manager.version
            )

    def prelaunch(self):
        if not system.path_exists(os.path.join(self.prefix_path, "user.reg")):
            create_prefix(self.prefix_path, arch=self.wine_arch)
        prefix_manager = WinePrefixManager(self.prefix_path)
        if self.runner_config.get("autoconf_joypad", True):
            prefix_manager.configure_joypads()
        self.sandbox(prefix_manager)
        self.set_regedit_keys()
        self.setup_x360ce(self.runner_config.get("x360ce-path"))
        if self.runner_config.get("vkd3d"):
            dxvk_manager = dxvk.VKD3DManager
        else:
            dxvk_manager = dxvk.DXVKManager
        self.setup_dxvk(
            "dxvk",
            dxvk_manager=dxvk_manager(
                self.prefix_path,
                arch=self.wine_arch,
                version=self.runner_config.get("dxvk_version"),
            ),
        )

        try:
            self.setup_nine(self.runner_config.get("gallium_nine"))
        except nine.NineUnavailable as ex:
            raise GameConfigError("Unable to configure GalliumNine: %s" % ex)
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

        overrides = overrides.copy()
        overrides.update(self.dll_overrides)
        return overrides

    def get_env(self, os_env=True):
        """Return environment variables used by the game"""
        # Always false to runner.get_env, the default value
        # of os_env is inverted in the wine class,
        # the OS env is read later.
        env = super(wine, self).get_env(False)
        if os_env:
            env.update(os.environ.copy())
        show_debug = self.runner_config.get("show_debug", "-all")
        if show_debug != "inherit":
            env["WINEDEBUG"] = show_debug
        env["WINEARCH"] = self.wine_arch
        env["WINE"] = self.get_executable()
        if self.prefix_path:
            env["WINEPREFIX"] = self.prefix_path

        if not ("WINEESYNC" in env and env["WINEESYNC"] == "1"):
            env["WINEESYNC"] = "1" if self.runner_config.get("esync") else "0"

        overrides = self.get_dll_overrides()
        if overrides:
            env["WINEDLLOVERRIDES"] = get_overrides_env(overrides)
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
        if "-4." in wine_path or "/4." in wine_path:
            version = "Ubuntu-18.04"
        else:
            version = "legacy"
        return runtime.get_env(
            version=version,
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
        pids = pids | system.get_pids_using_file(
            os.path.join(os.path.dirname(exe), "wineserver")
        )
        return pids

    def setup_x360ce(self, x360ce_path):
        if not x360ce_path:
            return
        x360ce_path = os.path.expanduser(x360ce_path)
        if not os.path.isdir(x360ce_path):
            logger.error("%s is not a valid path for x360ce", x360ce_path)
            return
        mode = "dumbxinputemu" if self.runner_config.get("dumbxinputemu") else "x360ce"
        dll_files = ["xinput1_3.dll"]
        if self.runner_config.get("x360ce-xinput9"):
            dll_files.append("xinput9_1_0.dll")

        for dll_file in dll_files:
            xinput_dest_path = os.path.join(x360ce_path, dll_file)
            xinput_arch = self.runner_config.get("xinput-arch") or self.wine_arch
            dll_path = os.path.join(RUNTIME_DIR, mode, xinput_arch)
            if not system.path_exists(xinput_dest_path):
                source_file = dll_file if mode == "dumbxinputemu" else "xinput1_3.dll"
                shutil.copyfile(os.path.join(dll_path, source_file), xinput_dest_path)

        if mode == "x360ce":
            if self.runner_config.get("x360ce-dinput"):
                dinput8_path = os.path.join(dll_path, "dinput8.dll")
                dinput8_dest_path = os.path.join(x360ce_path, "dinput8.dll")
                shutil.copyfile(dinput8_path, dinput8_dest_path)

            x360ce_config = X360ce()
            x360ce_config.populate_controllers()
            x360ce_config.write(os.path.join(x360ce_path, "x360ce.ini"))

        # X360 DLL handling
        self.dll_overrides["xinput1_3"] = "native"
        if self.runner_config.get("x360ce-xinput9"):
            self.dll_overrides["xinput9_1_0"] = "native"
        if self.runner_config.get("x360ce-dinput"):
            self.dll_overrides["dinput8"] = "native"

    def setup_nine(self, enable):
        nine_manager = nine.NineManager(self.prefix_path, self.wine_arch,)

        if enable:
            nine_manager.enable()
        else:
            nine_manager.disable()

    def sandbox(self, wine_prefix):
        if self.runner_config.get("sandbox", True):
            wine_prefix.desktop_integration(
                desktop_dir=self.runner_config.get("sandbox_dir")
            )
        else:
            wine_prefix.desktop_integration(restore=True)

    def play(self):
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

        if not system.path_exists(game_exe):
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
