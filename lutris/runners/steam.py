"""Steam for Linux runner"""

import os
from gettext import gettext as _

from lutris.exceptions import MissingGameExecutableError, UnavailableRunnerError
from lutris.monitored_command import MonitoredCommand
from lutris.runners import NonInstallableRunnerError
from lutris.runners.runner import Runner
from lutris.util import linux, system
from lutris.util.log import logger
from lutris.util.steam.appmanifest import get_appmanifest_from_appid, get_path_from_appmanifest
from lutris.util.steam.config import get_default_acf, get_steam_dir, get_steamapps_dirs
from lutris.util.steam.vdfutils import to_vdf
from lutris.util.strings import split_arguments


def get_steam_pid():
    """Return pid of Steam process."""
    return system.get_pid("steam$")


def is_running():
    """Checks if Steam is running."""
    return bool(get_steam_pid())


class steam(Runner):
    description = _("Runs Steam for Linux games")
    human_name = _("Steam")
    platforms = [_("Linux")]
    runner_executable = "steam"
    flatpak_id = "com.valvesoftware.Steam"
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
                "Command line arguments used when launching the game.\nIgnored when Steam Big Picture mode is enabled."
            ),
        },
        {
            "option": "run_without_steam",
            "label": _("DRM free mode (Do not launch Steam)"),
            "type": "bool",
            "default": False,
            "advanced": True,
            "help": _("Run the game directly without Steam, requires the game binary path to be set"),
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
            "option": "args",
            "type": "string",
            "label": _("Arguments"),
            "advanced": True,
            "help": _("Extra command line arguments used when launching Steam"),
        },
    ]
    system_options_override = [
        {"option": "disable_runtime", "default": True},
        {"option": "gamemode", "default": False},
    ]

    @property
    def runnable_alone(self):
        return not linux.LINUX_SYSTEM.is_flatpak()

    @property
    def appid(self):
        return self.game_config.get("appid") or ""

    @property
    def game_path(self):
        if not self.appid:
            return None
        return self.get_game_path_from_appid(self.appid)

    @property
    def steam_data_dir(self):
        """Main installation directory for Steam"""
        return get_steam_dir()

    def get_appmanifest(self):
        """Return an AppManifest instance for the game"""
        appmanifests = []
        for apps_path in get_steamapps_dirs():
            appmanifest = get_appmanifest_from_appid(apps_path, self.appid)
            if appmanifest:
                appmanifests.append(appmanifest)
        if len(appmanifests) > 1:
            logger.warning("More than one AppManifest for %s returning only 1st", self.appid)
        if appmanifests:
            return appmanifests[0]

    def get_executable(self) -> str:
        if linux.LINUX_SYSTEM.is_flatpak():
            # Fallback to xgd-open for Steam URIs in Flatpak
            return system.find_required_executable("xdg-open")
        runner_executable = self.runner_config.get("runner_executable")
        if runner_executable and os.path.isfile(runner_executable):
            return runner_executable
        return system.find_required_executable(self.runner_executable)

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
        command = self.get_command()
        if self.runner_config.get("start_in_big_picture"):
            command.append("-bigpicture")
        return command + split_arguments(self.runner_config.get("args") or "")

    def get_game_path_from_appid(self, appid):
        """Return the game directory."""
        for apps_path in get_steamapps_dirs():
            game_path = get_path_from_appmanifest(apps_path, appid)
            if game_path:
                return game_path
        logger.info("Data path for SteamApp %s not found.", appid)
        return ""

    def get_default_steamapps_path(self):
        steamapps_paths = get_steamapps_dirs()
        if steamapps_paths:
            return steamapps_paths[0]
        return ""

    def install(self, install_ui_delegate, version=None, callback=None):
        raise NonInstallableRunnerError(
            message=_("Steam for Linux installation is not handled by Lutris."),
            message_markup=_(
                "Steam for Linux installation is not handled by Lutris.\n"
                "Please go to "
                "<a href='http://steampowered.com'>http://steampowered.com</a>"
                " or install Steam with the package provided by your distribution."
            ),
        )

    def install_game(self, appid, generate_acf=False):
        logger.debug("Installing steam game %s", appid)
        if generate_acf:
            acf_data = get_default_acf(appid, appid)
            acf_content = to_vdf(acf_data)
            steamapps_path = self.get_default_steamapps_path()
            if not steamapps_path:
                raise UnavailableRunnerError(_("Could not find Steam path, is Steam installed?"))
            acf_path = os.path.join(steamapps_path, "appmanifest_%s.acf" % appid)
            with open(acf_path, "w", encoding="utf-8") as acf_file:
                acf_file.write(acf_content)
        system.spawn(self.get_command() + [f"steam://install/{appid}"])

    def get_run_data(self):
        return {"command": self.launch_args, "env": self.get_env()}

    def play(self):
        game_args = self.game_config.get("args") or ""

        binary_path = self.game_config.get("steamless_binary")
        if self.game_config.get("run_without_steam") and binary_path:
            # Start without steam
            if not system.path_exists(binary_path):
                raise MissingGameExecutableError(filename=binary_path)
            command = [binary_path]
        else:
            # Start through steam
            if linux.LINUX_SYSTEM.is_flatpak():
                if game_args:
                    steam_uri = "steam://run/%s//%s/" % (self.appid, game_args)
                else:
                    steam_uri = "steam://rungameid/%s" % self.appid
                return {
                    "command": self.launch_args + [steam_uri],
                    "env": self.get_env(),
                }
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

    def remove_game_data(self, app_id=None, **kwargs):
        if not self.is_installed():
            return False
        app_id = app_id or self.appid
        command = MonitoredCommand(
            self.get_command() + [f"steam://uninstall/{app_id}"],
            runner=self,
            env=self.get_env(),
        )
        command.start()
