import os
import subprocess
from threading import Thread

from lutris.util.log import logger


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
            logger.error(
                "Unable to execute %s, script is not executable", arg)
        except OSError:
            logger.error(
                "Unable to execute %s, script maybe missing Shebang", arg)

    def start(self):
        """Execute script in a new thread"""

        if self.script is None or not os.path.isfile(self.script):
            error = "Script not found"
            logger.error(error)

        else:
            super().start()
