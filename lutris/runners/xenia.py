"""Xenia Runner (Wine-based)"""

import os
from gettext import gettext as _

from lutris import settings
from lutris.exceptions import MissingExecutableError, MissingGameExecutableError
from lutris.runners.wine import wine
from lutris.util import system
from lutris.util.wine.wine import get_default_wine_version


class xenia(wine):
    human_name = _("Xenia")
    description = _("Xbox 360 Emulator")
    platforms = [_("Microsoft Xbox 360")]
    runnable_alone = True
    multiple_versions = False
    runner_executable = "xenia/xenia_canary.exe"
    download_url = (
        "https://github.com/xenia-canary/xenia-canary-releases/releases/latest/download/xenia_canary_windows.zip"
    )
    entry_point_option = "main_file"

    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("Game file"),
            "help": _("Path to .xex or .iso file"),
            "default_path": "game_path",
        },
        {
            "option": "prefix",
            "type": "directory",
            "label": _("Wine prefix"),
            "help": _("Wine prefix for Xenia. Leave empty for default."),
        },
        {
            "option": "arch",
            "type": "choice",
            "label": _("Prefix architecture"),
            "choices": [(_("64-bit"), "win64")],
            "default": "win64",
            "help": _("Xenia requires a 64-bit Wine prefix"),
        },
    ]

    runner_options = [
        {
            "option": "fullscreen",
            "type": "bool",
            "label": _("Fullscreen"),
            "default": True,
        },
    ] + wine.runner_options

    system_options_override = [{"option": "disable_runtime", "default": True}]

    @property
    def game_exe(self):
        """Return path to the managed Xenia Windows binary."""
        return os.path.join(settings.RUNNER_DIR, self.runner_executable)

    @property
    def prefix_path(self):
        """Return prefix path, defaulting to a location in the runner directory."""
        prefix = self.game_config.get("prefix")
        if prefix:
            return os.path.expanduser(prefix)
        return os.path.join(self.directory, "prefix")

    @property
    def wine_arch(self):
        """Xenia requires 64-bit."""
        return "win64"

    def read_version_from_config(self, default=None):
        """Read Wine version from config using the correct runner slug."""
        for level in [self.config.game_level, self.config.runner_level]:
            if self.name in level:
                runner_version = level[self.name].get("version")
                if runner_version:
                    return runner_version
        if default:
            return default
        return get_default_wine_version()

    def is_installed(self, flatpak_allowed=True, version=None, fallback=True):
        """Check if the Xenia binary is installed."""
        return os.path.isfile(self.game_exe)

    def play(self):
        """Launch an Xbox 360 game through Xenia under Wine."""
        launch_info = {"env": self.get_env(os_env=False)}

        xenia_exe = self.game_exe
        if not system.path_exists(xenia_exe):
            raise MissingExecutableError(_("Xenia executable not found at '%s'") % xenia_exe)

        command = self.get_command()
        command.append(xenia_exe)

        if self.runner_config.get("fullscreen"):
            command.append("--fullscreen")

        game_path = self.game_config.get("main_file") or ""
        if not system.path_exists(game_path):
            raise MissingGameExecutableError(filename=game_path)
        command.append(game_path)

        launch_info["command"] = command
        return launch_info
