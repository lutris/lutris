# pylint: disable=wrong-import-position
# pylint: disable=too-many-lines
#
# Copyright (C) 2009 Mathieu Comandon <mathieucomandon@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import signal
import sys
import tempfile
import types
from collections.abc import Callable
from gettext import gettext as _
from typing import TYPE_CHECKING, Any, Type, TypeVar, cast

from gi.repository import Gio, GLib, Gtk

from lutris import settings
from lutris.api import parse_installer_url
from lutris.cli.commands import handle_command_line, start_lutris
from lutris.cli.options import add_options, is_text_command
from lutris.cli.output import CommandOutput
from lutris.database import games as games_db
from lutris.database.services import ServiceGameCollection
from lutris.delegates import CommandLineUIDelegate, LaunchUIDelegate
from lutris.game import GAME_START, GAME_STOPPED, Game
from lutris.gui.dialogs import ErrorDialog, InstallOrPlayDialog, NoticeDialog, display_error
from lutris.gui.dialogs.issue import IssueReportWindow
from lutris.gui.display_backend import GtkDisplayBackend
from lutris.gui.download_queue import DOWNLOAD_QUEUE_COMPLETED
from lutris.gui.exception_backstops import init_exception_backstops
from lutris.gui.installerwindow import INSTALLATION_COMPLETED, INSTALLATION_FAILED, InstallerWindow
from lutris.gui.style_manager import StyleManager
from lutris.gui.widgets.status_icon import LutrisStatusIcon
from lutris.gui.widgets.utils import check_pixbuf_formats
from lutris.installer import InstallationKind, get_installers
from lutris.services import get_enabled_services
from lutris.services.gog_cloud_operation import CLOUD_SYNC_ENDED, CloudSyncOperation, is_cloud_sync_running
from lutris.util import datapath
from lutris.util.display_backend import set_display_backend
from lutris.util.http import HTTPError, Request
from lutris.util.log import file_handler, logger

from ..util.busy import BusyAsyncCall
from .lutriswindow import LutrisWindow

LUTRIS_EXPERIMENTAL_FEATURES_ENABLED = os.environ.get("LUTRIS_EXPERIMENTAL_FEATURES_ENABLED") == "1"

if TYPE_CHECKING:
    from lutris.api import InstallerInfoDict
    from lutris.services.base import BaseService

    GtkWindowType = TypeVar("GtkWindowType", bound=Gtk.Window)


