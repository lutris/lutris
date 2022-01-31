from gettext import gettext as _

from gi.repository import Gio, GLib, Gtk

from lutris import api
from lutris.gui.config.add_game import AddGameDialog
from lutris.gui.widgets.window import BaseApplicationWindow
from lutris.installer import get_installers
from lutris.util.strings import gtk_safe


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
        self.set_default_size(640, 450)
        self.search_timer_id = None
        self.text_query = None
        self.result_label = None
        self.title_label = Gtk.Label(visible=True)
        self.title_label.set_markup(f"<b>{self.title_text}</b>")
        self.vbox.pack_start(self.title_label, False, False, 12)

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
        if icon_name:
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
        self.title_label.set_markup("<b>Search Lutris.net</b>")
        self.listbox.destroy()
        entry = Gtk.Entry(visible=True)
        self.vbox.add(entry)
        self.result_label = self._get_label("")
        self.vbox.add(self.result_label)
        entry.connect("changed", self._on_search_updated)
        self.listbox = Gtk.ListBox()
        self.listbox.connect("row-activated", self._on_game_selected)
        scroll = Gtk.ScrolledWindow(visible=True)
        scroll.set_vexpand(True)
        scroll.add(self.listbox)
        self.vbox.add(scroll)
        entry.grab_focus()

    def _on_search_updated(self, entry):
        if self.search_timer_id:
            GLib.source_remove(self.search_timer_id)
        self.text_query = entry.get_text().strip()
        self.search_timer_id = GLib.timeout_add(750, self.update_search_results)

    def _on_game_selected(self, listbox, row):
        game_slug = row.api_info["slug"]
        installers = get_installers(game_slug=game_slug)
        application = Gio.Application.get_default()
        application.show_installer_window(installers)
        self.destroy()

    def update_search_results(self):
        if not self.text_query:
            return
        api_games = api.search_games(self.text_query)
        total_count = api_games.get("count", 0)
        count = len(api_games.get('results', []))

        if not count:
            self.result_label.set_markup(_("No results"))
        elif count == total_count:
            self.result_label.set_markup(_(f"Showing <b>{count}</b> results"))
        else:
            self.result_label.set_markup(_(f"<b>{total_count}</b> results, only displaying first {count}"))
        for row in self.listbox.get_children():
            row.destroy()
        for game in api_games.get("results", []):
            platforms = ",".join(gtk_safe(platform["name"]) for platform in game["platforms"])
            year = game['year'] or ""
            if platforms and year:
                platforms = ", " + platforms

            row = self.build_row("", gtk_safe(game['name']), f"{year}{platforms}")
            row.api_info = game
            self.listbox.add(row)
        self.listbox.show()

    def scan_folder(self):
        """Import a folder of ROMs"""
        self.title_label.set_markup(_("<b>Scan a folder</b>"))
        print("open scan")

    def install_from_setup(self):
        """Install from a setup file"""
        self.title_label.set_markup(_("<b>Select setup file</b>"))
        print("choose setup file")

    def install_from_script(self):
        """Install from a YAML file"""

        print("Choose YAML file")

    def add_local_game(self):
        """Manually configure game"""
        AddGameDialog(None)
        self.destroy()
