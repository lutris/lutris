import os
import subprocess
from threading import Thread

from lutris.util.log import logger


class ScriptThread():
    def __init__(self, runner):
        self.runner = runner

    def call_process_with_err(self, arg):
        """Handle subprocess errors in the new thread"""

        try:
            return subprocess.call(arg)

        except PermissionError:
            logger.error(
                "Unable to execute script , script is not executable")
        except OSError:
            logger.error(
                "Unable to execute script maybe its missing Shebang")

    def start(self):
        """Execute script in a new thread"""

        script = self.runner.system_config.get('pre_script')
        if os.path.isfile(script):
            self.pre_script_thread = Thread(target=self.call_process_with_err,
                                            args=[self.runner.system_config.get('pre_script')])

            self.pre_script_thread.start()
        else:
            logger.error(
                "Script not found at %s", script)
