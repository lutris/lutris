"""Base module for runners"""
# Standard Library
import os

# Third Party Libraries
from gi.repository import Gtk

# Lutris Modules
from lutris import pga, runtime, settings
from lutris.command import MonitoredCommand
from lutris.config import LutrisConfig
from lutris.gui import dialogs
from lutris.runners import RunnerInstallationError
from lutris.util import system
from lutris.util.extract import ExtractFailure, extract_archive
from lutris.util.http import Request
from lutris.util.log import logger


class RunnerMeta(type):
    def __new__(mcs, name, bases, body):
        if name != 'Runner' and 'play' not in body:
            raise TypeError(f"The play method is not implemented in runner {name}!")
        return super().__new__(mcs, name, bases, body)


class Runner(metaclass=RunnerMeta):  # pylint: disable=too-many-public-methods

    """Generic runner (base class for other runners)."""

    multiple_versions = False
    platforms = []
    require_libs = []
    runnable_alone = False
    game_options = []
    runner_options = []
    system_options_override = []
    context_menu_entries = []
    depends_on = None
    runner_executable = None

    def __init__(self, config=None):
        """Initialize runner."""
        self.arch = system.LINUX_SYSTEM.arch
        self.config = config
        self.game_data = {}
        if config:
            self.game_data = pga.get_game_by_field(self.config.game_config_id, "configpath")

    def __lt__(self, other):
        return self.name < other.name

    @property
    def description(self):
        """Return the class' docstring as the description."""
        return self.__doc__

    @description.setter
    def description(self, value):
        """Leave the ability to override the docstring."""
        self.__doc__ = value

    @property
    def name(self):
        return self.__class__.__name__

    @property
    def default_config(self):
        return LutrisConfig(runner_slug=self.name)

    @property
    def game_config(self):
        """Return the cascaded game config as a dict."""
        return self.config.game_config if self.config else {}

    @property
    def runner_config(self):
        """Return the cascaded runner config as a dict."""
        if self.config:
            return self.config.runner_config
        return self.default_config.runner_config

    @property
    def system_config(self):
        """Return the cascaded system config as a dict."""
        if self.config:
            return self.config.system_config
        return self.default_config.system_config

    @property
    def default_path(self):
        """Return the default path where games are installed."""
        return self.system_config.get("game_path")

    @property
    def browse_dir(self):
        """Return the path to open with the Browse Files action."""
        for key in self.game_config:
            if key in ["exe", "main_file", "rom", "disk", "iso"]:
                path = os.path.dirname(self.game_config.get(key) or "")
                if not os.path.isabs(path):
                    path = os.path.join(self.game_path, path)
                return path
        return self.game_path

    @property
    def game_path(self):
        """Return the directory where the game is installed."""
        return self.game_data.get("directory")

    @property
    def working_dir(self):
        """Return the working directory to use when running the game."""
        return self.game_path or os.path.expanduser("~/")

    @property
    def discord_rpc_enabled(self):
        if self.game_data.get("discord_rpc_enabled"):
            return self.game_data.get("discord_rpc_enabled")

    @property
    def discord_show_runner(self):
        if self.game_data.get("discord_show_runner"):
            return self.game_data.get("discord_show_runner")

    @property
    def discord_custom_game_name(self):
        if self.game_data.get("discord_custom_game_name"):
            return self.game_data.get("discord_custom_game_name")

    @property
    def discord_custom_runner_name(self):
        if self.game_data.get("discord_custom_runner_name"):
            return self.game_data.get("discord_custom_runner_name")

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
                    "label": "Custom executable for the runner",
                    "advanced": True,
                }
            )
        return runner_options

    def get_executable(self):
        if "runner_executable" in self.runner_config:
            runner_executable = self.runner_config["runner_executable"]
            if os.path.isfile(runner_executable):
                return runner_executable
        if not self.runner_executable:
            raise ValueError("runner_executable not set for {}".format(self.name))
        return os.path.join(settings.RUNNER_DIR, self.runner_executable)

    def get_env(self, os_env=False):
        """Return environment variables used for a game."""
        env = {}
        if os_env:
            env.update(os.environ.copy())

        system_env = self.system_config.get("env") or {}
        env.update(system_env)

        if self.system_config.get("dri_prime"):
            env["DRI_PRIME"] = "1"

        runtime_ld_library_path = None

        if self.use_runtime():
            runtime_env = self.get_runtime_env()
            if "STEAM_RUNTIME" in runtime_env and "STEAM_RUNTIME" not in env:
                env["STEAM_RUNTIME"] = runtime_env["STEAM_RUNTIME"]
            if "LD_LIBRARY_PATH" in runtime_env:
                runtime_ld_library_path = runtime_env["LD_LIBRARY_PATH"]

        if runtime_ld_library_path:
            ld_library_path = env.get("LD_LIBRARY_PATH")
            if not ld_library_path:
                ld_library_path = "$LD_LIBRARY_PATH"
            env["LD_LIBRARY_PATH"] = ":".join([runtime_ld_library_path, ld_library_path])

        return env

    def get_runtime_env(self):
        """Return runtime environment variables.

        This method may be overridden in runner classes.
        (Notably for Lutris wine builds)

        Returns:
            dict

        """
        return runtime.get_env(prefer_system_libs=self.system_config.get("prefer_system_libs", True))

    def prelaunch(self):
        """Run actions before running the game, override this method in runners"""
        return True

    def get_run_data(self):
        """Return dict with command (exe & args list) and env vars (dict).

        Reimplement in derived runner if need be."""
        return {"command": [self.get_executable()], "env": self.get_env()}

    def run(self, *args):
        """Run the runner alone."""
        if not self.runnable_alone:
            return
        if not self.is_installed():
            if not self.install_dialog():
                logger.info("Runner install cancelled")
                return

        command_data = self.get_run_data()
        command = command_data.get("command")
        env = (command_data.get("env") or {}).copy()

        if hasattr(self, "prelaunch"):
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

    def install_dialog(self):
        """Ask the user if she wants to install the runner.

        Return success of runner installation.
        """
        dialog = dialogs.QuestionDialog(
            {
                "question": ("The required runner is not installed.\n"
                             "Do you wish to install it now?"),
                "title": "Required runner unavailable",
            }
        )
        if Gtk.ResponseType.YES == dialog.result:

            from lutris.gui.dialogs.runners import simple_downloader
            from lutris.gui.dialogs import ErrorDialog
            try:
                if hasattr(self, "get_version"):
                    self.install(downloader=simple_downloader, version=self.get_version(use_default=False))
                else:
                    self.install(downloader=simple_downloader)
            except RunnerInstallationError as ex:
                ErrorDialog(ex.message)

            return self.is_installed()
        return False

    def is_installed(self):
        """Return whether the runner is installed"""
        return system.path_exists(self.get_executable())

    def get_runner_version(self, version=None):
        """Get the appropriate version for a runner

        Params:
            version (str): Optional version to lookup, will return this one if found

        Returns:
            dict: Dict containing version, architecture and url for the runner
        """
        logger.info(
            "Getting runner information for %s%s",
            self.name,
            " (version: %s)" % version if version else "",
        )
        request = Request("{}/api/runners/{}".format(settings.SITE_URL, self.name))
        runner_info = request.get().json
        if not runner_info:
            logger.error("Failed to get runner information")
            return

        versions = runner_info.get("versions") or []
        arch = self.arch
        if version:
            if version.endswith("-i386") or version.endswith("-x86_64"):
                version, arch = version.rsplit("-", 1)
            versions = [v for v in versions if v["version"] == version]
        versions_for_arch = [v for v in versions if v["architecture"] == arch]
        if len(versions_for_arch) == 1:
            return versions_for_arch[0]

        if len(versions_for_arch) > 1:
            default_version = [v for v in versions_for_arch if v["default"] is True]
            if default_version:
                return default_version[0]
        elif len(versions) == 1 and system.LINUX_SYSTEM.is_64_bit:
            return versions[0]
        elif len(versions) > 1 and system.LINUX_SYSTEM.is_64_bit:
            default_version = [v for v in versions if v["default"] is True]
            if default_version:
                return default_version[0]
        # If we didn't find a proper version yet, return the first available.
        if len(versions_for_arch) >= 1:
            return versions_for_arch[0]

    def install(self, version=None, downloader=None, callback=None):
        """Install runner using package management systems."""
        logger.debug(
            "Installing %s (version=%s, downloader=%s, callback=%s)",
            self.name,
            version,
            downloader,
            callback,
        )
        runner = self.get_runner_version(version)
        if not runner:
            raise RunnerInstallationError("Failed to retrieve {} ({}) information".format(self.name, version))
        if not downloader:
            raise RuntimeError("Missing mandatory downloader for runner %s" % self)
        opts = {"downloader": downloader, "callback": callback}
        if "wine" in self.name:
            opts["merge_single"] = True
            opts["dest"] = os.path.join(
                settings.RUNNER_DIR, self.name, "{}-{}".format(runner["version"], runner["architecture"])
            )

        if self.name == "libretro" and version:
            opts["merge_single"] = False
            opts["dest"] = os.path.join(settings.RUNNER_DIR, "retroarch/cores")
        self.download_and_extract(runner["url"], **opts)

    def download_and_extract(self, url, dest=None, **opts):
        downloader = opts["downloader"]
        merge_single = opts.get("merge_single", False)
        callback = opts.get("callback")
        tarball_filename = os.path.basename(url)
        runner_archive = os.path.join(settings.CACHE_DIR, tarball_filename)
        if not dest:
            dest = settings.RUNNER_DIR
        downloader(
            url, runner_archive, self.extract, {
                "archive": runner_archive,
                "dest": dest,
                "merge_single": merge_single,
                "callback": callback,
            }
        )

    def extract(self, archive=None, dest=None, merge_single=None, callback=None):
        if not system.path_exists(archive):
            raise RunnerInstallationError("Failed to extract {}".format(archive))
        try:
            extract_archive(archive, dest, merge_single=merge_single)
        except ExtractFailure as ex:
            logger.error("Failed to extract the archive %s file may be corrupt", archive)
            raise RunnerInstallationError("Failed to extract {}: {}".format(archive, ex))
        os.remove(archive)

        if self.name == "wine":
            logger.debug("Clearing wine version cache")
            from lutris.util.wine.wine import get_wine_versions
            get_wine_versions.cache_clear()

        if callback:
            callback()

    @staticmethod
    def remove_game_data(game_path=None):
        system.remove_folder(game_path)

    def can_uninstall(self):
        runner_path = os.path.join(settings.RUNNER_DIR, self.name)
        return os.path.isdir(runner_path)

    def uninstall(self):
        runner_path = os.path.join(settings.RUNNER_DIR, self.name)
        if os.path.isdir(runner_path):
            system.remove_folder(runner_path)

    def find_option(self, options_group, option_name):
        """Retrieve an option dict if it exists in the group"""
        if options_group not in ['game_options', 'runner_options']:
            return None
        output = None
        for item in getattr(self, options_group):
            if item["option"] == option_name:
                output = item
                break
        return output
