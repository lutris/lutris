# pylint: disable=no-member
import os

from gi.repository import Gtk

from lutris.gui.widgets.gi_composites import GtkTemplate
from lutris.gui.widgets.progress_box import ProgressBox
from lutris.runtime import ComponentUpdater
from lutris.util import datapath


@GtkTemplate(ui=os.path.join(datapath.get(), "ui", "download-queue.ui"))
class DownloadQueue(Gtk.ScrolledWindow):
    __gtype_name__ = "DownloadQueue"

    download_box: Gtk.Box = GtkTemplate.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.init_template()

        self.progress_boxes = {}

        try:
            # GTK 3.22 is required for this, but if this fails we can still run.
            # The download area comes out too small, but it's usable.
            self.set_max_content_height(250)
            self.set_propagate_natural_height(True)
        except AttributeError:
            pass

    def add_updater(self, updater: ComponentUpdater) -> None:
        def start_update():
            def check_progress():
                progress_info = updater.get_progress()

                if progress_info.label_markup:
                    progress_info.label_markup = "<span size='10000'>%s</span>" % progress_info.label_markup

                box.show()
                return progress_info

            box = ProgressBox(check_progress, visible=False, margin=6)
            box.update_progress()
            return box

        progress_box = start_update()
        self.progress_boxes[updater] = progress_box
        self.download_box.pack_start(progress_box, False, False, 0)
        progress_box.show()

    def end_updater(self, updater: ComponentUpdater) -> None:
        progress_box = self.progress_boxes.get(updater)
        if progress_box:
            del self.progress_boxes[updater]
            progress_box.destroy()
