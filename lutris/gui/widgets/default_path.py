import os
from gettext import gettext as _

from lutris.util.log import logger


class default_path_handler:
    ANY_PT = "Any pathtype"
    last_selected_path = {ANY_PT: None}

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
    def get(cls, entry=None, default=None, main_file_path=None, install_path=None, path_type=None):
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
        """
        try:
            lsp_pt = default_path_handler.last_selected_path[path_type]
        except KeyError:
            lsp_pt = None
        try:
            lsp_any = default_path_handler.last_selected_path[default_path_handler.ANY_PT]
        except KeyError:
            lsp_any = None

        items = [
            entry,
            default,
            lsp_pt,
            cls.path_to_directory(main_file_path),
            lsp_any,
            install_path,
            "/home/bob/Games",
            "~"]

        # names = [
        #     "entry",
        #     "default",
        #     "lsp_pt",
        #     "main_file_path",
        #     "lsp_any",
        #     "install_path",
        #     "\"~/Games\"",
        #     "\"~\""]

        # for i in range(len(items)):
        #     try:
        #         print("{}=\"{}\"".format(names[i], os.path.expanduser(items[i])))
        #     except TypeError:
        #         print("{}=\"{}\"".format(names[i], items[i]))

        for item in items:
            if cls.is_valid(item):
                try:
                    return os.path.expanduser(item)
                except TypeError:
                    return item
        logger.error(_("Could not find any valid default path, including ~"))
        return None

    @ classmethod
    def set_selected(cls, selected_path, path_type=ANY_PT):
        """Sets the last user selected path for this path type or any if no path type is selected"""
        cls.last_selected_path[path_type or cls.ANY_PT] = cls.path_to_directory(selected_path)
