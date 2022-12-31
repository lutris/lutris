from gettext import gettext as _

from gi.repository import Gdk, Gtk

from lutris import runtime
from lutris.game import Game
from lutris.gui import dialogs
from lutris.gui.dialogs.download import DownloadDialog
from lutris.runners import wine
from lutris.runners.runner import Runner
from lutris.util.downloader import Downloader
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import logger


class DialogInstallUIDelegate(Runner.InstallUIDelegate):
    """This provides UI for runner installation via dialogs."""

    def check_wine_availability(self):
        if not wine.get_wine_version() and not LINUX_SYSTEM.is_flatpak:
            dlg = dialogs.WineNotInstalledWarning(parent=self, cancellable=True)
            if dlg.result != Gtk.ResponseType.OK:
                return False

        return True

    def show_install_notice(self, message, secondary=None):
        dialogs.NoticeDialog(message, secondary, parent=self)

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

    def download_install_file(self, url, destination):
        dialog = DownloadDialog(url, destination, parent=self)
        dialog.run()
        return dialog.downloader.state == Downloader.COMPLETED


class DialogLaunchUIDelegate(Game.LaunchUIDelegate):
    """This provides UI for game launch via dialogs."""

    def check_game_launchable(self, game):
        if not game.runner.is_installed():
            installed = game.runner.install_dialog(self)
            if not installed:
                return False

        if game.runner.use_runtime():
            if runtime.RuntimeUpdater.is_updating:
                logger.warning("Game launching with the runtime is updating")
                dlg = dialogs.WarningDialog(_("Runtime currently updating"), _(
                    "Game might not work as expected"), parent=self)
                if dlg.result != Gtk.ResponseType.OK:
                    return False

        if "wine" in game.runner_name and not wine.get_wine_version() and not LINUX_SYSTEM.is_flatpak:
            dlg = dialogs.WineNotInstalledWarning(parent=self, cancellable=True)
            if dlg.result != Gtk.ResponseType.OK:
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
            dlg = dialogs.LaunchConfigSelectDialog(game, configs, title=_(
                "Select game to launch"), parent=self, has_dont_show_again=True)
            if not dlg.confirmed:
                return None  # no error here- the user cancelled out

            config_index = dlg.config_index
            if dlg.dont_show_again:
                save_preferred_config(config_index)
            else:
                reset_preferred_config()

        return configs[config_index - 1] if config_index > 0 else {}
