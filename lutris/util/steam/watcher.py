"""Steam game library watcher"""
# pylint: disable=too-few-public-methods
from gi.repository import GLib, Gio
from lutris.util.log import logger


class SteamWatcher:
    """Watches a Steam library folder and notify changes"""
    def __init__(self, steamapps_paths, callback=None):
        self.monitors = []
        self.callback = callback
        for steam_path in steamapps_paths:
            path = Gio.File.new_for_path(steam_path)
            try:
                monitor = path.monitor_directory(Gio.FileMonitorFlags.NONE)
                logger.debug("Watching Steam folder %s", steam_path)
                monitor.connect("changed", self._on_directory_changed)
                self.monitors.append(monitor)
            except GLib.Error as ex:
                logger.exception(ex)

    def _on_directory_changed(self, _monitor, _file, _other_file, event_type):
        path = _file.get_path()
        if not path.endswith(".acf"):
            return
        self.callback(event_type, path)
