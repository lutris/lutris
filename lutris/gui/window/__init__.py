"""Components that make up the main Lutris window.

The window itself stays a ``Gtk.ApplicationWindow`` template; the pieces that can be separated
from it live here. ``GameViewManager`` owns the view/store lifecycle as a plain object, and the
mixin modules group the notification and window-state signals.
"""
