from gettext import gettext as _
from typing import Optional

from gi.repository import Gdk, Gtk  # type: ignore

from lutris.exceptions import UnavailableRunnerError
from lutris.game import Game
from lutris.gui import dialogs
from lutris.gui.dialogs.download import DownloadDialog
from lutris.services import get_enabled_services
from lutris.util.downloader import Downloader


class Delegate:
    def get_service(self, service_id):
        """Returns a new service object by its id. This seems dumb, but it is a work-around
        for Python's circular import limitations."""
        return get_enabled_services()[service_id]()


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

    def check_game_launchable(self, game):
        """See if the game can be launched. If there are adverse conditions,
        this can warn the user and ask whether to launch. If this returs
        False, the launch is cancelled. The default is to return True with no
        actual checks.
        """
        if not game.runner.is_installed():
            raise UnavailableRunnerError(_("The required runner '%s' is not installed.") % game.runner.name)
        return True

    def select_game_launch_config(self, game):
        """Prompt the user for which launch config to use. Returns None
        if the user cancelled, an empty dict for the primary game configuration
        and the launch_config as a dict if one is selected.

        The default is the select the primary game.
        """
        return {}  # primary game


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

    def show_install_file_inquiry(self, question: str, title: str, message: str) -> Optional[str]:
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
        downloader = Downloader(url, destination, overwrite=True)
        downloader.start()
        return downloader.join()


class CommandLineUIDelegate(LaunchUIDelegate):
    """This delegate can provide user selections that were provided on the command line."""

    def __init__(self, launch_config_name):
        self.launch_config_name = launch_config_name

    def select_game_launch_config(self, game):
        if not self.launch_config_name:
            return {}

        game_config = game.config.game_level.get("game", {})
        configs = game_config.get("launch_configs")

        for config in configs:
            if config.get("name") == self.launch_config_name:
                return config

        raise RuntimeError("The launch configuration '%s' could not be found." % self.launch_config_name)


class DialogInstallUIDelegate(InstallUIDelegate):
    """This provides UI for runner installation via dialogs."""

    def show_install_yesno_inquiry(self, question, title):
        dialog = dialogs.QuestionDialog(
            {
                "parent": self,
                "question": question,
                "title": title,
            }
        )
        return Gtk.ResponseType.YES == dialog.result

    def show_install_file_inquiry(self, question, title, message):
        dlg = dialogs.QuestionDialog(
            {
                "parent": self,
                "question": question,
                "title": title,
            }
        )
        if dlg.result == dlg.YES:
            dlg = dialogs.FileDialog(message)
            return dlg.filename

    def download_install_file(self, url: str, destination: str) -> bool:
        dialog = DownloadDialog(url, destination, parent=self)
        dialog.run()
        return dialog.downloader.state == Downloader.COMPLETED


class DialogLaunchUIDelegate(LaunchUIDelegate):
    """This provides UI for game launch via dialogs."""

    def check_game_launchable(self, game):
        if not game.runner.is_installed():
            installed = game.runner.install_dialog(self)
            if not installed:
                return False

        return True

    def select_game_launch_config(self, game):
        game_config = game.config.game_level.get("game", {})
        configs = game_config.get("launch_configs")

        def get_preferred_config_index():
            # Validate that the settings are still valid; we need the index to
            # cope when two configs have the same name but we insist on a name
            # match. Returns None if it can't find a match, and then the user
            # must decide.
            preferred_name = game_config.get("preferred_launch_config_name")
            preferred_index = game_config.get("preferred_launch_config_index")

            if preferred_index == 0 or preferred_name == Game.PRIMARY_LAUNCH_CONFIG_NAME:
                return 0

            if preferred_name:
                if preferred_index:
                    try:
                        if configs[preferred_index - 1].get("name") == preferred_name:
                            return preferred_index
                    except IndexError:
                        pass

                for index, config in enumerate(configs):
                    if config.get("name") == preferred_name:
                        return index + 1

            return None

        def save_preferred_config(index):
            name = configs[index - 1].get("name") if index > 0 else Game.PRIMARY_LAUNCH_CONFIG_NAME
            game_config["preferred_launch_config_index"] = index
            game_config["preferred_launch_config_name"] = name
            game.config.save()

        def reset_preferred_config():
            game_config.pop("preferred_launch_config_index", None)
            game_config.pop("preferred_launch_config_name", None)
            game.config.save()

        if not configs:
            return {}  # use primary configuration

        keymap = Gdk.Keymap.get_default()
        if keymap.get_modifier_state() & Gdk.ModifierType.SHIFT_MASK:
            config_index = None
        else:
            config_index = get_preferred_config_index()

        if config_index is None:
            dlg = dialogs.LaunchConfigSelectDialog(game, configs, title=_("Select game to launch"), parent=self)
            if not dlg.confirmed:
                return None  # no error here- the user cancelled out

            config_index = dlg.config_index
            if dlg.dont_show_again:
                save_preferred_config(config_index)
            else:
                reset_preferred_config()

        return configs[config_index - 1] if config_index > 0 else {}
