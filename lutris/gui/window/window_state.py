"""Window geometry and visibility handling for the main window.

Saving and restoring the size, position and maximized state, and the tray/close behaviour on
the window's own signals, grouped into a mixin.
"""

from lutris import settings
from lutris.gui.widgets.gi_composites import GtkTemplate


class WindowStateMixin:
    """Keeps the window's stored size, position and visibility state up to date."""

    def save_window_state(self):
        """Saves the window's size position and state as settings."""
        width, height = self.window_size
        settings.write_setting("width", width)
        settings.write_setting("height", height)
        if self.window_x and self.window_y:
            settings.write_setting("window_x", self.window_x)
            settings.write_setting("window_y", self.window_y)
        settings.write_setting("maximized", self.maximized)

    def restore_window_position(self):
        """Restores the window position only; we call this when showing
        the window, but restore the other settings only when creating it."""
        self.window_x = settings.read_setting("window_x")
        self.window_y = settings.read_setting("window_y")
        if self.window_x and self.window_y:
            self.move(int(self.window_x), int(self.window_y))

    @GtkTemplate.Callback
    def on_resize(self, widget, *_args):
        """Size-allocate signal.
        Updates stored window size and maximized state.
        """
        if not widget.get_window():
            return
        self.maximized = widget.is_maximized()
        size = widget.get_size()
        if not self.maximized:
            self.window_size = size
        self.search_entry.set_size_request(min(max(50, size[0] - 470), 800), -1)

    def on_window_delete(self, *_args):
        app = self.application
        if app.has_running_games:
            self.hide()
            return True
        if not self.is_download_queue_empty:
            self.hide()
            return True
        if app.has_tray_icon():
            self.hide()
            return True
        return None

    def on_visible_changed(self, window, param):
        if self.application.tray:
            self.application.tray.update_present_menu()

    def on_window_configure(self, *_args):
        """Callback triggered when the window is moved, resized..."""
        self.window_x, self.window_y = self.get_position()

    @GtkTemplate.Callback
    def on_destroy(self, *_args):
        """Signal for window close."""
        # Stop cancellable running threads
        for stopper in self.threads_stoppers:
            stopper()

    @GtkTemplate.Callback
    def on_hide(self, *_args):
        self.save_window_state()

    @GtkTemplate.Callback
    def on_show(self, *_args):
        self.restore_window_position()
