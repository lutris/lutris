"""Xenia Runner (Wine-based)"""

import os
from collections.abc import Callable
from gettext import gettext as _
from typing import TYPE_CHECKING

from lutris import settings
from lutris.exceptions import MissingExecutableError, MissingGameExecutableError
from lutris.runners.runner import Runner
from lutris.runners.wine import wine
from lutris.util import system
from lutris.util.upstream import ReleaseSource
from lutris.util.wine.wine import get_default_wine_version

if TYPE_CHECKING:
    from lutris.delegates import InstallUIDelegate
    from lutris.installer.interpreter import ScriptInterpreter


class xenia(wine):
    runner_name = "xenia"
    human_name = _("Xenia")
    description = _("Xbox 360 Emulator")
    platform_dict = Runner.to_platform_dict([_("Microsoft Xbox 360")])
    runnable_alone = True
    multiple_versions = False
    runner_executable = "xenia_canary.exe"
    upstream = ReleaseSource("xenia-canary/xenia-canary", r"^xenia_canary_windows\.7z$", prereleases=True)
    upstream_arch = "x86_64"
    entry_point_option = "main_file"

    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("Game file"),
            "help": _("Path to .xex or .iso file"),
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

    @property
    def game_exe(self):
        """Return path to the managed Xenia Windows binary."""
        return os.path.join(settings.RUNNER_DIR, self.runner_executable_path)

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

    def is_installed(self, flatpak_allowed: bool = True, version: str | None = None, fallback: bool = True) -> bool:
        """Check if the Xenia binary is installed."""
        return os.path.isfile(self.game_exe)

    def is_installed_for(self, interpreter: "ScriptInterpreter") -> bool:
        return self.is_installed()

    def install(
        self,
        install_ui_delegate: "InstallUIDelegate",
        version: str | None = None,
        callback: Callable[[], None] | None = None,
    ) -> None:
        Runner.install(self, install_ui_delegate, version, callback)

    def get_command(self):
        """Return the command that launches Xenia itself.

        The Windows Xenia binary is appended to the Wine/umu launcher here so
        that both play() and running the runner standalone launch the emulator;
        for a umu/Proton wine version the bare launcher would otherwise have no
        executable to run. play() only needs to add the game path on top.
        """
        xenia_exe = self.game_exe
        if not system.path_exists(xenia_exe):
            raise MissingExecutableError(_("Xenia executable not found at '%s'") % xenia_exe)
        return super().get_command() + [xenia_exe]

    def play(self):
        """Launch an Xbox 360 game through Xenia under Wine."""
        command = self.get_command()

        if self.runner_config.get("fullscreen"):
            command.append("--fullscreen")

        game_path = self.game_config.get("main_file") or ""
        if not system.path_exists(game_path):
            raise MissingGameExecutableError(filename=game_path)
        command.append(game_path)

        return {"command": command, "env": self.get_env(os_env=False)}
