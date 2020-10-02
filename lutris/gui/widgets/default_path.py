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
        """`is_valid` Checks if the path is valid

        Args:
        - `path` (`str`): Path to check, can be `None`

        Returns:
        - `bool`: `True` if the string is a path and it exists on the system
        """

        try:
            fullpath = os.path.expanduser(path)
        except TypeError:
            return False
        else:
            return os.path.exists(fullpath)

    @staticmethod
    def path_to_directory(path):
        """`path_to_directory` looks for a file component to the path and removes it

        Args:
        - `path` (`str`): A path that can point to a directory or file

        Returns:
        - `str`: The specified path with the file component removed, or `None` if the path is invalid
        """

        if default_path_handler.is_valid(path):
            if os.path.isfile(path):
                return os.path.dirname(path)
            return path
        return None

    @classmethod
    def get(cls, entry=None, default=None, main_file_path=None, install_path=None, path_type=PATH_TYPE.UNKNOWN):
        """`get` Returns the path to use for a GTK dialog

        First match wins:
        - entry: what the user has previously selected for this control
        - default: control's defined default
        - lsp_pt: last selected path for this path type
        - main_file_path: the path to the game's main file
        - lsp_any: last selected path for any path type (excludes opens by a widget with a path type)
        - install_path: the path to install into
        - ~/Games: Games directory
        - ~: home directory

        Notes:
        - The path type can be used to classify the type of path to look for (e.g. installation path)

        Args:
        - `entry` (`str`, optional): What is in the text entry box if it exists. Defaults to `None`.
        - `default` (`str`, optional): What is the default for this kind of control. Defaults to `None`.
        - `main_file_path` (`str`, optional): The path to the game's main file. Defaults to `None`.
        - `install_path` (`str`, optional): Where we should install games. Defaults to `None`.
        - `path_type` (`PATH_TYPE`, optional): Type of path to use. Defaults to `PATH_TYPE.UNKNOWN`.

        Returns:
        - `str`: Path that should be used
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
        """`set_selected` Sets the last user selected path for this path type

        Args:
        - `selected_path` (`str`): path the user selected
        - `path_type` (`PATH_TYPE`, optional): Set if this widget belongs to a particular group.
         Defaults to `PATH_TYPE.UNKNOWN`.
        """

        cls.last_selected_path[path_type or PATH_TYPE.UNKNOWN] = cls.path_to_directory(selected_path)
