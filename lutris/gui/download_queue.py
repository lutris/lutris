# pylint: disable=no-member
import os
from typing import Any, Callable, Dict, Iterable, Optional

from gi.repository import Gtk

from lutris.gui.widgets.gi_composites import GtkTemplate
from lutris.gui.widgets.progress_box import ProgressBox
from lutris.util import datapath
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger


@GtkTemplate(ui=os.path.join(datapath.get(), "ui", "download-queue.ui"))
class DownloadQueue(Gtk.ScrolledWindow):
    """This class is a widget that displays a stack of progress boxes, which you can create
    and destroy with its methods."""
    __gtype_name__ = "DownloadQueue"

    download_box: Gtk.Box = GtkTemplate.Child()

    CompletionFunction = Callable[[Any, Optional[Exception]], None]

    def __init__(self, revealer: Gtk.Revealer, **kwargs):
        super().__init__(**kwargs)
        self.revealer = revealer
        self.init_template()

        self.progress_boxes: Dict[ProgressBox.ProgressFunction, ProgressBox] = {}

        try:
            # GTK 3.22 is required for this, but if this fails we can still run.
            # The download area comes out too small, but it's usable.
            self.set_max_content_height(250)
            self.set_propagate_natural_height(True)
        except AttributeError:
            pass

    @property
    def is_empty(self):
        """True if the queue has no progress boxes in it."""
        return not bool(self.progress_boxes)

    def add_progress_box(self, progress_function: ProgressBox.ProgressFunction) -> ProgressBox:
        """Adds a progress box to the queue; it will display the progress indicated by
        the progress_function, which is called immediately to initialize the box and
        then polled to update it. Returns the new progress box.

        The progres-box is removed when its function returns ProgressInfo.ended(), or when
        you call remove_progress_box().

        If called with a progress_function that has a box already, this method returns
        that box instead of creating one."""

        def check_progress():
            progress_info = progress_function()

            if progress_info.has_ended:
                self.remove_progress_box(progress_function)
                return progress_info

            if progress_info.label_markup:
                progress_info.label_markup = "<span size='10000'>%s</span>" % progress_info.label_markup

            return progress_info

        progress_box = self.progress_boxes.get(progress_function)
        if progress_box:
            progress_box.update_progress()
            return progress_box

        progress_box = ProgressBox(check_progress, visible=False, margin=6)
        progress_box.update_progress()

        self.progress_boxes[progress_function] = progress_box
        self.download_box.pack_start(progress_box, False, False, 0)
        progress_box.show()
        self.revealer.set_reveal_child(True)
        return progress_box

    def remove_progress_box(self, progress_function: ProgressBox.ProgressFunction) -> None:
        """Removes and destroys the progress box created for the progress_function given,
        if any is present."""
        progress_box = self.progress_boxes.get(progress_function)
        if progress_box:
            del self.progress_boxes[progress_function]
            progress_box.destroy()
            if not self.progress_boxes:
                self.revealer.set_reveal_child(False)

    def start(self, func: Callable[[], Any],
              progress_function: ProgressBox.ProgressFunction,
              completion_function: CompletionFunction = None):
        """Runs 'func' on a thread, while displaying a progress bar. The 'progress_function'
        controls this progress bar, and is removed when the function completes. After that,
        the completion function executes on the main thread, and is given whatever the
        original func returned, or the error it raised."""

        self.add_progress_box(progress_function)

        def completion_callback(result, error):
            if error:
                logger.exception("Failed to execute function: %s", error)

            self.remove_progress_box(progress_function)

            if bool(completion_function):
                completion_function(result, error)

        AsyncCall(func, completion_callback)

    def start_multiple(self, func: Callable[[], Any],
                       progress_functions: Iterable[ProgressBox.ProgressFunction],
                       completion_function: CompletionFunction = None):
        """Runs 'func' on a thread, while displaying a set of progress bars. The 'progress_functions'
        control the progress bars, and they are all removed when the function completes. Each
        progress bar can be also be removed if it's progress function returns ProgressInfo.ended()."""

        # Must capture the functions, since in earlier (<3.8) Pythons functions do not provide
        # value equality, so we need to make sure we're always using what we started with.
        captured_functions = list(progress_functions)

        for f in captured_functions:
            self.add_progress_box(f)

        def completion_callback(result, error):
            if error:
                logger.exception("Failed to execute function: %s", error)

            for to_end in captured_functions:
                self.remove_progress_box(to_end)

            if bool(completion_function):
                completion_function(result, error)

        AsyncCall(func, completion_callback)
