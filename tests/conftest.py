"""Shared pytest setup.

Pin the GTK/GDK versions before any test module is imported: modules that stub
gi.repository or import lutris GUI code can otherwise load GTK 4 before
gi.require_version("Gtk", "3.0") runs, breaking every GTK 3 import after it.
"""

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
