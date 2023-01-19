from gettext import gettext as _

from gi.repository import Gtk
from lutris.util.system import get_md5_hash
from lutris.gui.dialogs import ModalDialog
from lutris.util.jobs import AsyncCall
from lutris.scanners.tosec import search_tosec_by_md5


class ImportGameDialog(ModalDialog):
    def __init__(self, files, parent=None) -> None:
        super().__init__(
            _("Import a game"),
            parent=parent,
            border_width=10
        )
        self.files = files
        self.checksum_labels = {}
        self.description_labels = {}
        self.category_labels = {}
        self.file_hashes = {}
        self.files_by_hash = {}
        self.set_size_request(480, 240)
        self.get_content_area().add(self.add_file_labels(files))
        self.add_default_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        self.show_all()
        AsyncCall(self.search_checksums, self.search_result_finished)

    def add_file_labels(self, files):
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        for file_path in files:
            row = Gtk.ListBoxRow()
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            vbox.set_margin_left(12)

            description_label = Gtk.Label("")
            description_label.set_halign(Gtk.Align.START)
            vbox.pack_start(description_label, True, True, 5)
            self.description_labels[file_path] = description_label

            label = Gtk.Label(file_path)
            label.set_halign(Gtk.Align.START)
            vbox.pack_start(label, True, True, 5)

            checksum_label = Gtk.Label("")
            checksum_label.set_halign(Gtk.Align.START)
            vbox.pack_start(checksum_label, True, True, 5)
            self.checksum_labels[file_path] = checksum_label

            category_label = Gtk.Label("")
            category_label.set_halign(Gtk.Align.START)
            vbox.pack_start(category_label, True, True, 5)
            self.category_labels[file_path] = category_label

            row.add(vbox)
            listbox.add(row)
        return listbox

    def search_checksums(self):
        results = []
        for filename in self.files:
            md5 = get_md5_hash(filename)
            self.file_hashes[filename] = md5
            self.files_by_hash[md5] = filename
            result = search_tosec_by_md5(md5)
            if not result:
                result = [{"name": "Not found", "category": {"name": ""}, "roms":[{"md5": md5}]}]
            results.append(result)
        return results

    def search_result_finished(self, results, error):
        for result in results:
            for game in result:
                for rom in game["roms"]:
                    if rom["md5"] in self.files_by_hash:
                        filename = self.files_by_hash[rom["md5"]]
                        label = self.checksum_labels[filename]
                        label.set_text(rom["md5"])

                        label = self.description_labels[filename]
                        label.set_markup("<b>%s</b>" % game["name"])

                        label = self.category_labels[filename]
                        label.set_text(game["category"]["name"])