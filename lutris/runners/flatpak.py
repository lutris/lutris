import os
from collections.abc import Callable
from gettext import gettext as _

from lutris.exceptions import GameConfigError, MissingExecutableError
from lutris.installer.errors import FlatpakSetupError
from lutris.runners.commands.flatpak import install_flatpak as install_flatpak
from lutris.runners.runner import Runner
from lutris.util import flatpak as _flatpak
from lutris.util import system
from lutris.util.flatpak_install import (
    FlatpakInstallError,
    FlatpakPrerequisiteError,
    uninstall_user,
)
from lutris.util.strings import split_arguments


class flatpak(Runner):
    """
    Runner for Flatpak applications.
    """

    description = _("Runs Flatpak applications")
    platform_dict = Runner.to_platform_dict([_("Linux")])
    entry_point_option = "appid"
    human_name = _("Flatpak")
    runnable_alone = False
    system_options_override = [{"option": "disable_runtime", "default": True}]

    game_options = [
        {
            "option": "appid",
            "type": "string",
            "label": _("Application ID"),
            "help": _("The application's unique three-part identifier (tld.domain.app)."),
        },
        {
            "option": "arch",
            "type": "string",
            "label": _("Architecture"),
            "help": _(
                "The architecture to run. See flatpak --supported-arches for architectures supported by the host."
            ),
            "advanced": True,
        },
        {
            "option": "branch",
            "type": "string",
            "label": _("Branch"),
            "help": _("The branch to use."),
            "advanced": True,
        },
        {
            "option": "install_type",
            "type": "string",
            "label": _("Install type"),
            "help": _("Can be system or user."),
            "advanced": True,
        },
        {
            "option": "args",
            "type": "string",
            "label": _("Args"),
            "help": _("Arguments to be passed to the application."),
        },
        {
            "option": "fcommand",
            "type": "string",
            "label": _("Command"),
            "help": _("The command to run instead of the one listed in the application metadata."),
            "advanced": True,
        },
        {
            "option": "working_dir",
            "type": "directory",
            "label": _("Working directory"),
            "warn_if_non_writable_parent": True,
            "help": _("The directory to run the command in. Note that this must be a directory inside the sandbox."),
            "advanced": True,
        },
        {
            "option": "env_vars",
            "type": "string",
            "label": _("Environment variables"),
            "help": _(
                "Set an environment variable in the application. "
                "This overrides to the Context section from the application metadata."
            ),
            "advanced": True,
        },
    ]

    def is_installed(self, flatpak_allowed: bool = True) -> bool:
        return _flatpak.is_installed()

    def get_executable(self) -> str:
        exe = _flatpak.get_executable()
        if not exe or not system.path_exists(exe):
            raise MissingExecutableError(_("The Flatpak executable could not be found."))
        return exe

    def install(self, install_ui_delegate, version=None, callback=None):
        # Flatpak is a host prerequisite, not a runner Lutris can download.
        raise FlatpakSetupError("access" if _flatpak.is_sandboxed() else "missing")

    def can_uninstall(self):
        return False

    def uninstall(self, uninstall_callback: Callable[[], None] | None = None) -> None:
        raise RuntimeError("Flatpak can't be uninstalled from Lutris")

    @property
    def game_path(self):
        # The directory saved by the installer contains external game data,
        # not the deployment managed by Flatpak.
        directory = self.game_data.get("directory")
        return os.path.abspath(os.path.expanduser(directory)) if directory else ""

    def remove_game_data(self, app_id=None, game_path=None, **kwargs):
        # Game.uninstall(delete_files=True) requests external data removal.
        # The dialog uninstalls the package separately, without a game_path.
        if game_path is not None:
            if not _flatpak.is_game_data_directory(game_path, self.system_config):
                return
            system.remove_folder(game_path)
            return
        # Explicit application removal only; never delete the Flatpak installation tree.
        if self.game_config.get("install_type", "user") != "user":
            raise GameConfigError(_("Only user Flatpak applications can be uninstalled from Lutris."))
        try:
            uninstall_user(
                self.game_config.get("appid", ""),
                self.game_config.get("arch", ""),
                self.game_config.get("branch", ""),
            )
        except FlatpakPrerequisiteError as error:
            raise FlatpakSetupError(error.reason) from error
        except FlatpakInstallError as error:
            raise GameConfigError(str(error)) from error

    def get_command(self):
        arch = self.game_config.get("arch", "")
        branch = self.game_config.get("branch", "")
        fcommand = self.game_config.get("fcommand", "")
        command = _flatpak.get_bare_run_command(arch, fcommand, branch, self.game_config.get("install_type", "user"))
        directory = self.game_path
        working_dir = self.game_config.get("working_dir", "")
        if working_dir:
            working_dir = os.path.expanduser(working_dir)
            if not os.path.isabs(working_dir):
                working_dir = os.path.join(directory or os.path.expanduser("~"), working_dir)
            working_dir = os.path.abspath(working_dir)
        else:
            working_dir = directory
        for path in dict.fromkeys((directory, working_dir)):
            if path:
                # A colon is Flatpak's filesystem permission suffix separator.
                if ":" in path or path == "/":
                    raise GameConfigError("Flatpak game directories must not be '/' or contain ':'.")
                command.append(f"--filesystem={path}:rw")
        if working_dir:
            command.append(f"--cwd={working_dir}")
        return command

    def play(self):
        appid = self.game_config.get("appid", "")
        args = self.game_config.get("args", "")

        if not appid:
            raise GameConfigError(_("No application specified."))

        if appid.count(".") < 2:
            raise GameConfigError(
                _("Application ID is not specified in correct format.Must be something like: tld.domain.app")
            )

        if any(x in appid for x in ("--", "/")):
            raise GameConfigError(_("Application ID field must not contain options or arguments."))

        command = self.get_command() + [appid]
        if args:
            command.extend(split_arguments(args))
        return {"command": command}
