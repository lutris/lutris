import os

from gi.repository import Gtk

from lutris import settings


class AboutDialog:
    def __init__(self):
        ui_filename = os.path.join(settings.get_data_path(), 'ui',
                                   'AboutDialog.ui')
        if not os.path.exists(ui_filename):
            ui_filename = None

        builder = Gtk.Builder()
        builder.add_from_file(ui_filename)
        self.dialog = builder.get_object("about_dialog")
        builder.connect_signals(self)

        self.dialog.show_all()

    def destroy(self, widget):
        self.dialog.destroy()
