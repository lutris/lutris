from gettext import gettext as _
from os import path

from lutris import settings
from lutris.exceptions import MissingGameExecutableError
from lutris.runners.runner import Runner
from lutris.util import system


class duckstation(Runner):
    human_name = _("DuckStation")
    description = _("PlayStation 1 Emulator")
    platforms = [_("Sony PlayStation")]
    runnable_alone = True
    runner_directory = "duckstation"
    runner_executable = runner_directory + "/DuckStation-x64.AppImage"
    settings_directory = path.expanduser("~/.local/share/" + runner_directory)
    download_url = "https://github.com/stenzek/duckstation/releases/download/latest/DuckStation-x64.AppImage"

    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("ISO file"),
            "help": _("The game image, commonly called a ISO image."),
            "default_path": "game_path",
        }
    ]

    runner_options = [
        {
            "option": "bigpicture",
            "type": "bool",
            "label": _("Big Picture"),
            "help": _("Automatically starts big picture UI."),
            "default": False,
        },
        {
            "option": "nogui",
            "type": "bool",
            "label": _("No GUI"),
            "help": _("Disables main window from being shown, exits on shutdown."),
            "default": False,
        },
        {
            "option": "fullscreen",
            "type": "bool",
            "label": _("Fullscreen"),
            "help": _("Enters fullscreen mode immediately after starting."),
            "default": True,
        },
        {
            "option": "fastboot",
            "type": "bool",
            "label": _("Fast Boot"),
            "help": _("Force fast boot for provided filename."),
            "default": False,
        },
    ]

    system_options_override = [
        {
            "option": "disable_runtime",
            "default": True,
        },
    ]

    def uninstall(self, uninstall_callback=None):
        if path.isdir(self.settings_directory):
            system.delete_folder(self.settings_directory)
        if path.isdir(path.join(settings.RUNNER_DIR, self.runner_directory)):
            system.delete_folder(path.join(settings.RUNNER_DIR, self.runner_directory))
        uninstall_callback()

    def run(self, ui_delegate):
        initial_arguments = self.get_command()

        # Big Picture
        if self.runner_config.get("bigpicture"):
            initial_arguments.append("-bigpicture")
        system.execute(initial_arguments)

    def play(self):
        arguments = self.get_command()

        # Big Picture
        if self.runner_config.get("bigpicture"):
            arguments.append("-bigpicture")
        # No GUI
        if self.runner_config.get("nogui"):
            arguments.append("-nogui")
        # Fullscreen
        if self.runner_config.get("fullscreen"):
            arguments.append("-fullscreen")
        # Fast Boot
        if self.runner_config.get("fastboot"):
            arguments.append("-fastboot")

        iso = self.game_config.get("main_file") or ""
        if not system.path_exists(iso):
            raise MissingGameExecutableError(filename=iso)
        arguments.append(iso)
        return {"command": arguments}
