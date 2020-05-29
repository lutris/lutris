# Standard Library
import sys

# Lutris Modules
from lutris.gui.dialogs import ErrorDialog
from lutris.util.log import logger


class ScriptingError(Exception):

    """Custom exception for scripting errors, can be caught by modifying
    excepthook."""

    def __init__(self, message, faulty_data=None):
        self.message = message
        self.faulty_data = faulty_data
        super(ScriptingError, self).__init__()
        logger.error(self.__str__())

    def __str__(self):
        faulty_data = repr(self.faulty_data)
        return self.message + "\n%s" % faulty_data if faulty_data else ""

    def __repr__(self):
        return self.message


class FileNotAvailable(Exception):

    """Raised when a file has to be provided by the user"""


class MissingGameDependency(Exception):

    """Raise when a game requires another game that isn't installed"""

    def __init__(self, slug=None):
        self.slug = slug
        super().__init__()


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
