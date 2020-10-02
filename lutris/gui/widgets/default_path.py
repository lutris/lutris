import os
from enum import Enum, auto
from gettext import gettext as _

from lutris.util.log import logger


class PATH_TYPE(Enum):
    """Types of paths, UNKNOWN should be used by default"""

    UNKNOWN = 0
    BANNER = auto()
    ICON = auto()
    CACHE = auto()
    INSTALLER = auto()
    INSTALL_TO = auto()


class default_path_handler:
    """Handles finding the correct path to set in the file chooser dialog"""

    last_selected_path = {PATH_TYPE.UNKNOWN: None}

    @staticmethod
    def is_valid(path):
        """Checks if a path is valid, returns False if it is not a path (None)
           or if it does not exist on the system"""

        try:
            fullpath = os.path.expanduser(path)
        except TypeError:
            return False
        else:
            return os.path.exists(fullpath)

    @staticmethod
    def path_to_directory(path):
        """Takes a path, with a possible file component and returns just the directory portion"""

        if default_path_handler.is_valid(path):
            if os.path.isfile(path):
                return os.path.dirname(path)
            return path
        return None

    @classmethod
    def get(cls, entry=None, default=None, main_file_path=None, install_path=None, path_type=PATH_TYPE.UNKNOWN):
        """Returns the default path to use, if this item has a type then that might be used

        First match wins
            entry: what the user has previously selected for this control
            default: control's defined default
            lsp_pt: last selected path for this path type
            main_file_path: the path to the game's main file
            lsp_any: last selected path for any path type (excludes opens by a widget with a path type)
            install_path: the path to install into
            ~/Games: Games directory
            ~: home directory

        Note:
            if the path type is INSTALL_TO, install_path will be the highest priority, even if entry
            is set
        """

        override = None
        if PATH_TYPE.INSTALL_TO == path_type:
            override = install_path

        try:
            lsp_pt = default_path_handler.last_selected_path[path_type]
        except KeyError:
            lsp_pt = None
        try:
            lsp_any = default_path_handler.last_selected_path[PATH_TYPE.UNKNOWN]
        except KeyError:
            lsp_any = None

        items = [
            override,
            entry,
            default,
            lsp_pt,
            cls.path_to_directory(main_file_path),
            lsp_any,
            install_path,
            "/home/bob/Games",
            "~"]

        for item in items:
            if cls.is_valid(item):
                try:
                    return os.path.expanduser(item)
                except TypeError:
                    return item
        logger.error(_("Could not find any valid default path, including ~"))
        return None

    @ classmethod
    def set_selected(cls, selected_path, path_type=PATH_TYPE.UNKNOWN):
        """Sets the last user selected path for this path type or any if no path type is selected"""

        cls.last_selected_path[path_type or PATH_TYPE.UNKNOWN] = cls.path_to_directory(selected_path)
