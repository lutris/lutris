"""Installer specific exceptions"""

import sys
from gettext import gettext as _

from lutris.exceptions import LutrisError
from lutris.gui.dialogs import ErrorDialog
from lutris.util.log import logger
from lutris.util.strings import gtk_safe


class ScriptingError(LutrisError):
    """Custom exception for scripting errors, can be caught by modifying
    excepthook."""

    def __init__(self, message, message_markup=None, faulty_data=None):
        self.faulty_data = faulty_data
        super().__init__(message, message_markup=message_markup)
        logger.error(self.__str__())

    @staticmethod
    def wrap(error: BaseException) -> "ScriptingError":
        if isinstance(error, LutrisError):
            return ScriptingError(error.message, message_markup=error.message_markup)
        else:
            return ScriptingError(str(error))

    def __str__(self):
        if self.faulty_data is None:
            return self.message

        faulty_data = repr(self.faulty_data)
        if not faulty_data:
            return faulty_data

        return self.message + "\n%s" % faulty_data

    def __repr__(self):
        return self.message


class MissingGameDependencyError(LutrisError):
    """Raise when a game requires another game that isn't installed"""

    def __init__(self, *args, message=None, slug=None, **kwargs):
        self.slug = slug

        if not message:
            message = _("This game requires %s.") % slug
        super().__init__(message, *args, **kwargs)


_excepthook = sys.excepthook  # pylint: disable=invalid-name


def error_handler(error_type, value, traceback):
    """Intercept all possible exceptions and raise them as ScriptingErrors"""
    if error_type == ScriptingError:
        message = value.message
        if value.faulty_data:
            message += "\n<b>%s</b>" % gtk_safe(value.faulty_data)
        ErrorDialog(message)
    else:
        _excepthook(error_type, value, traceback)


sys.excepthook = error_handler
