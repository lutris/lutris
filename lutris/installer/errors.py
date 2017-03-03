import sys

from lutris.util.log import logger
from lutris.gui.dialogs import ErrorDialog


class ScriptingError(Exception):
    """Custom exception for scripting errors, can be caught by modifying
    excepthook."""
    def __init__(self, message, faulty_data=None):
        self.message = message
        self.faulty_data = faulty_data
        logger.error(self.message + repr(self.faulty_data))
        super(ScriptingError, self).__init__()

    def __str__(self):
        return self.message + "\n" + repr(self.faulty_data)

    def __repr__(self):
        return self.message


_excepthook = sys.excepthook


def error_handler(error_type, value, traceback):
    if error_type == ScriptingError:
        message = value.message
        if value.faulty_data:
            message += "\n<b>" + str(value.faulty_data) + "</b>"
        ErrorDialog(message)
    else:
        _excepthook(error_type, value, traceback)


sys.excepthook = error_handler
