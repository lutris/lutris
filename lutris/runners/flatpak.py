import os
import shutil
from gettext import gettext as _
from pathlib import Path

from lutris.command import MonitoredCommand
from lutris.runners.runner import Runner
from lutris.util.strings import split_arguments


class flatpak(Runner):
    """
    Runner for Flatpak applications.
    """

    description = _("Runs Flatpak applications")
    platforms = [_("Linux")]
    entry_point_option = "application"
    human_name = _("Flatpak")
    runnable_alone = False
    system_options_override = [{"option": "disable_runtime", "default": True}]
    # runner_executable = "flatpak"
    install_locations = {
        "system": "var/lib/flatpak/app/",
        "user": f"{Path.home()}/.local/share/flatpak/app/"
    }

    game_options = [
        {
            "option": "appid",
            "type": "string",
            "label": _("Application ID"),
            "help": _("The application's unique three-part identifier (tld.domain.app).")
        },
        {
            "option": "arch",
            "type": "string",
            "label": _("Architecture"),
            "help": _("The architecture to run. "
                      "See flatpak --supported-arches for architectures supported by the host."),
            "advanced": True
        },
        {
            "option": "branch",
            "type": "string",
            "label": _("Branch"),
            "help": _("The branch to use."),
            "advanced": True
        },
        {
            "option": "install_type",
            "type": "string",
            "label": _("Install type"),
            "help": _("Can be system or user."),
            "advanced": True
        },
        {
            "option": "args",
            "type": "string",
            "label": _("Args"),
            "help": _("Arguments to be passed to the application.")
        },
        {
            "option": "command",
            "type": "string",
            "label": _("Command"),
            "help": _("The command to run instead of the one listed in the application metadata."),
            "advanced": True
        },
        {
            "option": "working_dir",
            "type": "directory_chooser",
            "label": _("Working directory"),
            "help": _("The directory to run the command in. Note that this must be a directory inside the sandbox."),
            "advanced": True
        },

        {
            "option": "env_vars",
            "type": "string",
            "label": _("Environment variables"),
            "help": _("Set an environment variable in the application. "
                      "This overrides to the Context section from the application metadata."),
            "advanced": True
        }
    ]

    def is_installed(self):
        return shutil.which("flatpak")

    def get_executable(self):
        return shutil.which("flatpak")

    def can_uninstall(self):
        return False

    def uninstall(self):
        pass

    def game_path(self):
        install_type, application, arch, branch = (self.game_data[key] for key in
                                                   ("install_type", "application", "arch", "branch"))
        return os.path.join(self.install_locations[install_type], application, arch, branch)

    def remove_game_data(self, app_id=None, game_path=None, **kwargs):
        if not self.is_installed():
            return False
        command = MonitoredCommand(
            [self.get_executable(), f"uninstall --app --noninteractive {app_id}"],
            runner=self,
            env=self.get_env(),
            title=f"Uninstalling Flatpak App: {app_id}"
        )
        command.start()

    def play(self):
        arch = self.game_config.get("arch", "")
        branch = self.game_config.get("branch", "")
        args = self.game_config.get("args", "")
        app_id = self.game_config.get("application", "")

        if not app_id:
            return {"error": "CUSTOM", "text": "No application specified."}

        if app_id.count(".") < 2:
            return {"error": "CUSTOM", "text": "Application ID is not specified in correct format."
                                               "Must be something like: tld.domain.app"}

        if any(x in app_id for x in ("--", "/")):
            return {"error": "CUSTOM", "text": "Application ID field must not contain options or arguments."}

        command = [self.get_executable(), "run"]
        if arch:
            command.append(f"--arch={arch}")
        if branch:
            command.append(f"--branch={branch}")
        command.append(app_id)
        if args:
            command.extend(split_arguments(args))
        launch_info = {
            "command": command
        }
        return launch_info
