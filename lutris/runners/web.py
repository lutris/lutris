"""Open web games in a user-configured browser."""

import string
from gettext import gettext as _
from pathlib import Path
from urllib.parse import urlsplit

from lutris.exceptions import GameConfigError, MissingExecutableError
from lutris.runners.runner import GamePlayInfoDict, Runner
from lutris.util import system
from lutris.util.strings import split_arguments


class web(Runner):
    human_name = _("Web")
    description = _("Opens web games in a browser")
    platform_dict = Runner.to_platform_dict([_("Web")])
    game_options = [
        {
            "option": "main_file",
            "type": "string",
            "label": _("Full URL or HTML file path"),
        }
    ]
    runner_options = [
        {
            "option": "custom_browser_executable",
            "type": "file",
            "label": _("Browser executable"),
        },
        {
            "option": "custom_browser_args",
            "type": "string",
            "label": _("Browser arguments"),
            "default": '"$GAME"',
            "help": _("Use $GAME or $URL to insert the game URL."),
        },
    ]

    def get_executable(self) -> str:
        browser = self.runner_config.get("custom_browser_executable") or "xdg-open"
        if executable := system.find_executable(browser):
            return executable
        raise MissingExecutableError(_("The browser executable '%s' could not be found.") % browser)

    def play(self) -> GamePlayInfoDict:
        url = self.game_config.get("main_file")
        if not url:
            raise GameConfigError(_("Enter a URL or HTML file path for the game."))
        if not urlsplit(url).scheme:
            path = Path(url).expanduser()
            if not path.is_file():
                raise GameConfigError(_("The file %s does not exist.") % path)
            url = path.resolve().as_uri()

        template = self.runner_config.get("custom_browser_args") or '"$GAME"'
        args = [string.Template(arg).safe_substitute(GAME=url, URL=url) for arg in split_arguments(template)]
        return {"command": [self.get_executable(), *args]}
