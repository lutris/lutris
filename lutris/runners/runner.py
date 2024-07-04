"""Base module for runners"""

import os
import signal
from gettext import gettext as _
from typing import Any, Callable, Dict, Optional

from lutris import runtime, settings
from lutris.api import format_runner_version, get_default_runner_version_info
from lutris.config import LutrisConfig
from lutris.database.games import get_game_by_field
from lutris.exceptions import MisconfigurationError, MissingExecutableError, UnavailableLibrariesError
from lutris.monitored_command import MonitoredCommand
from lutris.runners import RunnerInstallationError
from lutris.util import flatpak, strings, system
from lutris.util.extract import ExtractError, extract_archive
from lutris.util.graphics.gpu import GPUS
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import logger


class Runner:  # pylint: disable=too-many-public-methods
    """Generic runner (base class for other runners)."""

    multiple_versions = False
    platforms = []
    runnable_alone = False
    game_options = []
    runner_options = []
    system_options_override = []
    context_menu_entries = []
    require_libs = []
    runner_executable = None
    entry_point_option = "main_file"
    download_url = None
    arch = None  # If the runner is only available for an architecture that isn't x86_64
    flatpak_id = None

    def __init__(self, config=None):
        """Initialize runner."""
        if config:
            self.has_explicit_config = True
            self._config = config
            self.game_data = get_game_by_field(config.game_config_id, "configpath")
        else:
            self.has_explicit_config = False
            self._config = None
            self.game_data = {}

    def __lt__(self, other):
        return self.name < other.name

    @property
    def description(self):
        """Return the class' docstring as the description."""
        return self.__doc__

    @description.setter
    def description(self, value):
        """Leave the ability to override the docstring."""
        self.__doc__ = value  # What the shit

    @property
    def runner_warning(self):
        """Returns a message (as markup) that is displayed in the configuration dialog as
        a warning."""
        return None

    @property
    def name(self):
        return self.__class__.__name__

    @property
    def directory(self):
        return os.path.join(settings.RUNNER_DIR, self.name)

    @property
    def config(self):
        if not self._config:
            self._config = LutrisConfig(runner_slug=self.name)
        return self._config

    @config.setter
    def config(self, new_config):
        self._config = new_config
        self.has_explicit_config = new_config is not None

    @property
    def game_config(self):
        """Return the cascaded game config as a dict."""
        if not self.has_explicit_config:
            logger.warning("Accessing game config while runner wasn't given one.")

        return self.config.game_config

    @property
    def runner_config(self):
        """Return the cascaded runner config as a dict."""
        return self.config.runner_config

    @property
    def system_config(self):
        """Return the cascaded system config as a dict."""
        return self.config.system_config

    @property
    def default_path(self):
        """Return the default path where games are installed."""
        return self.system_config.get("game_path")

    @property
    def game_path(self):
        """Return the directory where the game is installed."""
        game_path = self.game_data.get("directory")
        if game_path:
            return os.path.expanduser(game_path)  # expanduser just in case!

        if self.has_explicit_config:
            # Default to the directory where the entry point is located.
            entry_point = self.game_config.get(self.entry_point_option)
            if entry_point:
                return os.path.dirname(os.path.expanduser(entry_point))
        return ""

    def resolve_game_path(self):
        """Returns the path where the game is found; if game_path does not
        provide a path, this may try to resolve the path by runner-specific means,
        which can find things like /usr/games when applicable."""
        return self.game_path

    @property
    def working_dir(self):
        """Return the working directory to use when running the game."""
        return self.game_path or os.path.expanduser("~/")

    @property
    def shader_cache_dir(self):
        """Return the cache directory for this runner to use. We create
        this if it does not exist."""
        path = os.path.join(settings.SHADER_CACHE_DIR, self.name)
        if not os.path.isdir(path):
            os.mkdir(path)
        return path

    @property
    def nvidia_shader_cache_path(self):
        """The path to place in __GL_SHADER_DISK_CACHE_PATH; NVidia
        will place its cache cache in a subdirectory here."""
        return self.shader_cache_dir

    @property
    def discord_client_id(self):
        if self.game_data.get("discord_client_id"):
            return self.game_data.get("discord_client_id")

    def get_platform(self):
        return self.platforms[0]

    def get_runner_options(self):
        runner_options = self.runner_options[:]
        if self.runner_executable:
            runner_options.append(
                {
                    "option": "runner_executable",
                    "type": "file",
                    "label": _("Custom executable for the runner"),
                    "advanced": True,
                }
            )

        runner_options.append(
            {
                "section": _("Side Panel"),
                "option": "visible_in_side_panel",
                "type": "bool",
                "label": _("Visible in Side Panel"),
                "default": True,
                "advanced": True,
                "scope": ["runner"],
                "help": _("Show this runner in the side panel if it is installed or available through Flatpak."),
            }
        )
        return runner_options

    def get_executable(self) -> str:
        if "runner_executable" in self.runner_config:
            runner_executable = self.runner_config["runner_executable"]
            if os.path.isfile(runner_executable):
                return runner_executable
        if not self.runner_executable:
            raise MisconfigurationError("runner_executable not set for {}".format(self.name))

        exe = os.path.join(settings.RUNNER_DIR, self.runner_executable)
        if not os.path.isfile(exe):
            raise MissingExecutableError(_("The executable '%s' could not be found.") % self.runner_executable)
        return exe

    def get_command(self):
        """Returns the command line to run the runner itself; generally a game
        will be appended to this by play()."""
        try:
            exe = self.get_executable()
            if not system.path_exists(exe):
                raise MissingExecutableError(_("The executable '%s' could not be found.") % exe)
            return [exe]
        except MisconfigurationError:
            if flatpak.is_app_installed(self.flatpak_id):
                return flatpak.get_run_command(self.flatpak_id)

            raise

    def get_env(self, os_env=False, disable_runtime=False):
        """Return environment variables used for a game."""
        env = {}
        if os_env:
            env = system.get_environment()

        # Steam compatibility
        if os.environ.get("SteamAppId"):
            logger.info("Game launched from steam (AppId: %s)", os.environ["SteamAppId"])
            env["LC_ALL"] = ""

        # Set correct LC_ALL depending on user settings
        locale = self.system_config.get("locale")
        if locale:
            env["LC_ALL"] = locale

        # By default, we'll set NVidia's shader disk cache to be
        # per-game, so it overflows less readily.
        env["__GL_SHADER_DISK_CACHE"] = "1"
        env["__GL_SHADER_DISK_CACHE_PATH"] = self.nvidia_shader_cache_path

        # Override SDL2 controller configuration
        sdl_gamecontrollerconfig = self.system_config.get("sdl_gamecontrollerconfig")
        if sdl_gamecontrollerconfig:
            path = os.path.expanduser(sdl_gamecontrollerconfig)
            if system.path_exists(path):
                with open(path, "r", encoding="utf-8") as controllerdb_file:
                    sdl_gamecontrollerconfig = controllerdb_file.read()
            env["SDL_GAMECONTROLLERCONFIG"] = sdl_gamecontrollerconfig

        # Set monitor to use for SDL 1 games
        sdl_video_fullscreen = self.system_config.get("sdl_video_fullscreen")
        if sdl_video_fullscreen and sdl_video_fullscreen != "off":
            env["SDL_VIDEO_FULLSCREEN_DISPLAY"] = sdl_video_fullscreen

        if self.system_config.get("gpu") and len(GPUS) > 1:
            gpu = GPUS[self.system_config["gpu"]]
            if gpu.driver == "nvidia":
                env["DRI_PRIME"] = "1"
                env["__NV_PRIME_RENDER_OFFLOAD"] = "1"
                env["__GLX_VENDOR_LIBRARY_NAME"] = "nvidia"
                env["__VK_LAYER_NV_optimus"] = "NVIDIA_only"
            else:
                env["DRI_PRIME"] = gpu.pci_id
            env["VK_ICD_FILENAMES"] = gpu.icd_files  # Deprecated
            env["VK_DRIVER_FILES"] = gpu.icd_files  # Current form

        # Set PulseAudio latency to 60ms
        if self.system_config.get("pulse_latency"):
            env["PULSE_LATENCY_MSEC"] = "60"

        runtime_ld_library_path = None

        if not disable_runtime and self.use_runtime():
            runtime_env = self.get_runtime_env()
            runtime_ld_library_path = runtime_env.get("LD_LIBRARY_PATH")

        if runtime_ld_library_path:
            ld_library_path = env.get("LD_LIBRARY_PATH")
            env["LD_LIBRARY_PATH"] = os.pathsep.join(filter(None, [runtime_ld_library_path, ld_library_path]))

        # Apply user overrides at the end
        env.update(self.system_config.get("env") or {})

        return env

    def finish_env(self, env: Dict[str, str], game) -> None:
        """This is called by the Game after setting up the environment to allow the runner
        to make final adjustments, which may be based on the environment so far."""
        pass

    def get_runtime_env(self):
        """Return runtime environment variables.

        This method may be overridden in runner classes.
        (Notably for Lutris wine builds)

        Returns:
            dict

        """
        return runtime.get_env(prefer_system_libs=self.system_config.get("prefer_system_libs", True))

    def apply_launch_config(self, gameplay_info, launch_config):
        """Updates the gameplay_info to reflect a launch_config section. Called only
        if a non-default config is chosen."""
        gameplay_info["command"] = self.get_launch_config_command(gameplay_info, launch_config)

        config_working_dir = self.get_launch_config_working_dir(launch_config)

        if config_working_dir:
            gameplay_info["working_dir"] = config_working_dir

    def get_launch_config_command(self, gameplay_info, launch_config):
        """Generates a new command for the gameplay_info, to implement the launch_config.
        Returns a new list of strings; the caller can modify it further.

        If launch_config has no command, this builds one from the gameplay_info command
        and the 'exe' value in the launch_config.

        Runners override this when required to control the command used."""

        if "command" in launch_config:
            command = strings.split_arguments(launch_config["command"])
        else:
            command = self.get_command()

        exe = self.get_launch_config_exe(launch_config)
        if exe:
            command.append(exe)

        if launch_config.get("args"):
            command += strings.split_arguments(launch_config["args"])

        return command

    def get_launch_config_exe(self, launch_config):
        """Locates the "exe" of the launch config. If it appears
        to be relative to the game's working_dir, this will try to
        adjust it to be relative to the config's instead.
        """
        exe = launch_config.get("exe")
        config_working_dir = self.get_launch_config_working_dir(launch_config)

        if exe:
            exe = os.path.expanduser(exe)  # just in case!

            if config_working_dir and not os.path.isabs(exe):
                exe_from_config = self.resolve_config_path(exe, config_working_dir)
                exe_from_game = self.resolve_config_path(exe)

                if os.path.exists(exe_from_game) and not os.path.exists(exe_from_config):
                    relative = os.path.relpath(exe_from_game, start=config_working_dir)
                    if not relative.startswith("../"):
                        return relative

        return exe

    def get_launch_config_working_dir(self, launch_config):
        """Extracts the "working_dir" from the config, and resolves this relative
        to the game's working directory, so that an absolute path results.

        This returns None if no working_dir is present, or if it found to be missing.
        """
        config_working_dir = launch_config.get("working_dir")
        if config_working_dir:
            config_working_dir = self.resolve_config_path(config_working_dir)
            if os.path.isdir(config_working_dir):
                return config_working_dir

        return None

    def resolve_config_path(self, path, relative_to=None):
        """Interpret a path taken from the launch_config relative to
        a working directory, using the game's working_dir if that is omitted,
        and expanding the '~' if we get one.

        This is provided as a method so the WINE runner can try to convert
        Windows-style paths to usable paths.
        """
        path = os.path.expanduser(path)

        if not os.path.isabs(path):
            if not relative_to:
                relative_to = self.working_dir

            if relative_to:
                return os.path.join(relative_to, path)

        return path

    def prelaunch(self):
        """Run actions before running the game, override this method in runners; raise an
        exception if prelaunch fails, and it will be reported to the user, and
        then the game won't start."""
        available_libs = set()
        for lib in set(self.require_libs):
            if lib in LINUX_SYSTEM.shared_libraries:
                if self.arch:
                    if self.arch in [_lib.arch for _lib in LINUX_SYSTEM.shared_libraries[lib]]:
                        available_libs.add(lib)
                else:
                    available_libs.add(lib)
        unavailable_libs = set(self.require_libs) - available_libs
        if unavailable_libs:
            raise UnavailableLibrariesError(unavailable_libs, self.arch)

    def get_run_data(self):
        """Return dict with command (exe & args list) and env vars (dict).

        Reimplement in derived runner if need be."""
        return {"command": self.get_command(), "env": self.get_env()}

    def run(self, ui_delegate):
        """Run the runner alone."""
        if not self.runnable_alone:
            return
        if not self.is_installed():
            if not self.install_dialog(ui_delegate):
                logger.info("Runner install cancelled")
                return

        command_data = self.get_run_data()
        command = command_data.get("command")
        env = (command_data.get("env") or {}).copy()

        self.prelaunch()

        command_runner = MonitoredCommand(command, runner=self, env=env)
        command_runner.start()

    def use_runtime(self):
        if runtime.RUNTIME_DISABLED:
            logger.info("Runtime disabled by environment")
            return False
        if self.system_config.get("disable_runtime"):
            logger.info("Runtime disabled by system configuration")
            return False
        return True

    def install_dialog(self, ui_delegate):
        """Ask the user if they want to install the runner.

        Return success of runner installation.
        """

        if ui_delegate.show_install_yesno_inquiry(
            question=_("The required runner is not installed.\n" "Do you wish to install it now?"),
            title=_("Required runner unavailable"),
        ):
            if hasattr(self, "get_version"):
                version = self.get_version(use_default=False)  # pylint: disable=no-member
                self.install(ui_delegate, version=version)
            else:
                self.install(ui_delegate)

            return self.is_installed()
        return False

    def is_installed(self, flatpak_allowed: bool = True) -> bool:
        """Return whether the runner is installed"""
        try:
            # Don't care where the exe is, only if we can find it.
            exe = self.get_executable()
            if system.path_exists(exe):
                return True
        except MisconfigurationError:
            pass  # We can still try flatpak even if 'which' fails us!

        return bool(flatpak_allowed and self.flatpak_id and flatpak.is_app_installed(self.flatpak_id))

    def is_installed_for(self, interpreter):
        """Returns whether the runner is installed. Specific runners can extract additional
        script settings, to determine more precisely what must be installed."""
        return self.is_installed()

    def get_installer_runner_version(self, installer, use_runner_config: bool = True) -> Optional[str]:
        return None

    def adjust_installer_runner_config(self, installer_runner_config: Dict[str, Any]) -> None:
        """This is called during installation to let to run fix up in the runner's section of
        the configuration before it is saved. This method should modify the dict given."""
        pass

    def get_runner_version(self, version: str = None) -> Optional[Dict[str, str]]:
        """Get the appropriate version for a runner, as with get_default_runner_version(),
        but this method allows the runner to apply its configuration."""
        return get_default_runner_version_info(self.name, version)

    def install(self, install_ui_delegate, version=None, callback=None):
        """Install runner using package management systems."""
        logger.debug(
            "Installing %s (version=%s, callback=%s)",
            self.name,
            version,
            callback,
        )
        opts = {"install_ui_delegate": install_ui_delegate, "callback": callback}
        if self.download_url:
            opts["dest"] = self.directory
            return self.download_and_extract(self.download_url, **opts)
        runner_version_info = self.get_runner_version(version)
        if not runner_version_info:
            raise RunnerInstallationError(_("Failed to retrieve {} ({}) information").format(self.name, version))

        if "wine" in self.name:
            opts["merge_single"] = True
            opts["dest"] = os.path.join(self.directory, format_runner_version(runner_version_info))

        if self.name == "libretro" and version:
            opts["merge_single"] = False
            opts["dest"] = os.path.join(settings.RUNNER_DIR, "retroarch/cores")
        self.download_and_extract(runner_version_info["url"], **opts)

    def download_and_extract(self, url, dest=None, **opts):
        install_ui_delegate = opts["install_ui_delegate"]
        merge_single = opts.get("merge_single", False)
        callback = opts.get("callback")
        tarball_filename = os.path.basename(url)
        runner_archive = os.path.join(settings.CACHE_DIR, tarball_filename)
        if not dest:
            dest = settings.RUNNER_DIR

        install_ui_delegate.download_install_file(url, runner_archive)
        self.extract(archive=runner_archive, dest=dest, merge_single=merge_single, callback=callback)

    def extract(self, archive=None, dest=None, merge_single=None, callback=None):
        if not system.path_exists(archive, exclude_empty=True):
            raise RunnerInstallationError(_("Failed to extract {}").format(archive))
        try:
            extract_archive(archive, dest, merge_single=merge_single)
        except ExtractError as ex:
            logger.error("Failed to extract the archive %s file may be corrupt", archive)
            raise RunnerInstallationError(_("Failed to extract {}: {}").format(archive, ex)) from ex
        os.remove(archive)

        if self.name == "wine":
            logger.debug("Clearing wine version cache")
            from lutris.util.wine.wine import get_installed_wine_versions

            get_installed_wine_versions.cache_clear()

        if self.runner_executable:
            runner_executable = os.path.join(settings.RUNNER_DIR, self.runner_executable)
            if os.path.isfile(runner_executable):
                system.make_executable(runner_executable)

        if callback:
            callback()

    def remove_game_data(self, app_id=None, game_path=None):
        system.remove_folder(game_path)

    def can_uninstall(self):
        return os.path.isdir(self.directory)

    def uninstall(self, uninstall_callback: Callable[[], None]) -> None:
        runner_path = self.directory
        if os.path.isdir(runner_path):
            system.remove_folder(runner_path, completion_function=uninstall_callback)
        else:
            uninstall_callback()

    def find_option(self, options_group, option_name):
        """Retrieve an option dict if it exists in the group"""
        if options_group not in ["game_options", "runner_options"]:
            return None
        output = None
        for item in getattr(self, options_group):
            if item["option"] == option_name:
                output = item
                break
        return output

    def force_stop_game(self, game):
        """Stop the running game. If this leaves any game processes running,
        the caller will SIGKILL them (after a delay)."""
        game.kill_processes(signal.SIGTERM)

    def extract_icon(self, game_slug):
        """The config UI calls this to extract the game icon. Most runners do not
        support this and do nothing. This is not called if a custom icon is installed
        for the game."""
