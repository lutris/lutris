# pylint: disable=no-member
import os
from typing import Any, Callable, Dict, Iterable, List, Optional, Set

from gi.repository import GObject, Gtk  # type: ignore

from lutris.gui.widgets.gi_composites import GtkTemplate
from lutris.gui.widgets.progress_box import ProgressBox
from lutris.util import datapath
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger


@GtkTemplate(ui=os.path.join(datapath.get(), "ui", "download-queue.ui"))
class DownloadQueue(Gtk.ScrolledWindow):
    """This class is a widget that displays a stack of progress boxes, which you can create
    and destroy with its methods."""

    __gsignals__ = {
        "download-completed": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    __gtype_name__ = "DownloadQueue"

    download_box: Gtk.Box = GtkTemplate.Child()  # type: ignore

    CompletionFunction = Callable[[Any], None]
    ErrorFunction = Callable[[Exception], None]

    def __init__(self, revealer: Gtk.Revealer, **kwargs):
        super().__init__(**kwargs)
        self.revealer = revealer
        self.init_template()

        self.running_operation_names: Set[str] = set()
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

    def start(
        self,
        operation: Callable[[], Any],
        progress_function: ProgressBox.ProgressFunction,
        completion_function: Optional[CompletionFunction] = None,
        error_function: Optional[ErrorFunction] = None,
        operation_name: Optional[str] = None,
    ) -> bool:
        """Runs 'operation' on a thread, while displaying a progress bar. The 'progress_function'
        controls this progress bar, and it is removed when the 'operation' completes.

        If 'operation_name' is given, it is added to self.running_operation_names while
        the 'operation' runs. If the name is present already, this method does nothing
        but returns False. If the worker thread has started, this returns True.

        Args:
            operation:              Called on a worker thread
            progress_function:      Called on the main thread for progress status
            completion_function:    Called on the main thread on completion, with result
            error_function:         Called on the main threa don error, with exception
            operation_name:         Name of operation, to prevent duplicate queued work."""

        return self.start_multiple(
            operation,
            [progress_function],
            completion_function=completion_function,
            error_function=error_function,
            operation_names=[operation_name] if operation_name else None,
        )

    def start_multiple(
        self,
        operation: Callable[[], Any],
        progress_functions: Iterable[ProgressBox.ProgressFunction],
        completion_function: Optional[CompletionFunction] = None,
        error_function: Optional[ErrorFunction] = None,
        operation_names: Optional[List[str]] = None,
    ) -> bool:
        """Runs 'operation' on a thread, while displaying a set of progress bars. The
        'progress_functions' control these progress bars, and they are removed when the
        'operation' completes.

        If 'operation_names' is given, they are added to self.running_operation_names while
        the 'operation' runs. If any name is present already, this method does nothing
        but returns False. If the worker thread has started, this returns True.

        Args:
            operation:              Called on a worker thread
            progress_functions:     Called on the main thread for progress status
            completion_function:    Called on the main thread on completion, with result
            error_function:         Called on the main threa don error, with exception
            operation_names:        Names of operations, to prevent duplicate queued work."""

        if operation_names:
            if not self.running_operation_names.isdisjoint(operation_names):
                return False
            self.running_operation_names.update(operation_names)
        else:
            operation_names = []

        # Must capture the functions, since in earlier (<3.8) Pythons functions do not provide
        # value equality, so we need to make sure we're always using what we started with.
        captured_functions = list(progress_functions)

        for f in captured_functions:
            self.add_progress_box(f)

        def completion_callback(result, error):
            for to_end in captured_functions:
                self.remove_progress_box(to_end)

            self.running_operation_names.difference_update(operation_names)

            if error:
                logger.exception("Failed to execute download-queue function: %s", error)
                if error_function:
                    error_function(error)
            elif completion_function:
                completion_function(result)
            self.emit("download-completed")

        AsyncCall(operation, completion_callback)
        return True
