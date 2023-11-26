from typing import Callable

from gi.repository import GLib, Gtk, Pango

from lutris.util.log import logger


class ProgressBox(Gtk.Box):
    """Simple, small progress bar used to monitor the update of runtime or runner components.
    This class needs only a function that returns a Progress object, which describes the current
    progress and optionally can stop the update."""

    ProgressFunction = Callable[[], 'ProgressBox.Progress']

    def __init__(self,
                 progress_function: ProgressFunction,
                 **kwargs):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, no_show_all=True, spacing=6, **kwargs)

        self.progress_function = progress_function
        self.progress = ProgressBox.Progress(0.0)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, visible=True, spacing=6,
                       valign=Gtk.Align.CENTER)

        self.label = Gtk.Label("", visible=False,
                               wrap=True, ellipsize=Pango.EllipsizeMode.MIDDLE,
                               xalign=0)
        vbox.pack_start(self.label, False, False, 0)

        self.progressbar = Gtk.ProgressBar(pulse_step=0.4, visible=True)
        self.progressbar.set_valign(Gtk.Align.CENTER)
        vbox.pack_start(self.progressbar, False, False, 0)

        self.pack_start(vbox, True, True, 0)

        self.stop_button = Gtk.Button.new_from_icon_name("media-playback-stop-symbolic", Gtk.IconSize.BUTTON)
        self.stop_button.hide()
        self.stop_button.get_style_context().add_class("circular")
        self.stop_button.connect("clicked", self.on_stop_clicked)
        self.pack_start(self.stop_button, False, False, 0)

        self.timer_id = GLib.timeout_add(500, self.on_update_progress)
        self.connect("destroy", self.on_destroy)

    class Progress:
        """Contains the current state of the update being monitored. This can also provide
        for stopping the update via a function you can provide.

        Updates often cannot be stopped after a certain point; at that point they start
        providing Progress objects with no stop-function, and the stop button disappears."""

        def __init__(self, progress: float = None, label_markup: str = "", stop_function: Callable = None):
            self.progress = progress
            self.label_markup = label_markup
            self.stop_function = stop_function

        @property
        def can_stop(self) -> bool:
            """Called to check if the stop button should appear."""
            return bool(self.stop_function)

        def stop(self):
            """Called whe the stop button is clicked."""
            if self.stop_function:
                self.stop_function()

    def on_stop_clicked(self, _widget) -> None:
        if self.progress.can_stop:
            self.progress.stop()

    def on_destroy(self, _widget) -> None:
        if self.timer_id:
            GLib.source_remove(self.timer_id)

    def on_update_progress(self) -> bool:
        try:
            progress = self.progress_function()
        except Exception as ex:
            logger.exception("Unable to obtain a progress update: %s", ex)
            self.timer_id = None
            return False

        self._apply_progress(progress)
        return True

    def _apply_progress(self, progress: Progress):
        self.progress = progress

        if progress.progress is None:
            self.progressbar.pulse()
        else:
            self.progressbar.set_fraction(min(progress.progress, 1))
        self._set_label(progress.label_markup or "")
        self.stop_button.set_visible(progress.can_stop)

    def _set_label(self, markup: str) -> None:
        if markup:
            if markup != self.label.get_text():
                self.label.set_markup(markup)
            self.label.show()
        else:
            self.label.hide()
