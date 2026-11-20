"""The Qt frontend's application.

It uses Gio.Application with Lutris' id so that Lutris runs once and command
lines reach the primary instance. It drives Qt too:
PySide6's Qt dispatches its events through GLib's main loop, which
Gio.Application.run() runs, with asyncio on it (see lutris.util.mainloop).
"""

import asyncio
import os
import signal
import sys
from gettext import gettext as _
from types import TracebackType

from gi.repository import Gio, GLib
from PySide6.QtGui import QIcon, QWindow
from PySide6.QtWidgets import QApplication

from lutris import settings
from lutris.backend import cloud_saves, events, games, installers, runtime_updates
from lutris.backend.errors import LutrisError
from lutris.backend.models import GameInfo
from lutris.cli.commands import INTERRUPTED_STATUS, handle_command_line, start_lutris
from lutris.cli.options import add_options, is_text_command
from lutris.cli.output import CommandOutput
from lutris.delegates import LaunchUIDelegate
from lutris.qt.display_backend import QtDisplayBackend
from lutris.qt.main_window import MainWindow
from lutris.qt.translations import QmlTranslator
from lutris.qt.tray import TrayIcon
from lutris.util import datapath
from lutris.util.display_backend import set_display_backend
from lutris.util.log import logger


class QtLutrisApplication(Gio.Application):
    """Shows the library in a Qt window, and runs the commands forwarded to it."""

    def __init__(self) -> None:
        super().__init__(application_id=settings.APPLICATION_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        # The command-line frontend's application came first, and hands over to this one
        self.set_default()
        add_options(self)
        GLib.set_application_name(_("Lutris"))
        self.qt_application: QApplication | None = None
        self.window: MainWindow | None = None
        self.tray: TrayIcon | None = None
        self._tray_held = False
        self._window_held = False
        self._minimized_for_game = False
        self._local_launch_status: int | None = None
        # The games holding the application while they run, even with the window closed
        self._running_game_ids: set[str] = set()

    def run(self, argv: list[str] | None = None) -> int:
        status = super().run(argv)
        return status if self._local_launch_status is None else self._local_launch_status

    def do_startup(self) -> None:
        Gio.Application.do_startup(self)
        # Only the primary instance shows anything, so only it needs Qt
        self.qt_application = QApplication([sys.argv[0]])
        self.qt_application.setQuitOnLastWindowClosed(False)
        self.qt_application.setApplicationName("Lutris")
        self.qt_application.setDesktopFileName(settings.APPLICATION_ID)
        icon = QIcon(os.path.join(datapath.get(), "media", "default_icon.png"))
        self.qt_application.setWindowIcon(QIcon.fromTheme(settings.APPLICATION_ID, icon))
        self.qt_application.installTranslator(QmlTranslator(self.qt_application))
        set_display_backend(QtDisplayBackend())
        self._install_exception_backstop()
        events.GAME_LAUNCHING.register(self.on_game_launching)
        events.GAME_STARTED.register(self.on_game_started)
        events.GAME_STOPPED.register(self.on_game_stopped)
        # PyGObject's own Ctrl+C handling doesn't get a chance while Qt waits in GLib
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self.on_interrupt)

    def do_shutdown(self) -> None:
        if self.tray:
            self.tray.shutdown()
        # Quitting (on Ctrl+C, say) leaves the window open otherwise
        if self.window:
            self.window.shutdown()
        Gio.Application.do_shutdown(self)

    def do_command_line(self, command_line: Gio.ApplicationCommandLine) -> int:
        output = CommandOutput(command_line)
        if os.geteuid() == 0:
            output.print_error(_("Do not run Lutris as root."))
            return 2
        options = command_line.get_options_dict()
        arguments = [arg for arg in command_line.get_arguments()[1:] if arg not in ("-d", "--debug")]
        start_lutris(options, run_checks_async=not arguments)

        if is_text_command(options):
            # Forwarded by the command-line frontend; it reports its own status when done
            self.create_asyncio_task(handle_command_line(command_line, LaunchUIDelegate()))
            return 0

        force = options.contains("force")
        if remaining := options.lookup_value(GLib.OPTION_REMAINING):
            uris = remaining.get_strv()
            if len(uris) != 1:
                output.print_error(_("Supply one Lutris launch URI."))
                return 1
            self.create_asyncio_task(self._launch_from_uri(command_line, uris[0], force=force))
            return 0
        try:
            self.show_window(force=force)
            if self.window and options.contains("submit-issue"):
                self.window.controller.preferences_controller.open_issue_report()
        except RuntimeError as error:
            output.print_error(str(error))
            return 1
        return 0

    async def _launch_from_uri(
        self, command_line: Gio.ApplicationCommandLine, uri: str, *, force: bool = False
    ) -> None:
        status = 1
        output = CommandOutput(command_line)
        try:
            if target := installers.get_store_install_target(uri):
                self.show_window(force=force)
                if self.window:
                    await self.window.controller.open_store_install(*target)
            else:
                if self.window:
                    await self.window.controller.runtime_updates_controller.wait_for_update()
                if force:
                    await runtime_updates.update_runtime(force=True)
                game_id = await games.launch_from_uri(uri)
                # The launch event runs at idle, after this command releases its application hold
                self._hold_for_game(game_id)
            status = 0
        except asyncio.CancelledError:
            status = INTERRUPTED_STATUS
            raise
        except LutrisError as error:
            output.print_error(error.message)
        except Exception as error:
            logger.exception("Shortcut launch failed: %s", error)
            output.print_error(str(error))
        finally:
            if not command_line.get_is_remote():
                self._local_launch_status = status
            command_line.set_exit_status(status)
            command_line.done()

    def _install_exception_backstop(self) -> None:
        """Show the errors that escape Qt's slots, which PySide6 passes to sys.excepthook,
        rather than only printing them."""
        original_excepthook = sys.excepthook

        def excepthook(error_type: type[BaseException], error: BaseException, traceback: TracebackType | None) -> None:
            original_excepthook(error_type, error, traceback)
            if isinstance(error, Exception) and self.window:
                self.window.prompts.error(error)

        sys.excepthook = excepthook

    def on_interrupt(self) -> bool:
        """Quit on Ctrl+C."""
        self.quit()
        return GLib.SOURCE_REMOVE

    def show_window(self, *, force: bool = False) -> None:
        if not self.window:
            self.window = MainWindow()
            self.window.engine.quit.connect(lambda: self.quit())
            self.window.window.visibleChanged.connect(self.on_window_visibility_changed)
            self.tray = TrayIcon(
                self.window.controller.preferences_controller,
                self.show_window,
                self.quit,
                self._set_tray_held,
                self.window,
            )
            # Fill in artwork the library is missing, without a word unless some arrives
            self.window.controller.update_artwork(quiet=True)
            # Keep umu and the rest of the runtime current, if the last check is stale
            self.window.controller.runtime_updates_controller.update(force=force)
        elif force:
            self.window.controller.runtime_updates_controller.check()
        self.window.show()

    def _set_tray_held(self, held: bool) -> None:
        if held == self._tray_held:
            return
        self._tray_held = held
        if held:
            self.hold()
        else:
            self.release()

    def on_window_visibility_changed(self) -> None:
        visible = bool(self.window and self.window.window.isVisible())
        if visible and not self._window_held:
            self._window_held = True
            self.hold()
        elif not visible and self._window_held:
            self._window_held = False
            if self.window:
                self.window.prompts.dismiss()
            self.release()

    def on_game_launching(self, game: GameInfo) -> None:
        self._hold_for_game(game.id)

    def on_game_started(self, _game: GameInfo) -> None:
        if self.window and self.window.window.isExposed() and settings.read_bool_setting("hide_client_on_game_start"):
            self.window.window.showMinimized()
            self._minimized_for_game = True

    def _hold_for_game(self, game_id: str) -> None:
        if game_id not in self._running_game_ids:
            self._running_game_ids.add(game_id)
            self.hold()

    def on_game_stopped(self, game: GameInfo) -> None:
        if game.id in self._running_game_ids:
            self._running_game_ids.discard(game.id)
            self.create_asyncio_task(self._release_when_saves_finish(game.id))
        if self._minimized_for_game and not self._running_game_ids:
            self._minimized_for_game = False
            if self.window and self.window.window.visibility() == QWindow.Visibility.Minimized:
                self.window.window.showNormal()

    async def _release_when_saves_finish(self, game_id: str) -> None:
        signal = asyncio.Event()
        registration = cloud_saves.CLOUD_SAVE_ENDED.register(
            lambda transfer_id: signal.set() if transfer_id == f"{game_id}:post-exit" else None
        )
        try:
            if any(transfer.id == f"{game_id}:post-exit" for transfer in await cloud_saves.list_transfers()):
                await signal.wait()
        finally:
            registration.unregister()
            self.release()
