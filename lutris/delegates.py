"""What the core asks of whatever UI is driving it.

Launching a game, installing a runner or logging in to a service sometimes
needs the user: to confirm, pick a configuration, type something or provide a
file. Rather than open dialogs itself, core code calls a delegate, passed in by
whoever started the operation. The defaults here need no UI and make the
choices a non-interactive caller would; a frontend subclasses them to ask the
user (lutris.gui.dialogs.delegates does that for GTK).
"""

from collections.abc import Callable
from gettext import gettext as _
from typing import TYPE_CHECKING, Any

from lutris.exceptions import UnavailableRunnerError
from lutris.installer import InstallationKind
from lutris.services import SERVICES
from lutris.util.downloader import SimpleDownloader
from lutris.util.log import logger

if TYPE_CHECKING:
    from lutris.config import LaunchConfigDict
    from lutris.game import Game
    from lutris.services.base import BaseService, OnlineService


class Delegate:
    """The questions any operation may need to put to the user.

    Messages and questions are Pango markup (a small subset of HTML), which a
    frontend renders or strips.
    """

    def get_service(self, service_id: str) -> "BaseService":
        """Returns a new service object by its id. This seems dumb, but it is a work-around
        for Python's circular import limitations."""
        return SERVICES[service_id]()

    def show_notice(self, message_markup: str, secondary: str | None = None) -> None:
        """Tell the user something. The default only logs it."""
        logger.info("%s %s", message_markup, secondary or "")

    def ask_question(self, title: str, question_markup: str) -> bool:
        """Ask the user a yes or no question. The default answers no."""
        logger.info("Not asking '%s' with no user to answer; assuming no", title)
        return False

    def ask_for_text(self, title: str, question_markup: str, initial_value: str = "") -> str | None:
        """Ask the user to type something; returns None if they cancel. The default cancels."""
        return None

    def ask_for_file(self, message: str, default_path: str | None = None) -> str | None:
        """Ask the user to pick a file; returns None if they cancel. The default cancels."""
        return None

    def start_installer(
        self,
        installers: list[dict[str, Any]],
        service: "BaseService | None" = None,
        appid: str | None = None,
        installation_kind: InstallationKind = InstallationKind.INSTALL,
    ) -> None:
        """Install a game with one of these installer scripts, letting the user pick one and
        answer its questions; service and appid identify the service game being installed.
        This returns once the installer has started. The default can't run one, and only logs it."""
        logger.warning("Not installing %s with no user to run the installer", installers[0].get("name", "a game"))


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

    def resolve_cloud_sync_conflict(self, game_name: str, location_name: str) -> str | None:
        """Ask which copy of a game's saves to keep when both the local and the cloud
        copies changed; returns "download", "upload" or None to skip that location.
        This is a ConflictResolver (lutris.services.gog_cloud_hooks), so it's called on
        a worker thread and may block it. The default skips.
        """
        return None

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


class ServiceLoginUIDelegate(Delegate):
    """Provides the UI a service needs to log in; passed to OnlineService.login().

    Logging in always needs a user, so the defaults only log that they can't.
    """

    def install_service_launcher(self, service: "OnlineService") -> None:
        """Help the user register the game's launcher before signing in to the service."""
        logger.warning("%s needs its launcher installed before logging in", service.name)

    def show_web_login(self, service: "OnlineService") -> None:
        """Offer the service's browser sign-in flow."""
        logger.warning("Can't log in to %s without a user to show its login page to", service.name)

    def ask_for_humble_bundle_cookies(self) -> str | None:
        """Ask the user for their Humble Bundle cookies, exported from a browser in which
        they're logged in. Returns the cookies file's contents, or None if they cancel."""
        return None
