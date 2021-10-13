"""Steam for Linux runner"""
import os
import subprocess
import time
from gettext import gettext as _

from lutris.command import MonitoredCommand
from lutris.runners import NonInstallableRunnerError
from lutris.runners.runner import Runner
from lutris.util import linux, system
from lutris.util.log import logger
from lutris.util.steam.appmanifest import get_appmanifest_from_appid, get_path_from_appmanifest
from lutris.util.steam.config import STEAM_DATA_DIRS, get_default_acf, get_steam_dir, read_config, read_library_folders
from lutris.util.steam.vdf import to_vdf
from lutris.util.strings import split_arguments


def shutdown():
    """Cleanly quit Steam."""
    logger.debug("Shutting down Steam")
    if is_running():
        subprocess.call(["steam", "-shutdown"])


def get_steam_pid():
    """Return pid of Steam process."""
    return system.get_pid("steam$")


def kill():
    """Force quit Steam."""
    system.kill_pid(get_steam_pid())


def is_running():
    """Checks if Steam is running."""
    return bool(get_steam_pid())


class steam(Runner):
    description = _("Runs Steam for Linux games")
    human_name = _("Steam")
    platforms = [_("Linux")]
    runner_executable = "steam"
    game_options = [
        {
            "option": "appid",
            "label": _("Application ID"),
            "type": "string",
            "help": _(
                "The application ID can be retrieved from the game's "
                "page at steampowered.com. Example: 235320 is the "
                "app ID for <i>Original War</i> in: \n"
                "http://store.steampowered.com/app/<b>235320</b>/"
            ),
        },
        {
            "option": "args",
            "type": "string",
            "label": _("Arguments"),
            "help": _(
                "Command line arguments used when launching the game.\n"
                "Ignored when Steam Big Picture mode is enabled."
            ),
        },
        {
            "option": "run_without_steam",
            "label": _("DRM free mode (Do not launch Steam)"),
            "type": "bool",
            "default": False,
            "advanced": True,
            "help": _(
                "Run the game directly without Steam, requires the game binary path to be set"
            ),
        },
        {
            "option": "steamless_binary",
            "type": "file",
            "label": _("Game binary path"),
            "advanced": True,
            "help": _("Path to the game executable (Required by DRM free mode)"),
        },
    ]
    runner_options = [
        {
            "option": "quit_steam_on_exit",
            "label": _("Stop Steam after game exits"),
            "type": "bool",
            "default": False,
            "help": _(
                "Shut down Steam after the game has quit\n"
                "(only if Steam was started by Lutris)"
            ),
        },
        {
            "option": "start_in_big_picture",
            "label": _("Start Steam in Big Picture mode"),
            "type": "bool",
            "default": False,
            "help": _(
                "Launches Steam in Big Picture mode.\n"
                "Only works if Steam is not running or "
                "already running in Big Picture mode.\n"
                "Useful when playing with a Steam Controller."
            ),
        },
        {
            "option": "lsi_steam",
            "label": _("Start Steam with LSI"),
            "type": "bool",
            "default": False,
            "help": _(
                "Launches steam with LSI patches enabled. "
                "Make sure Lutris Runtime is disabled and "
                "you have LSI installed. "
                "https://github.com/solus-project/linux-steam-integration"
            ),
        },
        {
            "option": "args",
            "type": "string",
            "label": _("Arguments"),
            "advanced": True,
            "help": _("Extra command line arguments used when launching Steam"),
        },
    ]
    system_options_override = [{"option": "disable_runtime", "default": True}]

    def __init__(self, config=None):
        super(steam, self).__init__(config)
        self.own_game_remove_method = _("Remove game data (through Steam)")
        self.no_game_remove_warning = True
        self.original_steampid = None

    @property
    def runnable_alone(self):
        return not linux.LINUX_SYSTEM.is_flatpak

    @property
    def appid(self):
        return self.game_config.get("appid") or ""

    def get_steam_config(self):
        """Return the "Steam" part of Steam's config.vdf as a dict."""
        return read_config(self.steam_data_dir)

    def get_library_config(self):
        """Return the "libraryfolders" part of Steam's libraryfolders.vdf as a dict """
        return read_library_folders(self.steam_data_dir)

    @property
    def game_path(self):
        if not self.appid:
            return None
        return self.get_game_path_from_appid(self.appid)

    @property
    def steam_data_dir(self):
        """Main installation directory for Steam"""
        return get_steam_dir()

    @property
    def library_folders(self):
        """Return a list Steam library paths"""
        return self.get_steamapps_dirs()

    def get_appmanifest(self):
        """Return an AppManifest instance for the game"""
        appmanifests = []
        for apps_path in self.get_steamapps_dirs():
            appmanifest = get_appmanifest_from_appid(apps_path, self.appid)
            if appmanifest:
                appmanifests.append(appmanifest)
        if len(appmanifests) > 1:
            logger.warning("More than one AppManifest for %s returning only 1st", self.appid)
        if appmanifests:
            return appmanifests[0]

    def get_executable(self):
        if linux.LINUX_SYSTEM.is_flatpak:
            # Use xdg-open for Steam URIs in Flatpak
            return system.find_executable("xdg-open")
        if self.runner_config.get("lsi_steam") and system.find_executable("lsi-steam"):
            return system.find_executable("lsi-steam")
        runner_executable = self.runner_config.get("runner_executable")
        if runner_executable and os.path.isfile(runner_executable):
            return runner_executable
        return system.find_executable(self.runner_executable)

    @property
    def working_dir(self):
        """Return the working directory to use when running the game."""
        if self.game_config.get("run_without_steam"):
            steamless_binary = self.game_config.get("steamless_binary")
            if steamless_binary and os.path.isfile(steamless_binary):
                return os.path.dirname(steamless_binary)
        return super().working_dir

    @property
    def launch_args(self):
        """Provide launch arguments for Steam"""
        args = [self.get_executable()]
        if linux.LINUX_SYSTEM.is_flatpak:
            return args
        if self.runner_config.get("start_in_big_picture"):
            args.append("-bigpicture")
        return args + split_arguments(self.runner_config.get("args") or "")

    def get_game_path_from_appid(self, appid):
        """Return the game directory."""
        for apps_path in self.get_steamapps_dirs():
            game_path = get_path_from_appmanifest(apps_path, appid)
            if game_path:
                return game_path
        logger.info("Data path for SteamApp %s not found.", appid)

    def get_steamapps_dirs(self):
        """Return a list of the Steam library main + custom folders."""
        dirs = []
        # Extra colon-separated compatibility tools dirs environment variable
        if 'STEAM_EXTRA_COMPAT_TOOLS_PATHS' in os.environ:
            dirs += os.getenv('STEAM_EXTRA_COMPAT_TOOLS_PATHS').split(':')
        # Main steamapps dir and compatibilitytools.d dir
        for data_dir in STEAM_DATA_DIRS:
            for _dir in ["steamapps", "compatibilitytools.d"]:
                abs_dir = os.path.join(os.path.expanduser(data_dir), _dir)
                abs_dir = system.fix_path_case(abs_dir)
                if abs_dir and os.path.isdir(abs_dir):
                    dirs.append(abs_dir)

        # Custom dirs
        steam_config = self.get_steam_config()
        if steam_config:
            i = 1
            while "BaseInstallFolder_%s" % i in steam_config:
                path = steam_config["BaseInstallFolder_%s" % i] + "/steamapps"
                path = system.fix_path_case(path)
                if path and os.path.isdir(path):
                    dirs.append(path)
                i += 1

        # New Custom dirs
        if library_config = self.get_library_config()
        if library_config:
            paths = []
            for entry in library_config.values():
                if "mounted" in entry:
                    if entry.get("path") and entry.get("mounted") == "1":
                        path = system.fix_path_case(entry.get("path") + "/steamapps")
                        paths.append(path)
                else:
                    path = system.fix_path_case(entry.get("path") + "/steamapps")
                    paths.append(path)
            for path in paths:
                if path and os.path.isdir(path):
                    dirs.append(path)
        return system.list_unique_folders(dirs)

    def get_default_steamapps_path(self):
        steamapps_paths = self.get_steamapps_dirs()
        if steamapps_paths:
            return steamapps_paths[0]

    def install(self, version=None, downloader=None, callback=None):
        raise NonInstallableRunnerError(
            "Steam for Linux installation is not handled by Lutris.\n"
            "Please go to "
            "<a href='http://steampowered.com'>http://steampowered.com</a>"
            " or install Steam with the package provided by your distribution."
        )

    def install_game(self, appid, generate_acf=False):
        logger.debug("Installing steam game %s", appid)
        if generate_acf:
            acf_data = get_default_acf(appid, appid)
            acf_content = to_vdf(acf_data)
            steamapps_path = self.get_default_steamapps_path()
            if not steamapps_path:
                raise RuntimeError("Could not find Steam path, is Steam installed?")
            acf_path = os.path.join(steamapps_path, "appmanifest_%s.acf" % appid)
            with open(acf_path, "w") as acf_file:
                acf_file.write(acf_content)
            if is_running():
                shutdown()
                time.sleep(5)
        command = [self.get_executable(), "steam://install/%s" % appid]
        subprocess.Popen(command)

    def prelaunch(self):
        def has_steam_shutdown(times=10):
            for __ in range(times):
                time.sleep(1)
                if not is_running():
                    return True

        # If using primusrun, shutdown existing Steam first
        if self.system_config.get("optimus") != "off" and is_running():
            shutdown()
            if not has_steam_shutdown():
                logger.info("Forcing Steam shutdown")
                kill()
                if not has_steam_shutdown(5):
                    logger.error("Failed to shut down Steam :(")
                    return False
        return True

    def get_run_data(self):
        return {"command": self.launch_args, "env": self.get_env()}

    def play(self):
        game_args = self.game_config.get("args") or ""

        binary_path = self.game_config.get("steamless_binary")
        if self.game_config.get("run_without_steam") and binary_path:
            # Start without steam
            if not system.path_exists(binary_path):
                return {"error": "FILE_NOT_FOUND", "file": binary_path}
            self.original_steampid = None
            command = [binary_path]
        else:
            # Start through steam
            if linux.LINUX_SYSTEM.is_flatpak:
                if game_args:
                    steam_uri = "steam://run/%s//%s/" % (self.appid, game_args)
                else:
                    steam_uri = "steam://rungameid/%s" % self.appid
                return {
                    "command": self.launch_args + [steam_uri],
                    "env": self.get_env(),
                }

            # Get current steam pid to act as the root pid instead of lutris
            self.original_steampid = get_steam_pid()
            command = self.launch_args

            if self.runner_config.get("start_in_big_picture") or not game_args:
                command.append("steam://rungameid/%s" % self.appid)
            else:
                command.append("-applaunch")
                command.append(self.appid)

        if game_args:
            for arg in split_arguments(game_args):
                command.append(arg)

        return {
            "command": command,
            "env": self.get_env(),
        }

    def stop(self):
        if self.runner_config.get("quit_steam_on_exit") and not self.original_steampid:
            shutdown()
            return True
        return False

    def remove_game_data(self, appid=None, **kwargs):
        if not self.is_installed():
            return False
        command = MonitoredCommand(
            [self.get_executable(), "steam://uninstall/%s" % (appid or self.appid)],
            runner=self,
            env=self.get_env(),
        )
        command.start()
