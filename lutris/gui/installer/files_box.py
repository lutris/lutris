from gi.repository import GObject, Gtk

from lutris.gui.installer.file_box import InstallerFileBox
from lutris.util.log import logger


class InstallerFilesBox(Gtk.ListBox):
    """List box presenting all files needed for an installer"""

    max_downloads = 3

    __gsignals__ = {
        "files-ready": (GObject.SIGNAL_RUN_LAST, None, (bool, )),
        "files-available": (GObject.SIGNAL_RUN_LAST, None, ())
    }

    def __init__(self):
        super().__init__()
        self.installer = None
        self.ready_files = set()
        self.available_files = set()
        self.installer_files_boxes = {}
        self._file_queue = []

    def load_installer(self, installer):
        self.stop_all()

        self.installer = installer
        self.available_files.clear()
        self.ready_files.clear()
        self.installer_files_boxes.clear()
        self._file_queue.clear()

        for child in self.get_children():
            child.destroy()

        for installer_file in installer.files:
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
        """Iterates through installer files while keeping the number
        of simultaneously downloaded files down to a maximum number"""
        started_downloads = 0
        for file_id, file_entry in self.installer_files_boxes.items():
            if file_id not in self.available_files:
                if file_entry.provider == "download":
                    started_downloads += 1
                    if started_downloads <= self.max_downloads:
                        file_entry.start()
                    else:
                        self._file_queue.append(file_id)
                else:
                    file_entry.start()
        if len(self.available_files) == len(self.installer.files):
            logger.info("All files remain available")
            self.emit("files-available")

    def stop_all(self):
        """Stops all ongoing files gathering.
        Iterates through installer files, and call the "stop" command
        if they've been started and not available yet.
        """
        self._file_queue.clear()
        for file_id, file_box in self.installer_files_boxes.items():
            if file_box.started and file_id not in self.available_files and file_box.stop_func is not None:
                file_box.stop_func()

    @property
    def is_ready(self):
        """Return True if all files are ready to be fetched"""
        return len(self.ready_files) == len(self.installer.files)

    def check_files_ready(self):
        """Checks if all installer files are ready and emit a signal if so"""
        if self.is_ready:
            self.emit("files-ready", self.is_ready)
        else:
            logger.info("Waiting for user to provide files")

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
        self.ready_files.discard(file_id)
        self.check_files_ready()

    def on_file_available(self, widget):
        """A new file is available"""
        file_id = widget.installer_file.id
        logger.debug("%s is available", file_id)
        self.available_files.add(file_id)
        if self._file_queue:
            next_file_id = self._file_queue.pop()
            self.installer_files_boxes[next_file_id].start()
        if len(self.available_files) == len(self.installer.files):
            logger.info("All files available")
            self.emit("files-available")

    def get_game_files(self):
        """Return a mapping of the local files usable by the interpreter"""
        return {
            installer_file.id: installer_file.dest_file
            for installer_file in self.installer.files
        }
