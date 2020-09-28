import os
from gettext import gettext as _

from lutris.util.log import logger


class default_path_handler:
    last_selected_path = {None: None}

    @staticmethod
    def IsValid(path):
        if not path:
            return path
        retVal = os.path.expanduser(path)
        if not os.path.exists(retVal):
            return None
        return retVal

    @staticmethod
    def GetDirectory(path):
        retVal = default_path_handler.IsValid(path)
        if retVal:
            if os.path.isfile(retVal):
                retVal = os.path.dirname(retVal)
        return retVal

    @classmethod
    def GetDefault(cls, entry=None, default=None, game_path=None, install_path=None, path_type=None):
        lsp = None
        if path_type in default_path_handler.last_selected_path:
            lsp = default_path_handler.last_selected_path[path_type]
        items = [
            entry,
            game_path,
            install_path,
            lsp,
            default_path_handler.last_selected_path[None],
            "~/Games",
            "~"]
        for item in items:
            checked_item = default_path_handler.IsValid(item)
            if checked_item:
                return checked_item
        logger.error(_("Could not find any default path"))
        return None

    @classmethod
    def SetLastSelectedPath(cls, selected_path, path_type=None):
        default_path_handler.last_selected_path[path_type] = default_path_handler.GetDirectory(selected_path)
        default_path_handler.last_selected_path[None] = default_path_handler.GetDirectory(selected_path)
