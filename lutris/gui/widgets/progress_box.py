from typing import Callable, Optional

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

from lutris.util.jobs import schedule_repeating_at_idle
from lutris.util.log import logger


class ProgressInfo:
    """Contains the current state of a process being monitored. This can also provide
    for stopping the process via a function you can provide.

    Processes sometimes cannot be stopped after a certain point; at that point they start
    providing Progress objects with no stop-function."""

    def __init__(self, progress: float = 0, label_markup: str = "", stop_function: Optional[Callable] = None):
        self.progress = progress
        self.label_markup = label_markup
        self.stop_function = stop_function
        self.has_ended = False

    @classmethod
    def ended(cls, label_markup: str = "") -> "ProgressInfo":
        """Creates a ProgressInfo whose has_ended flag is set, to indicate that
        the monitored process is over."""
        info = cls(1.0, label_markup=label_markup)
        info.has_ended = True
        return info

    @property
    def can_stop(self) -> bool:
        """Called to check if the stop button should appear."""
        return bool(self.stop_function)

    def stop(self):
        """Called whe the stop button is clicked."""
        if self.stop_function:
            try:
                self.stop_function()
            except Exception as ex:
                logger.exception("Error during progress box stop: %s", ex)


class ProgressBox(Gtk.Box):
    """Simple, small progress bar used to monitor the update of runtime or runner components.
    This class needs only a function that returns a Progress object, which describes the current
    progress and optionally can stop the update."""

    ProgressFunction = Callable[[], "ProgressInfo"]

    def __init__(self, progress_function: ProgressFunction, **kwargs):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, no_show_all=True, spacing=6, **kwargs)

        self.progress_function = progress_function
        self.progress = ProgressInfo(0.0)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, visible=True, spacing=6, valign=Gtk.Align.CENTER)

        self.label = Gtk.Label(label="", visible=False, wrap=True, ellipsize=Pango.EllipsizeMode.MIDDLE, xalign=0)
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

        self._destroyed = False
        self._apply_progress(ProgressInfo(0.0, "Please wait..."))
        self._timer_task = schedule_repeating_at_idle(self.on_update_progress, interval_seconds=0.5)
        self.connect("destroy", self.on_destroy)

    def on_stop_clicked(self, _widget) -> None:
        if self.progress.can_stop:
            self.progress.stop()

    def on_destroy(self, _widget) -> None:
        self._destroyed = True
        self._timer_task.unschedule()

    def on_update_progress(self) -> bool:
        try:
            self.update_progress()
            return True
        except Exception as ex:
            logger.exception("Unable to obtain a progress update: %s", ex)
            return False

    def update_progress(self) -> None:
        """Invokes the progress function and displays what it returns;
        this can be called to ensure the box is immediately up-to-date,
        without waiting for idle-time."""
        progress = self.progress_function()
        self._apply_progress(progress)

    def _apply_progress(self, progress: ProgressInfo):
        # Just in case the progress-function destroys the progress box.
        if self._destroyed:
            return

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
