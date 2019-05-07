"""Unused handler registration but since someone reports problems with URL
integration once in a while, it could prove itself useful."""
import os
import sys

from gi.repository import Gio

from lutris.util.log import logger


def register_url_handler():
    """Register the lutris: protocol to open with the application."""
    executable = os.path.abspath(sys.argv[0])
    base_key = "desktop.gnome.url-handlers.lutris"
    schema_directory = "/usr/share/glib-2.0/schemas/"
    schema_source = Gio.SettingsSchemaSource.new_from_directory(
        schema_directory, None, True
    )
    schema = schema_source.lookup(base_key, True)
    if schema:
        settings = Gio.Settings.new(base_key)
        settings.set_string("command", executable)
    else:
        logger.warning("Schema not installed, cannot register url-handler")
