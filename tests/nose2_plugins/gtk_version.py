"""nose2 plugin that pins GTK/GDK versions before any test module is imported.

Without this, test modules that stub gi.repository or import lutris GUI code
can cause GTK 4.0 to load before gi.require_version("Gtk", "3.0") runs,
breaking all subsequent GTK3-dependent test imports.
"""

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
