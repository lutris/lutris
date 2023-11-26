from typing import Callable, Tuple

from gi.repository import GLib, Gtk, Pango

from lutris.gui.dialogs import ErrorDialog


class ProgressBox(Gtk.Box):
    """Simple, small progress bar used to monitor the update of runtime or runner components.
    This class needs only a function that returns the current progress, as a tuple of progress (0->1)
    and markup to display in a label. When the progress number is None, the progress is done and
    this box will destroy itself."""

    ProgressFunction = Callable[[], Tuple[float, str]]

    def __init__(self, progress_function: ProgressFunction, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, no_show_all=True, spacing=6, **kwargs)

        self.progress_function = progress_function

        self.label = Gtk.Label("", visible=False,
                               wrap=True, ellipsize=Pango.EllipsizeMode.MIDDLE,
                               xalign=0)
        self.pack_start(self.label, False, False, 0)

        self.progressbar = Gtk.ProgressBar(visible=True)
        self.pack_start(self.progressbar, False, False, 0)

        self.timer_id = GLib.timeout_add(500, self.on_update_progress)
        self.connect("destroy", self.on_destroy)

    def on_destroy(self, _widget):
        if self.timer_id:
            GLib.source_remove(self.timer_id)

    def on_update_progress(self) -> bool:
        try:
            progress, progress_text = self.progress_function()
        except Exception as ex:
            ErrorDialog(ex, parent=self.get_toplevel())
            self.timer_id = None
            self.destroy()
            return False

        self.progressbar.set_fraction(min(progress, 1))
        self._set_label(progress_text or "")
        return True

    def _set_label(self, markup: str) -> None:
        if markup:
            if markup != self.label.get_text():
                self.label.set_markup(markup)
            self.label.show()
        else:
            self.label.hide()
