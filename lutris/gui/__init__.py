"""Lutris GUI package: the GTK frontend"""

import gi

# Before anything in the frontend imports them
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("PangoCairo", "1.0")
