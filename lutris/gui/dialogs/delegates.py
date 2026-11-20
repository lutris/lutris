from collections.abc import Callable
from gettext import gettext as _
from typing import TYPE_CHECKING, Any, cast

from gi.repository import Gdk, Gio, Gtk

from lutris.delegates import Delegate, InstallUIDelegate, LaunchUIDelegate, ServiceLoginUIDelegate
from lutris.game import Game
from lutris.gui import dialogs
from lutris.gui.dialogs.cloud_sync import ask_cloud_sync_conflict
from lutris.gui.dialogs.download import DownloadDialog
from lutris.installer import InstallationKind
from lutris.util.downloader import BaseDownloader

if TYPE_CHECKING:
    from lutris.config import LaunchConfigDict
    from lutris.gui.application import LutrisApplication
    from lutris.gui.lutriswindow import LutrisWindow
    from lutris.services.base import BaseService, OnlineService


class DialogDelegate(Delegate):
    """Asks the user through GTK dialogs. Windows inherit this (through the delegates
    below), so the dialogs are parented to `self`."""

    def show_notice(self, message_markup: str, secondary: str | None = None) -> None:
        dialogs.NoticeDialog(message_markup, secondary, parent=cast(Gtk.Widget, self))

    def ask_question(self, title: str, question_markup: str) -> bool:
        dialog = dialogs.QuestionDialog({"parent": self, "question": question_markup, "title": title})
        return dialog.result == Gtk.ResponseType.YES

    def ask_for_text(self, title: str, question_markup: str, initial_value: str = "") -> str | None:
        dialog = dialogs.InputDialog(
            {"parent": self, "question": question_markup, "title": title, "initial_value": initial_value}
        )
        if dialog.run() != Gtk.ResponseType.OK:
            return None
        return dialog.user_value

    def ask_for_file(self, message: str, default_path: str | None = None) -> str | None:
        return dialogs.FileDialog(message, default_path=default_path, parent=cast(Gtk.Window, self)).filename

    def start_installer(
        self,
        installers: list[dict[str, Any]],
        service: "BaseService | None" = None,
        appid: str | None = None,
        installation_kind: InstallationKind = InstallationKind.INSTALL,
    ) -> None:
        application = cast("LutrisApplication", Gio.Application.get_default())
        application.show_installer_window(installers, service, appid, installation_kind=installation_kind)


class DialogServiceLoginUIDelegate(DialogDelegate, ServiceLoginUIDelegate):
    """This provides UI for logging in to services via dialogs."""

    def install_service_launcher(self, service: "OnlineService") -> None:
        self.show_notice(_("Install the %s launcher and add it to Lutris first.") % service.name)

    def show_web_login(self, service: "OnlineService") -> None:
        self.show_notice(_("Use the Qt frontend to sign in to %s in your browser.") % service.name)

    def ask_for_humble_bundle_cookies(self) -> str | None:
        return dialogs.HumbleBundleCookiesDialog(parent=cast(Gtk.Widget, self)).cookies_content


class DialogInstallUIDelegate(DialogDelegate, InstallUIDelegate):
    """This provides UI for runner installation via dialogs."""

    def show_install_yesno_inquiry(self, question: str, title: str) -> bool:
        dialog = dialogs.QuestionDialog(
            {
                "parent": self,
                "question": question,
                "title": title,
            }
        )
        return Gtk.ResponseType.YES == dialog.result

    def show_install_file_inquiry(self, question: str, title: str, message: str) -> str | None:
        dlg = dialogs.QuestionDialog(
            {
                "parent": self,
                "question": question,
                "title": title,
            }
        )
        if dlg.result == dlg.YES:
            file_dlg = dialogs.FileDialog(message)
            return file_dlg.filename
        return None

    def download_install_file(self, url: str, destination: str) -> bool:
        dialog = DownloadDialog(url, destination, parent=self)
        dialog.run()
        return dialog.downloader.state == BaseDownloader.COMPLETED


class DialogLaunchUIDelegate(DialogDelegate, LaunchUIDelegate):
    """This provides UI for game launch via dialogs."""

    def check_game_launchable(self, game: Game) -> bool:
        if not game.runner.is_installed():
            installed = game.runner.install_dialog(cast(InstallUIDelegate, self))
            if not installed:
                return False

        return True

    def resolve_cloud_sync_conflict(self, game_name: str, location_name: str) -> str | None:
        return ask_cloud_sync_conflict(game_name, location_name)

    def wait_for_component_updates(self, game: Game, on_ready: Callable[[], None]) -> None:
        from lutris.gui.lutriswindow import LutrisWindow  # noqa: PLC0415

        window = cast(LutrisWindow, self)
        if window.is_download_queue_empty:
            on_ready()
            return

        dialog = dialogs.ComponentUpdateWaitDialog(
            is_queue_empty=lambda: window.is_download_queue_empty,
            parent=window,
        )

        def on_response(_dialog, response):
            if response == Gtk.ResponseType.OK:
                on_ready()

        dialog.connect("response", on_response)
        dialog.show()

    def select_game_launch_config(self, game: Game) -> "LaunchConfigDict | None":
        config = game.config

        if not config:
            return {}  # use primary configuration

        game_config = config.game_level.get("game", {})
        configs: list["LaunchConfigDict"] = game_config.get("launch_configs")

        if not configs:
            return {}  # use primary configuration

        def get_preferred_config_index() -> int | None:
            # Validate that the settings are still valid; we need the index to
            # cope when two configs have the same name but we insist on a name
            # match. Returns None if it can't find a match, and then the user
            # must decide.
            preferred_name = game_config.get("preferred_launch_config_name")
            preferred_index: int = game_config.get("preferred_launch_config_index")

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

        def save_preferred_config(index: int) -> None:
            name = configs[index - 1].get("name") if index > 0 else Game.PRIMARY_LAUNCH_CONFIG_NAME
            game_config["preferred_launch_config_index"] = index
            game_config["preferred_launch_config_name"] = name
            config.save()

        def reset_preferred_config() -> None:
            game_config.pop("preferred_launch_config_index", None)
            game_config.pop("preferred_launch_config_name", None)
            config.save()

        keymap = Gdk.Keymap.get_default()
        if keymap.get_modifier_state() & Gdk.ModifierType.SHIFT_MASK:
            config_index = None
        else:
            config_index = get_preferred_config_index()

        if config_index is None:
            dlg = dialogs.LaunchConfigSelectDialog(
                game, configs, title=_("Select game to launch"), parent=cast("LutrisWindow", self)
            )
            if not dlg.confirmed:
                return None  # no error here- the user cancelled out

            config_index = dlg.config_index
            if dlg.dont_show_again:
                save_preferred_config(config_index)
            else:
                reset_preferred_config()

        return configs[config_index - 1] if config_index > 0 else {}
