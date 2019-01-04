"""Various utilities using the GObject framework"""
from gi.repository import Gtk, Gdk
from lutris.util.system import reset_library_preloads


def open_uri(uri):
    """Opens a local or remote URI with the default application"""
    reset_library_preloads()
    Gtk.show_uri(None, uri, Gdk.CURRENT_TIME)
