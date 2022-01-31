from gettext import gettext as _

from gi.repository import Gtk

from lutris.gui.config.add_game import AddGameDialog
from lutris.gui.widgets.window import BaseApplicationWindow


class AddGamesWindow(BaseApplicationWindow):  # pylint: disable=too-many-public-methods
    """Show a selection of ways to add games to Lutris"""

    sections = [
        (
            "system-search-symbolic",
            _("Search the Lutris website for installers"),
            _("Query our website for community installers"),
            "search_installers"
        ),
        (
            "folder-new-symbolic",
            _("Scan a folder for games"),
            _("Mass-import a folder of games"),
            "scan_folder"
        ),
        (
            "media-optical-dvd-symbolic",
            _("Install game from media"),
            _("Launch a setup file from an optical drive or download"),
            "install_from_setup"
        ),
        (
            "x-office-document-symbolic",
            _("Install from a local install script"),
            _("Run a YAML install script"),
            "install_from_script"
        ),
        (
            "list-add-symbolic",
            _("Add locally installed game"),
            _("Manually configure a game available locally"),
            "add_local_game"
        )
    ]

    title_text = _("Add games to Lutris")

    def __init__(self, application=None):
        super().__init__(application=application)
        self.set_default_size(560, 450)

        title_label = Gtk.Label(visible=True)
        title_label.set_markup(f"<b>{self.title_text}</b>")
        self.vbox.pack_start(title_label, False, False, 18)

        self.listbox = Gtk.ListBox(visible=True)
        self.listbox.set_activate_on_single_click(True)
        self.vbox.pack_start(self.listbox, False, False, 12)
        for icon, text, subtext, callback_name in self.sections:
            row = self.build_row(icon, text, subtext)
            row.callback_name = callback_name

            self.listbox.add(row)
        self.listbox.connect("row-activated", self.on_row_activated)

    def on_row_activated(self, listbox, row):
        if row.callback_name:
            callback = getattr(self, row.callback_name)
            callback()

    def _get_row(self):
        row = Gtk.ListBoxRow(visible=True)
        row.set_selectable(False)
        row.set_activatable(True)
        return row

    def _get_box(self):
        return Gtk.Box(
            spacing=12,
            margin_right=12,
            margin_left=12,
            margin_top=12,
            margin_bottom=12,
            visible=True,
        )

    def _get_icon(self, name, small=False):
        if small:
            size = Gtk.IconSize.MENU
        else:
            size = Gtk.IconSize.DND
        icon = Gtk.Image.new_from_icon_name(name, size)
        icon.show()
        return icon

    def _get_label(self, text):
        label = Gtk.Label(visible=True)
        label.set_markup(text)
        label.set_alignment(0, 0.5)
        return label

    def build_row(self, icon_name, text, subtext):
        row = self._get_row()
        box = self._get_box()
        icon = self._get_icon(icon_name)
        box.pack_start(icon, False, False, 0)
        label = self._get_label(f"<b>{text}</b>\n{subtext}")
        box.pack_start(label, True, True, 0)
        next_icon = self._get_icon("go-next-symbolic", small=True)
        box.pack_start(next_icon, False, False, 0)
        row.add(box)
        return row

    def search_installers(self):
        """Search installers with the Lutris API"""
        print("open search")

    def scan_folder(self):
        """Import a folder of ROMs"""
        print("open scan")

    def install_from_setup(self):
        """Install from a setup file"""
        print("choose setup file")

    def install_from_script(self):
        """Install from a YAML file"""
        print("Choose YAML file")

    def add_local_game(self):
        """Manually configure game"""
        AddGameDialog(None)
        self.destroy()
