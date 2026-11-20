"""The Qt frontend's application.

Like the GTK frontend's, it's a Gio.Application with Lutris' id, so that Lutris
runs once and command lines reach whichever instance runs. It drives Qt too:
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
from PySide6.QtGui import QGuiApplication

from lutris import settings
from lutris.backend import events, games
from lutris.backend.errors import LutrisError
from lutris.backend.models import GameInfo
from lutris.cli.commands import INTERRUPTED_STATUS, handle_command_line, start_lutris
from lutris.cli.options import add_options, is_text_command
from lutris.cli.output import CommandOutput
from lutris.delegates import LaunchUIDelegate
from lutris.qt.display_backend import QtDisplayBackend
from lutris.qt.main_window import MainWindow
from lutris.qt.translations import QmlTranslator
from lutris.util.display_backend import set_display_backend
from lutris.util.log import logger

# Options that need a part of the GUI the Qt frontend doesn't have yet
_UNSUPPORTED_OPTIONS = ("install", "reinstall", "submit-issue")


class QtLutrisApplication(Gio.Application):
    """Shows the library in a Qt window, and runs the commands forwarded to it."""

    def __init__(self) -> None:
        super().__init__(application_id=settings.APPLICATION_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        # The command-line frontend's application came first, and hands over to this one
        self.set_default()
        add_options(self)
        GLib.set_application_name(_("Lutris"))
        self.qt_application: QGuiApplication | None = None
        self.window: MainWindow | None = None
        self._window_held = False
        self._local_launch_status: int | None = None
        # The games holding the application while they run, even with the window closed
        self._running_game_ids: set[str] = set()

    def run(self, argv: list[str] | None = None) -> int:
        status = super().run(argv)
        return status if self._local_launch_status is None else self._local_launch_status

    def do_startup(self) -> None:
        Gio.Application.do_startup(self)
        # Only the primary instance shows anything, so only it needs Qt
        self.qt_application = QGuiApplication([sys.argv[0]])
        self.qt_application.setQuitOnLastWindowClosed(False)
        self.qt_application.setApplicationName("Lutris")
        self.qt_application.setDesktopFileName(settings.APPLICATION_ID)
        self.qt_application.installTranslator(QmlTranslator(self.qt_application))
        set_display_backend(QtDisplayBackend())
        self._install_exception_backstop()
        events.GAME_LAUNCHING.register(self.on_game_launching)
        events.GAME_STOPPED.register(self.on_game_stopped)
        # PyGObject's own Ctrl+C handling doesn't get a chance while Qt waits in GLib
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self.on_interrupt)

    def do_shutdown(self) -> None:
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

        if any(options.contains(name) for name in _UNSUPPORTED_OPTIONS):
            output.print_error(_("This command is not available in the Qt version of Lutris yet."))
            return 1
        if remaining := options.lookup_value(GLib.OPTION_REMAINING):
            uris = remaining.get_strv()
            if len(uris) != 1:
                output.print_error(_("Supply one Lutris launch URI."))
                return 1
            self.create_asyncio_task(self._launch_from_uri(command_line, uris[0]))
            return 0
        try:
            self.show_window()
        except RuntimeError as error:
            output.print_error(str(error))
            return 1
        return 0

    async def _launch_from_uri(self, command_line: Gio.ApplicationCommandLine, uri: str) -> None:
        status = 1
        output = CommandOutput(command_line)
        try:
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

    def show_window(self) -> None:
        if not self.window:
            self.window = MainWindow()
            self.window.window.visibleChanged.connect(self.on_window_visibility_changed)
            # Fill in artwork the library is missing, without a word unless some arrives
            self.window.controller.update_artwork(quiet=True)
            # Keep umu and the rest of the runtime current, if the last check is stale
            self.window.controller.runtime_updates_controller.update()
        self.window.show()

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

    def _hold_for_game(self, game_id: str) -> None:
        if game_id not in self._running_game_ids:
            self._running_game_ids.add(game_id)
            self.hold()

    def on_game_stopped(self, game: GameInfo) -> None:
        if game.id in self._running_game_ids:
            self._running_game_ids.discard(game.id)
            self.release()
