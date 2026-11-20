"""The terminal a command line came from."""

import os

from gi.repository import Gio


class CommandOutput:
    """Talks to the terminal of the process that ran `lutris`. That's not this
    process when the command line was forwarded to the instance already running,
    so commands print, read and resolve relative paths through this instead.
    """

    def __init__(self, command_line: Gio.ApplicationCommandLine) -> None:
        self.command_line = command_line

    def print(self, text: str) -> None:
        """Print a line on the invoking process' standard output."""
        # Workaround broken pygobject bindings
        self.command_line.do_print_literal(self.command_line, text + "\n")  # type: ignore

    def print_error(self, text: str) -> None:
        """Print a line on the invoking process' standard error."""
        self.command_line.do_printerr_literal(self.command_line, text + "\n")  # type: ignore

    def ask_yes_or_no(self, question: str) -> bool:
        """Ask a question on the invoking process' terminal; anything but a yes is a no."""
        self.print("%s [Y/N]" % question)
        stdin = self.command_line.get_stdin()
        if not stdin:
            return False
        answer, _length = Gio.DataInputStream.new(stdin).read_line_utf8(None)
        return (answer or "").strip().lower() in ("y", "yes")

    def get_path(self, path: str) -> str:
        """Return a path from the command line as an absolute path; a relative one is
        relative to the invoking process' working directory, not this one's."""
        cwd = self.command_line.get_cwd()
        return os.path.abspath(os.path.join(cwd, path) if cwd else path)
