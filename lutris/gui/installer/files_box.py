from gi.repository import GObject, Gtk

from lutris.gui.installer.file_box import InstallerFileBox
from lutris.util.log import logger


class InstallerFilesBox(Gtk.ListBox):
    """List box presenting all files needed for an installer"""

    __gsignals__ = {
        "files-ready": (GObject.SIGNAL_RUN_LAST, None, (bool, )),
        "files-available": (GObject.SIGNAL_RUN_LAST, None, ())
    }

    def __init__(self, installer_files, parent):
        super().__init__()
        self.parent = parent
        self.installer_files = installer_files
        self.ready_files = set()
        self.available_files = set()
        self.installer_files_boxes = {}
        for installer_file in installer_files:
            installer_file_box = InstallerFileBox(installer_file)
            installer_file_box.connect("file-ready", self.on_file_ready)
            installer_file_box.connect("file-unready", self.on_file_unready)
            installer_file_box.connect("file-available", self.on_file_available)
            self.installer_files_boxes[installer_file.id] = installer_file_box
            self.add(installer_file_box)
            if installer_file_box.is_ready:
                self.ready_files.add(installer_file.id)
        self.show_all()
        self.check_files_ready()

    def start_all(self):
        """Start all downloads"""
        for file_id in self.installer_files_boxes:
            self.installer_files_boxes[file_id].start()

    @property
    def is_ready(self):
        """Return True if all files are ready to be fetched"""
        return len(self.ready_files) == len(self.installer_files)

    def check_files_ready(self):
        """Checks if all installer files are ready and emit a signal if so"""
        logger.debug("Files are ready? %s", self.is_ready)
        self.emit("files-ready", self.is_ready)

    def on_file_ready(self, widget):
        """Fired when a file has a valid provider.
        If the file is user provided, it must set to a valid path.
        """
        file_id = widget.installer_file.id
        self.ready_files.add(file_id)
        self.check_files_ready()

    def on_file_unready(self, widget):
        """Fired when a file can't be provided.
        Blocks the installer from continuing.
        """
        file_id = widget.installer_file.id
        self.ready_files.remove(file_id)
        self.check_files_ready()

    def on_file_available(self, widget):
        """A new file is available"""
        file_id = widget.installer_file.id
        self.available_files.add(file_id)
        if len(self.available_files) == len(self.installer_files):
            logger.info("All files available")
            self.emit("files-available")

    def get_game_files(self):
        """Return a mapping of the local files usable by the interpreter"""
        return {
            installer_file.id: installer_file.dest_file
            for installer_file in self.installer_files
        }
