"""Xenia Runner (Wine-based)"""

import os
from functools import cached_property
from gettext import gettext as _

from lutris import settings
from lutris.exceptions import MissingExecutableError, MissingGameExecutableError
from lutris.runners.runner import Runner
from lutris.runners.wine import wine
from lutris.util import system
from lutris.util.http import Request
from lutris.util.log import logger
from lutris.util.wine.wine import get_default_wine_version

XENIA_LATEST_RELEASE_API = "https://api.github.com/repos/xenia-canary/xenia-canary/releases/latest"


class xenia(wine):
    runner_name = "xenia"
    human_name = _("Xenia")
    description = _("Xbox 360 Emulator")
    platform_dict = Runner.to_platform_dict([_("Microsoft Xbox 360")])
    runnable_alone = True
    multiple_versions = False
    runner_executable = "xenia_canary.exe"
    entry_point_option = "main_file"

    @cached_property
    def download_url(self):
        """Resolve latest Xenia Canary Windows asset URL via GitHub API."""
        logger.debug("Fetching latest Xenia Canary release info from %s", XENIA_LATEST_RELEASE_API)

        release = Request(XENIA_LATEST_RELEASE_API).get().json
        assets = release.get("assets", []) if release else []
        windows_assets = [a for a in assets if "windows" in a.get("name", "").lower()]

        if len(windows_assets) != 1:
            raise RuntimeError(
                "Expected exactly one Xenia Canary Windows asset, found %d: %s"
                % (len(windows_assets), [a.get("name") for a in windows_assets])
            )
        return windows_assets[0]["browser_download_url"]

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

    system_options_override = [{"option": "disable_runtime", "default": True}]

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

    def is_installed(self, flatpak_allowed=True, version=None, fallback=True):
        """Check if the Xenia binary is installed."""
        return os.path.isfile(self.game_exe)

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
