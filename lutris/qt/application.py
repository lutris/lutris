"""The Qt frontend's application.

Like the GTK frontend's, it's a Gio.Application with Lutris' id, so that Lutris
runs once and command lines reach whichever instance runs. It drives Qt too:
PySide6's Qt dispatches its events through GLib's main loop, which
Gio.Application.run() runs, with asyncio on it (see lutris.util.mainloop).
"""

import os
import signal
import sys
from gettext import gettext as _
from types import TracebackType

from gi.repository import Gio, GLib
from PySide6.QtWidgets import QApplication

from lutris import settings
from lutris.backend import events
from lutris.backend.models import GameInfo
from lutris.cli.commands import handle_command_line, start_lutris
from lutris.cli.options import add_options, is_text_command
from lutris.cli.output import CommandOutput
from lutris.delegates import LaunchUIDelegate
from lutris.qt.display_backend import QtDisplayBackend
from lutris.qt.main_window import MainWindow
from lutris.qt.tasks import show_error
from lutris.util.display_backend import set_display_backend

# Options that need a part of the GUI the Qt frontend doesn't have yet
_UNSUPPORTED_OPTIONS = ("install", "reinstall", "submit-issue", GLib.OPTION_REMAINING)


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
        # The games holding the application while they run, even with the window closed
        self._running_game_ids: set[str] = set()

    def do_startup(self) -> None:
        Gio.Application.do_startup(self)
        # Only the primary instance shows anything, so only it needs Qt
        self.qt_application = QApplication([sys.argv[0]])
        self.qt_application.setApplicationName("Lutris")
        self.qt_application.setDesktopFileName(settings.APPLICATION_ID)
        set_display_backend(QtDisplayBackend())
        self._install_exception_backstop()
        events.GAME_LAUNCHING.register(self.on_game_launching)
        events.GAME_STOPPED.register(self.on_game_stopped)
        # PyGObject's own Ctrl+C handling doesn't get a chance while Qt waits in GLib
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self.on_interrupt)

    def do_shutdown(self) -> None:
        # Quitting (on Ctrl+C, say) leaves the window open otherwise
        if self.window:
            self.window.close()
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
            output.print_error(_("The Qt version of Lutris can only show the library so far."))
        self.show_window()
        return 0

    def _install_exception_backstop(self) -> None:
        """Show the errors that escape Qt's slots, which PySide6 passes to sys.excepthook,
        rather than only printing them."""
        original_excepthook = sys.excepthook

        def excepthook(error_type: type[BaseException], error: BaseException, traceback: TracebackType | None) -> None:
            original_excepthook(error_type, error, traceback)
            if isinstance(error, Exception):
                show_error(error, self.window)

        sys.excepthook = excepthook

    def on_interrupt(self) -> bool:
        """Quit on Ctrl+C."""
        self.quit()
        return GLib.SOURCE_REMOVE

    def show_window(self) -> None:
        if not self.window:
            self.window = MainWindow()
            self.window.closed.connect(self.on_window_closed)
            self.hold()
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def on_window_closed(self) -> None:
        self.window = None
        self.release()

    def on_game_launching(self, game: GameInfo) -> None:
        if game.id not in self._running_game_ids:
            self._running_game_ids.add(game.id)
            self.hold()

    def on_game_stopped(self, game: GameInfo) -> None:
        if game.id in self._running_game_ids:
            self._running_game_ids.discard(game.id)
            self.release()
