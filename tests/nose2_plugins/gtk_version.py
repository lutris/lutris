"""nose2 plugin that pins GTK/GDK versions before any test module is imported.

Without this, test modules that stub gi.repository or import lutris GUI code
can cause a different GTK version to load before gi.require_version runs,
breaking all subsequent GTK-dependent test imports.
"""

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
