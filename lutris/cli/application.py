"""The command-line frontend's application, which every `lutris` command starts with.

It's a Gio.Application with the same id as the Qt frontend's, so that Lutris runs
once: a command line that names a command needing no GUI is forwarded to the
instance already running, whatever its frontend, or run here, with no GUI toolkit
loaded, when there's none. Any other command line needs a GUI, so this hands it
to a GUI frontend before registering (see needs_frontend).
"""

import asyncio
import os
import signal
import sys
from gettext import gettext as _

from gi.repository import Gio, GLib

from lutris import settings
from lutris.cli.commands import INTERRUPTED_STATUS, handle_command_line, start_lutris
from lutris.cli.options import add_options, is_text_command
from lutris.cli.output import CommandOutput
from lutris.delegates import LaunchUIDelegate
from lutris.util.log import logger


class CommandLineApplication(Gio.Application):
    """Runs the commands that need no GUI."""

    def __init__(self) -> None:
        super().__init__(application_id=settings.APPLICATION_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        add_options(self)
        # Set when the command line needs a GUI frontend; run() then returns without
        # doing anything, and the caller runs the frontend with the same command line
        self.needs_frontend = False
        self._commands: set[asyncio.Task[int]] = set()
        # GLib reports success for the command line this process received from
        # itself whenever a command held the application, so run() reports this
        self._local_exit_status: int | None = None

    def run(self, argv: list[str] | None = None) -> int:  # type: ignore[override]
        status = super().run(argv)
        return status if self._local_exit_status is None else self._local_exit_status

    def do_startup(self) -> None:
        Gio.Application.do_startup(self)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self.on_interrupt)

    def do_handle_local_options(self, options: GLib.VariantDict) -> int:
        if options.contains("version"):
            print("%s-%s" % (os.path.basename(sys.argv[0]), settings.VERSION))
            return 0
        if not is_text_command(options):
            # Before registering, so that the frontend can register instead
            self.needs_frontend = True
            return 0
        if os.geteuid() == 0:
            logger.error("Do not run Lutris as root.")
            return 2
        return -1  # Register, and run the command here or forward it

    def do_command_line(self, command_line: Gio.ApplicationCommandLine) -> int:
        options = command_line.get_options_dict()
        if not is_text_command(options):
            # Another `lutris` wants the GUI while this instance runs a command
            CommandOutput(command_line).print_error(
                _("Lutris is busy running a command; try again once it has finished.")
            )
            return 1
        start_lutris(options, run_checks_async=False)
        task = self.create_asyncio_task(self.run_command(command_line))
        self._commands.add(task)
        task.add_done_callback(self._commands.discard)
        return 0  # The command reports its own status when it finishes

    async def run_command(self, command_line: Gio.ApplicationCommandLine) -> int:
        status = INTERRUPTED_STATUS  # Unless the command finishes
        try:
            status = await handle_command_line(command_line, LaunchUIDelegate())
            return status
        finally:
            if not command_line.get_is_remote():
                self._local_exit_status = status

    def on_interrupt(self) -> bool:
        """Stop the running commands on Ctrl+C."""
        if not self._commands:
            self.quit()
        for task in self._commands:
            task.cancel()
        return GLib.SOURCE_CONTINUE