class LutrisApplication(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id=settings.APPLICATION_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
            register_session=True,
        )
        # The command-line frontend's application came first, and hands over to this one
        self.set_default()

        # Prepare the backstop logic just before the first emission hook (or connection) is
        # established; this will apply to all connections from this point forward.
        init_exception_backstops()
        set_display_backend(GtkDisplayBackend())

        GAME_START.register(self.on_game_start)
        GAME_STOPPED.register(self.on_game_stopped)
        settings.SETTINGS_CHANGED.register(self.on_settings_changed)
        INSTALLATION_COMPLETED.register(self.on_install_ended)
        INSTALLATION_FAILED.register(self.on_install_ended)
        DOWNLOAD_QUEUE_COMPLETED.register(self.on_download_queue_completed)
        CLOUD_SYNC_ENDED.register(self.on_cloud_sync_ended)

        GLib.set_application_name(_("Lutris"))
        GLib.set_prgname(settings.APPLICATION_ID)
        self.force_updates = False
        self.css_provider = Gtk.CssProvider.new()
        self.window: LutrisWindow | None = None

        self._running_games = []
        self.app_windows: dict[str, Gtk.Window] = {}
        self.tray = None

        self.quit_on_game_exit = False
        self.style_manager = StyleManager()

        if os.geteuid() == 0:
            NoticeDialog(_("Do not run Lutris as root."))
            sys.exit(2)

        try:
            self.css_provider.load_from_path(os.path.join(datapath.get(), "ui", "lutris.css"))
        except GLib.Error as e:
            logger.exception(e)

        add_options(self)

    def do_startup(self) -> None:  # pylint: disable=arguments-differ
        """Sets up the application on first start."""
        Gtk.Application.do_startup(self)
        file_handler.doRollover()
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        action = Gio.SimpleAction.new("quit")
        action.connect("activate", lambda *x: self.quit())
        self.add_action(action)
        self.add_accelerator("<Primary>q", "app.quit")

    def do_activate(self) -> None:  # pylint: disable=arguments-differ
        if not self.window:
            self.window = LutrisWindow(application=self)
            screen = self.window.props.screen  # pylint: disable=no-member
            Gtk.StyleContext.add_provider_for_screen(screen, self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def start_runtime_updates(self) -> None:
        if os.environ.get("LUTRIS_SKIP_INIT"):
            logger.debug("Skipping initialization")
        elif not self.window:
            logger.error("Runtime updates can't be started with a LutrisWindow.")
        else:
            self.window.start_runtime_updates(self.force_updates)

    def get_window_key(self, **kwargs: Any) -> str:
        if kwargs.get("appid"):
            return str(kwargs["appid"])
        if kwargs.get("runner"):
            return str(kwargs["runner"].name)
        if kwargs.get("installers"):
            installer: dict[str, Any] = kwargs["installers"][0]
            return installer.get("slug") or installer.get("game_slug") or "Malformed script"
        if kwargs.get("game"):
            return str(kwargs["game"].id)
        return str(kwargs)

    def show_window(
        self,
        window_class: Type["GtkWindowType"],
        update_function: Callable[["GtkWindowType"], None] | None = None,
        **kwargs: Any,
    ) -> "GtkWindowType":
        """Instantiate a window keeping 1 instance max

        Params:
            window_class (Gtk.Window): class to create the instance from
            update_function (Callable): Function to initialize or update the window (if possible before being shown)
            kwargs (dict): Additional arguments to pass to the instanciated window

        Returns:
            Gtk.Window: the existing window instance or a newly created one
        """
        window_key = str(window_class.__name__) + self.get_window_key(**kwargs)
        if self.app_windows.get(window_key):
            self.app_windows[window_key].present()
            window_inst = cast("GtkWindowType", self.app_windows[window_key])
            if update_function:
                update_function(window_inst)
            return window_inst
        if issubclass(window_class, Gtk.Dialog):
            if "parent" in kwargs or not self.window:
                window_inst: "GtkWindowType" = window_class(**kwargs)
            else:
                window_inst: "GtkWindowType" = window_class(parent=self.window, **kwargs)
            window_inst.set_application(self)
        else:
            window_inst = window_class(application=self, **kwargs)
        window_inst.connect("destroy", self.on_app_window_destroyed, self.get_window_key(**kwargs))
        if update_function:
            update_function(window_inst)
        self.app_windows[window_key] = window_inst
        window_inst.show()
        window_inst.present()
        return window_inst

    def show_installer_window(
        self,
        installers: list[dict[str, Any]],
        service: "BaseService | None" = None,
        appid: str | None = None,
        installation_kind: InstallationKind = InstallationKind.INSTALL,
    ) -> None:
        self.show_window(
            InstallerWindow, installers=installers, service=service, appid=appid, installation_kind=installation_kind
        )

    def show_lutris_installer_window(self, game_slug: str) -> None:
        def on_installers_ready(installers: list[dict[str, Any]], error: BaseException) -> None:
            if error and self.window:
                display_error(error, parent=self.window)
            elif installers:
                self.show_installer_window(installers)
            else:
                ErrorDialog(_("No installer available."), parent=self.window)

        BusyAsyncCall(get_installers, on_installers_ready, game_slug=game_slug)

    def on_app_window_destroyed(self, app_window: Gtk.Window, window_key: str) -> bool:
        """Remove the reference to the window when it has been destroyed"""
        window_key = str(app_window.__class__.__name__) + window_key
        try:
            del self.app_windows[window_key]
        except KeyError:
            logger.warning("Failed to remove window %s", window_key)
            logger.info("Available windows: %s", ", ".join(self.app_windows.keys()))

        return True  # stop signal propagation

    def do_command_line(self, command_line: Gio.ApplicationCommandLine) -> int:  # noqa: C901  # pylint: disable=arguments-differ
        # pylint: disable=too-many-locals,too-many-return-statements,too-many-branches
        # pylint: disable=too-many-statements
        options = command_line.get_options_dict()
        output = CommandOutput(command_line)

        if options.contains("force"):
            self.force_updates = True

        # Check in the background when the command line just opens the window
        arguments = [arg for arg in command_line.get_arguments()[1:] if arg not in ("-d", "--debug")]
        start_lutris(options, run_checks_async=not arguments)
        check_pixbuf_formats()

        # The commands that need no GUI, forwarded by the command-line frontend; they
        # report their own status when they finish
        if is_text_command(options):
            self.create_asyncio_task(handle_command_line(command_line, self.launch_ui_delegate))
            return 0

        if options.contains("submit-issue"):
            IssueReportWindow(application=self)
            return 0

        url = options.lookup_value(GLib.OPTION_REMAINING)
        try:
            installer_info = self.get_lutris_action(url)
        except ValueError:
            output.print_error(_("%s is not a valid URI") % (url.get_strv() if url else "''"))
            return 1

        game_slug = installer_info["game_slug"]
        action = installer_info["action"]
        service = installer_info["service"]
        appid = installer_info["appid"]
        launch_config_name = installer_info["launch_config_name"]

        revision = installer_info["revision"]

        installer_file = None
        if option := options.lookup_value("install"):
            installer_file = option.get_string()
            if installer_file.startswith(("http:", "https:")):
                try:
                    request = Request(installer_file).get()
                except HTTPError:
                    output.print_error(_("Failed to download %s") % installer_file)
                    return 1
                try:
                    headers = dict(request.response_headers or {})
                    file_name = headers["Content-Disposition"].split("=", 1)[-1]
                except KeyError, IndexError:
                    file_name = os.path.basename(installer_file)
                file_path = os.path.join(tempfile.gettempdir(), file_name)
                output.print(_("download {url} to {file} started").format(url=installer_file, file=file_path))
                with open(file_path, "wb") as dest_file:
                    dest_file.write(request.content)
                installer_file = file_path
                action = "install"
            else:
                installer_file = output.get_path(installer_file)
                action = "install"

            if not os.path.isfile(installer_file):
                output.print_error(_("No such file: %s") % installer_file)
                return 1

        db_game = None
        if game_slug and not service:
            if action == "rungameid":
                # Force db_game to use game id
                if not self.has_tray_icon() and (not self.window or not self.window.is_visible()):
                    self.quit_on_game_exit = True
                db_game = games_db.get_game_by_field(game_slug, "id")
            elif action == "rungame":
                # Force db_game to use game slug
                if not self.has_tray_icon() and (not self.window or not self.window.is_visible()):
                    self.quit_on_game_exit = True
                db_game = games_db.get_game_by_field(game_slug, "slug")
            elif action == "install":
                # Installers can use game or installer slugs
                if not self.has_tray_icon() and (not self.window or not self.window.is_visible()):
                    self.quit_on_game_exit = True
                db_game = games_db.get_game_by_field(game_slug, "slug") or games_db.get_game_by_field(
                    game_slug, "installer_slug"
                )
            else:
                # Dazed and confused, try anything that might works
                db_game = (
                    games_db.get_game_by_field(game_slug, "id")
                    or games_db.get_game_by_field(game_slug, "slug")
                    or games_db.get_game_by_field(game_slug, "installer_slug")
                )

        # If reinstall flag is passed, force the action to install
        if options.contains("reinstall"):
            action = "install"

        # Graphical commands
        self.set_tray_icon()
        self.activate()

        if not action:
            if db_game and db_game["installed"]:
                # Game found but no action provided, ask what to do
                dlg = InstallOrPlayDialog(str(db_game["name"]))
                if not dlg.action:
                    action = "cancel"
                elif dlg.action == "play":
                    action = "rungame"
                elif dlg.action == "install":
                    action = "install"
            elif game_slug or installer_file or service:
                # No game found, default to install if a game_slug or
                # installer_file is provided
                action = "install"

        if service and appid:
            service_game = ServiceGameCollection.get_game(service, appid)
            if service_game:
                service = get_enabled_services()[service]()
                service.install(service_game, self.launch_ui_delegate)
                return 0

        if action == "cancel":
            if self.window and not self.window.is_visible():
                self.quit()
            return 0

        if action == "install":
            installers = get_installers(
                game_slug=game_slug,
                installer_file=installer_file,
                revision=revision,
            )
            if installers:
                self.show_installer_window(installers)
        elif action in ("rungame", "rungameid"):
            if not db_game or not db_game["id"]:
                logger.warning("No game found in library")
                if self.window and not self.window.is_visible():
                    self.quit()
                return 0

            def on_error(error: BaseException) -> None:
                logger.exception("Unable to launch game: %s", error)

            game = Game(str(db_game["id"]))
            game.game_error.register(on_error)
            game.launch(CommandLineUIDelegate(launch_config_name))

            if game.state == game.STATE_STOPPED and self.window and not self.window.is_visible():
                self.quit()

            if self.quit_on_game_exit:

                def game_stop_signal_handler(signum: int, _frame: types.FrameType | None) -> None:
                    logger.debug("signal handler called with signal: %d", signum)
                    game.stop()

                signal.signal(signal.SIGTERM, game_stop_signal_handler)
                signal.signal(signal.SIGINT, game_stop_signal_handler)
        elif self.window:
            self.window.present()
            self.start_runtime_updates()
            # If the Lutris GUI is started by itself, don't quit it when a game stops
            self.quit_on_game_exit = False
        return 0

    def on_settings_changed(self, setting_key: str, new_value: Any, section: str) -> bool:
        if section == "lutris":
            if setting_key == "preferred_theme":
                self.style_manager.preferred_theme = new_value
            elif setting_key == "show_tray_icon" and self.window:
                if self.window.get_visible():
                    self.set_tray_icon()
        return True  # stop signal propagation

    def on_game_start(self, game: Game) -> None:
        self._running_games.append(game)
        if self.window and settings.read_bool_setting("hide_client_on_game_start"):
            self.window.hide()  # Hide launcher window

    def on_game_stopped(self, game: Game) -> None:
        """Callback to quit Lutris is last game stops while the window is hidden."""
        running_game_ids = [g.id for g in self._running_games]
        if game.id in running_game_ids:
            logger.debug("Removing %s from running IDs", game.id)
            try:
                del self._running_games[running_game_ids.index(game.id)]
            except ValueError:
                pass
        elif running_game_ids:
            logger.warning("%s not in %s", game.id, running_game_ids)
        else:
            logger.debug("Game has already been removed from running IDs?")

        if self.window and settings.read_bool_setting("hide_client_on_game_start") and not self.quit_on_game_exit:
            self.window.show()  # Show launcher window
        else:
            self._quit_if_hidden_and_idle()

    def on_install_ended(self) -> None:
        self._quit_if_hidden_and_idle()

    def on_download_queue_completed(self, _widget: Gtk.Widget = None) -> None:
        self._quit_if_hidden_and_idle()

    def on_cloud_sync_ended(self, _operation: CloudSyncOperation) -> None:
        self._quit_if_hidden_and_idle()

    def _quit_if_hidden_and_idle(self) -> None:
        """Quits Lutris if the window is not visible and there is no ongoing activity
        (running games or active downloads) keeping it alive."""
        if not self.window or not self.window.is_visible():
            if not self.has_running_games and not self.has_active_downloads:
                if self.quit_on_game_exit or not self.has_tray_icon():
                    self.quit()

    @property
    def has_active_downloads(self) -> bool:
        """True if the download queue has active operations, or a game's saves are syncing."""
        if is_cloud_sync_running():
            return True
        if self.window:
            return not self.window.is_download_queue_empty
        return False

    @property
    def launch_ui_delegate(self) -> LaunchUIDelegate:
        """The delegate for launches that have no window of their own to use.
        This is the main window once it exists, whatever command line we got;
        choices made on the command line are passed to the launch they apply to
        instead. Before that, it provides no UI."""
        return self.window or LaunchUIDelegate()

    def get_running_games(self) -> list[Game]:
        # This method reflects games that have stopped even if the 'game-stopped' signal
        # has not been handled yet; that handler will still clean up the list though.
        return [g for g in self._running_games if g.state != g.STATE_STOPPED]

    @property
    def has_running_games(self) -> bool:
        return bool(self.get_running_games())

    def get_running_game_ids(self) -> list[str]:
        """Returns the ids of the games presently running."""
        return [game.id for game in self.get_running_games()]

    def is_game_running_by_id(self, game_id: str) -> bool:
        """True if the ID is the ID of a game that is running."""
        return bool(game_id and str(game_id) in self.get_running_game_ids())

    def get_game_by_id(self, game_id: str) -> Game:
        """Returns the game with the ID given; if it's running this is the running
        game instance, and if not it's a fresh copy off the database."""
        for game in self.get_running_games():
            if game.id == str(game_id):
                return game

        return Game(game_id)

    @staticmethod
    def get_lutris_action(url: GLib.Variant | None) -> "InstallerInfoDict | dict[str, None]":
        installer_info = {
            "game_slug": None,
            "revision": None,
            "action": None,
            "service": None,
            "appid": None,
            "launch_config_name": None,
        }

        if url:
            urls = url.get_strv()

            if urls:
                url_str = urls[0]
                installer_info = parse_installer_url(url_str)
        return installer_info

    def do_shutdown(self) -> None:  # pylint: disable=arguments-differ
        logger.info("Shutting down Lutris")
        if self.window:
            selected_category = "%s:%s" % self.window.selected_category
            settings.write_setting("selected_category", selected_category)
            self.window.destroy()
        Gtk.Application.do_shutdown(self)

    def set_tray_icon(self) -> None:
        """Creates or destroys a tray icon for the application"""
        active = settings.read_setting("show_tray_icon", default="false").lower() == "true"
        if active and not self.tray:
            self.tray = LutrisStatusIcon(application=self)
        if self.tray:
            self.tray.set_visible(active)

    def has_tray_icon(self) -> bool:
        return bool(self.tray and self.tray.is_visible())
