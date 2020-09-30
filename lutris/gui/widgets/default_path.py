import os
from gettext import gettext as _

from lutris.util.log import logger


class default_path_handler:
    last_selected_path = {None: None}

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
        retVal = default_path_handler.is_valid(path)
        if retVal:
            if os.path.isfile(retVal):
                retVal = os.path.dirname(retVal)
        return retVal

    @classmethod
    def get(cls, entry=None, default=None, game_path=None, install_path=None, path_type="Any"):
        """Returns the default path to use, if this item has a type then that might be used

        First match wins
            entry: what the user has previously selected for this control
            default: control's defined default
            game_path: the path to the game's executable
            install_path: the path to the game's working directory
            lsp_pt: last selected path for this path type
            lsp_any: last selected path for any path type
            ~/Games: Games directory
            ~: home directory
        """
        try:
            lsp_pt = default_path_handler.last_selected_path[path_type]
        except KeyError:
            lsp_pt = None
        try:
            lsp_any = default_path_handler.last_selected_path["any"]
        except KeyError:
            lsp_any = None

        items = [
            entry,
            default,
            game_path,
            install_path,
            lsp_pt,
            lsp_any,
            "~/Games",
            "~"]
        for item in items:
            if cls.is_valid(item):
                return item
        logger.error(_("Could not find any valid default path, including ~"))
        return None

    @classmethod
    def set_selected(cls, selected_path, path_type="Any"):
        """Sets the last user selected path for this path type or any if no path type is selected"""
        default_path_handler.last_selected_path[path_type] = default_path_handler.path_to_directory(selected_path)
