import os
import subprocess
from threading import Thread

from lutris.util.log import logger
from lutris.gui import dialogs


class ScriptThread(Thread):
    """Execute a given script in a new thread and handle the exceptions that might occur"""

    def __init__(self, script):
        super().__init__(target=self.call_process_with_err,
                         args=[script])
        self.script = script

    def call_process_with_err(self, arg):
        """Handle subprocess errors in the new thread"""

        try:
            return subprocess.call(arg)

        except PermissionError:
            error = "Unable to execute " + arg + ", script is not executable"
            logger.error(error)
            dialogs.ErrorDialog(error)
        except OSError:
            error = "Unable to execute " + arg + ", script maybe missing Shebang"
            logger.error(error)
            dialogs.ErrorDialog(error)

    def start(self):
        """Execute script in a new thread"""

        if self.script is None or not os.path.isfile(self.script):
            error = "Script not found"
            logger.error(error)
            dialogs.ErrorDialog(error)

        else:
            super().start()
