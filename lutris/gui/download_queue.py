# pylint: disable=no-member
import os
from typing import Dict

from gi.repository import Gtk

from lutris.gui.widgets.gi_composites import GtkTemplate
from lutris.gui.widgets.progress_box import ProgressBox
from lutris.util import datapath


@GtkTemplate(ui=os.path.join(datapath.get(), "ui", "download-queue.ui"))
class DownloadQueue(Gtk.ScrolledWindow):
    """This class is a widget that displays a stack of progress boxes, which you can create
    and destroy with its methods."""
    __gtype_name__ = "DownloadQueue"

    download_box: Gtk.Box = GtkTemplate.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.init_template()

        self.progress_boxes: Dict[ProgressBox.ProgressFunction, ProgressBox] = {}

        try:
            # GTK 3.22 is required for this, but if this fails we can still run.
            # The download area comes out too small, but it's usable.
            self.set_max_content_height(250)
            self.set_propagate_natural_height(True)
        except AttributeError:
            pass

    def add_progress_box(self, progress_function: ProgressBox.ProgressFunction) -> ProgressBox:
        """Adds a progress box to the queue; it will display the progress indicated by
        the progress_function, which is called immediately to initialize the box and
        then polled to update it. Returns the new progress box.

        If called with a progress_function that has a box already, this method returns
        that box instead of creating one."""

        def check_progress():
            progress_info = progress_function()

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
        return progress_box

    def remove_progress_box(self, progress_function: ProgressBox.ProgressFunction) -> None:
        """Removes and destroys the progress box created for the progress_function given,
        if any is present."""
        progress_box = self.progress_boxes.get(progress_function)
        if progress_box:
            del self.progress_boxes[progress_function]
            progress_box.destroy()
