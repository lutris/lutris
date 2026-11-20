"""What the core asks of whatever UI is driving it.

Launching a game or installing a runner sometimes needs the user: to confirm,
pick a configuration or provide a file. Rather than open dialogs itself, core
code calls one of these delegates. The defaults here need no UI and make the
choices a non-interactive caller would; a frontend subclasses them to ask the
user (lutris.gui.dialogs.delegates does that for GTK).
"""

from collections.abc import Callable
from gettext import gettext as _
from typing import TYPE_CHECKING

from lutris.exceptions import UnavailableRunnerError
from lutris.services import SERVICES
from lutris.util.downloader import SimpleDownloader

if TYPE_CHECKING:
    from lutris.config import LaunchConfigDict
    from lutris.game import Game
    from lutris.services.base import BaseService


class Delegate:
    def get_service(self, service_id: str) -> "BaseService":
        """Returns a new service object by its id. This seems dumb, but it is a work-around
        for Python's circular import limitations."""
        return SERVICES[service_id]()


class LaunchUIDelegate(Delegate):
    """These objects provide UI for the game while it is being launched;
    one provided to the launch() method.

    The default implementation provides no UI and makes default choices for
    the user, but DialogLaunchUIDelegate implements this to show dialogs and ask the
    user questions. Windows then inherit from DialogLaunchUIDelegate.

    If these methods throw any errors are reported via tha game-error signal;
    that is not part of this delegate because errors can be report outside of
    the launch() method, where no delegate is available.
    """

    def check_game_launchable(self, game: "Game") -> bool:
        """See if the game can be launched. If there are adverse conditions,
        this can warn the user and ask whether to launch. If this returs
        False, the launch is cancelled. The default is to return True with no
        actual checks.
        """
        if not game.runner.is_installed():
            raise UnavailableRunnerError(_("The required runner '%s' is not installed.") % game.runner.name)
        return True

    def select_game_launch_config(self, game: "Game") -> "LaunchConfigDict | None":
        """Prompt the user for which launch config to use. Returns None
        if the user cancelled, an empty dict for the primary game configuration
        and the launch_config as a dict if one is selected.

        The default is the select the primary game.
        """
        return {}  # primary game

    def wait_for_component_updates(self, game: "Game", on_ready: Callable[[], None]) -> None:
        """Defer the launch until any in-progress Lutris component downloads
        complete. Launching while runtime/wine components are being installed
        can crash games or corrupt their Wine prefix (see issue #6702).

        The default invokes on_ready() immediately; DialogLaunchUIDelegate
        overrides this to show a wait dialog with a 'Launch Anyway' override.
        If the user cancels, on_ready is never called.
        """
        on_ready()


class InstallUIDelegate(Delegate):
    """These objects provide UI for a runner as it is installing itself.
    One of these must be provided to the install() method.

    The default implementation provides no UI and makes default choices for
    the user, but DialogInstallUIDelegate implements this to show dialogs and
    ask the user questions. Windows then inherit from DialogLaunchUIDelegate.
    """

    def show_install_yesno_inquiry(self, question: str, title: str) -> bool:
        """Called to ask the user a yes/no question.

        The default is 'yes'."""
        return True

    def show_install_file_inquiry(self, question: str, title: str, message: str) -> str | None:
        """Called to ask the user for a file.

        Lutris first asks the user the question given (showing the title);
        if the user answers 'Yes', it asks for the file using the message.

        Returns None if the user answers 'No' or cancels out. Returns the
        file path if the user selected one.

        The default is to return None always.
        """
        return None

    def download_install_file(self, url: str, destination: str) -> bool:
        """Downloads a file from a URL to a destination, overwriting any
        file at that path.

        Returns True if sucessful, and False if the user cancels.

        The default is to download with no UI, and no option to cancel.
        """
        downloader = SimpleDownloader(url, destination, overwrite=True)
        downloader.start()
        return downloader.join()


class CommandLineUIDelegate(LaunchUIDelegate):
    """This delegate can provide user selections that were provided on the command line."""

    def __init__(self, launch_config_name: str | None):
        self.launch_config_name = launch_config_name

    def select_game_launch_config(self, game: "Game") -> "LaunchConfigDict | None":
        if not self.launch_config_name:
            return {}

        game_config = game.config.game_level.get("game", {}) if game.config else {}
        configs: list["LaunchConfigDict"] = game_config.get("launch_configs") or []

        for config in configs:
            if config.get("name") == self.launch_config_name:
                return config

        raise RuntimeError("The launch configuration '%s' could not be found." % self.launch_config_name)
