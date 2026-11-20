"""The command-line frontend's application, which every `lutris` command starts with.

It's a Gio.Application with the same id as the GTK frontend's, so that Lutris runs
once: a command line that names a command needing no GUI is forwarded to the
instance already running, whatever its frontend, or run here, with no GUI toolkit
loaded, when there's none. Any other command line needs a GUI, so this hands it
to a GUI frontend before registering (see needs_frontend).
"""

import os
import sys
from gettext import gettext as _

from gi.repository import Gio, GLib

from lutris import settings
from lutris.cli.commands import run_text_command, start_lutris
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
        output = CommandOutput(command_line)
        options = command_line.get_options_dict()
        if not is_text_command(options):
            # Another `lutris` wants the GUI while this instance runs a command
            output.print_error(_("Lutris is busy running a command; try again once it has finished."))
            return 1
        start_lutris(options, run_checks_async=False)
        status = run_text_command(options, output, LaunchUIDelegate())
        return status or 0
