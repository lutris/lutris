"""Main Lutris package"""

from lutris.version import read_version

# Canonical value in pyproject.toml; bump it with `uv version --bump ...`
__version__ = read_version()

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
