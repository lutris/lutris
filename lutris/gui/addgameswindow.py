from gettext import gettext as _

from gi.repository import Gio, GLib, Gtk

from lutris import api
from lutris.exceptions import watch_errors
from lutris.gui.config.add_game import AddGameDialog
from lutris.gui.dialogs import DirectoryDialog, ErrorDialog, FileDialog
from lutris.gui.widgets.navigation_stack import NavigationStack
from lutris.gui.widgets.window import BaseApplicationWindow
from lutris.installer import AUTO_WIN32_EXE, get_installers
from lutris.scanners.lutris import scan_directory
from lutris.util.jobs import AsyncCall
from lutris.util.strings import gtk_safe, slugify


class AddGamesWindow(BaseApplicationWindow):  # pylint: disable=too-many-public-methods
    """Show a selection of ways to add games to Lutris"""

    sections = [
        (
            "system-search-symbolic",
            "go-next-symbolic",
            _("Search the Lutris website for installers"),
            _("Query our website for community installers"),
            "search_installers",
        ),
        (
            "folder-new-symbolic",
            "go-next-symbolic",
            _("Scan a folder for games"),
            _("Mass-import a folder of games"),
            "scan_folder"
        ),
        (
            "media-optical-dvd-symbolic",
            "go-next-symbolic",
            _("Install a Windows game from media"),
            _("Launch a setup file from an optical drive or download"),
            "install_from_setup"
        ),
        (
            "x-office-document-symbolic",
            "document-open-symbolic",
            _("Install from a local install script"),
            _("Run a YAML install script"),
            "install_from_script"
        ),
        (
            "list-add-symbolic",
            "view-more-horizontal-symbolic",
            _("Add locally installed game"),
            _("Manually configure a game available locally"),
            "add_local_game"
        )
    ]

    title_text = _("Add games to Lutris")

    def __init__(self, application=None):
        super().__init__(application=application)
        self.set_default_size(640, 450)
        self.search_entry = None
        self.search_frame = None
        self.search_listbox = None
        self.search_timer_id = None
        self.search_spinner = None
        self.text_query = None
        self.result_label = None
        self.continue_install_setup_button = None
        self.title_label = Gtk.Label(visible=True)
        self.vbox.pack_start(self.title_label, False, False, 12)

        back_button = Gtk.Button(_("Back"), sensitive=False)
        back_button.connect("clicked", self.on_back_clicked)
        self.action_buttons.pack_start(back_button, False, False, 0)

        self.stack = NavigationStack(back_button)
        self.vbox.pack_start(self.stack, True, True, 12)

        self.stack.add_named_factory("initial", self.create_initial_page)
        self.stack.add_named_factory("search_installers", self.create_search_installers_page)
        self.stack.add_named_factory("scan_folder", self.create_scan_folder_page)
        self.stack.add_named_factory("installed_games", self.create_installed_games_page)
        self.stack.add_named_factory("install_from_setup", self.create_install_from_setup_page)

        self.show_all()

        self.load_initial_page()

    def on_back_clicked(self, _widget):
        self.stack.navigate_back()

    def on_watched_error(self, error):
        ErrorDialog(str(error), parent=self)

    # Initial Page

    def load_initial_page(self):
        self.stack.navigate_to_page(self.present_inital_page)

    def create_initial_page(self):
        frame = Gtk.Frame(shadow_type=Gtk.ShadowType.ETCHED_IN)
        listbox = Gtk.ListBox()
        listbox.set_activate_on_single_click(True)
        for icon, next_icon, text, subtext, callback_name in self.sections:
            row = self._get_listbox_row(icon, text, subtext, next_icon)
            row.callback_name = callback_name

            listbox.add(row)
        listbox.connect("row-activated", self.on_row_activated)
        frame.add(listbox)
        return frame

    def present_inital_page(self):
        self.title_label.set_markup(f"<b>{self.title_text}</b>")
        self.stack.present_page("initial")

    @watch_errors()
    def on_row_activated(self, listbox, row):
        if row.callback_name:
            callback = getattr(self, row.callback_name)
            callback()

    # Search Installers Page

    def search_installers(self):
        """Search installers with the Lutris API"""
        if self.search_entry:
            self.search_entry.set_text("")
            self.result_label.set_text("")
            self.search_frame.hide()
        self.stack.navigate_to_page(self.present_search_installers_page)

    def create_search_installers_page(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, no_show_all=True, spacing=6, visible=True)
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, visible=True)
        self.search_entry = Gtk.SearchEntry(visible=True)
        hbox.pack_start(self.search_entry, True, True, 0)
        self.search_spinner = Gtk.Spinner(visible=False)
        hbox.pack_end(self.search_spinner, False, False, 6)
        vbox.pack_start(hbox, False, False, 0)
        self.result_label = self._get_label("")
        vbox.pack_start(self.result_label, False, False, 0)
        self.search_entry.connect("changed", self._on_search_updated)

        self.search_frame = Gtk.Frame(shadow_type=Gtk.ShadowType.ETCHED_IN)
        self.search_listbox = Gtk.ListBox(visible=True)
        self.search_listbox.connect("row-activated", self._on_game_selected)
        scroll = Gtk.ScrolledWindow(visible=True)
        scroll.set_vexpand(True)
        scroll.add(self.search_listbox)
        self.search_frame.add(scroll)
        vbox.pack_start(self.search_frame, True, True, 0)
        return vbox

    def present_search_installers_page(self):
        self.title_label.set_markup(_("<b>Search Lutris.net</b>"))
        self.stack.present_page("search_installers")
        self.search_entry.grab_focus()

    @watch_errors()
    def _on_search_updated(self, entry):
        if self.search_timer_id:
            GLib.source_remove(self.search_timer_id)
        self.text_query = entry.get_text().strip()
        self.search_timer_id = GLib.timeout_add(750, self.update_search_results)

    @watch_errors()
    def update_search_results(self):
        # Don't start a search while another is going; defer it instead.
        if self.search_spinner.get_visible():
            self.search_timer_id = GLib.timeout_add(750, self.update_search_results)
            return

        self.search_timer_id = None

        if self.text_query:
            self.search_spinner.show()
            self.search_spinner.start()
            AsyncCall(api.search_games, self.update_search_results_cb, self.text_query)

    @watch_errors()
    def update_search_results_cb(self, api_games, error):
        if error:
            raise error

        self.search_spinner.stop()
        self.search_spinner.hide()
        total_count = api_games.get("count", 0)
        count = len(api_games.get('results', []))

        if not count:
            self.result_label.set_markup(_("No results"))
        elif count == total_count:
            self.result_label.set_markup(_(f"Showing <b>{count}</b> results"))
        else:
            self.result_label.set_markup(_(f"<b>{total_count}</b> results, only displaying first {count}"))
        for row in self.search_listbox.get_children():
            row.destroy()
        for game in api_games.get("results", []):
            platforms = ",".join(gtk_safe(platform["name"]) for platform in game["platforms"])
            year = game['year'] or ""
            if platforms and year:
                platforms = ", " + platforms

            row = self._get_listbox_row("", gtk_safe(game['name']), f"{year}{platforms}")
            row.api_info = game
            self.search_listbox.add(row)
        self.search_frame.show()

    @watch_errors()
    def _on_game_selected(self, listbox, row):
        game_slug = row.api_info["slug"]
        installers = get_installers(game_slug=game_slug)
        application = Gio.Application.get_default()
        application.show_installer_window(installers)
        self.destroy()

    # Scan Folder Page

    def scan_folder(self):
        """Scan a folder of already installed games"""
        def present_scan_folder_page():
            self.title_label.set_markup("<b>Import games from a folder</b>")
            self.stack.present_page("scan_folder")
            AsyncCall(scan_directory, self._on_folder_scanned, script_dlg.folder)

        script_dlg = DirectoryDialog(_("Select folder to scan"), parent=self)
        if script_dlg.folder:
            self.stack.jump_to_page(present_scan_folder_page)

    def create_scan_folder_page(self):
        spinner = Gtk.Spinner(visible=True)
        spinner.start()
        return spinner

    @watch_errors()
    def _on_folder_scanned(self, result, error):
        def present_installed_games_page():
            if installed or missing:
                self.title_label.set_markup(_("<b>Games found</b>"))
            else:
                self.title_label.set_markup(_("<b>No games found</b>"))

            page = self.create_installed_games_page(installed, missing)
            self.stack.present_replacement_page("installed_games", page)

        if error:
            ErrorDialog(str(error), parent=self)
            self.stack.navigation_reset()
            return

        installed, missing = result
        self.stack.navigate_to_page(present_installed_games_page)

    def create_installed_games_page(self, installed, missing):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        if installed:
            installed_label = self._get_label("Installed games")
            vbox.pack_start(installed_label, False, False, 0)

            installed_listbox = Gtk.ListBox()
            installed_scroll = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.ETCHED_IN)
            installed_scroll.set_vexpand(True)
            installed_scroll.add(installed_listbox)
            vbox.pack_start(installed_scroll, True, True, 0)
            for folder in installed:
                installed_listbox.add(self._get_listbox_row("", gtk_safe(folder), ""))

        if missing:
            missing_listbox = Gtk.ListBox()
            missing_scroll = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.ETCHED_IN)
            missing_scroll.set_vexpand(True)
            missing_scroll.add(missing_listbox)
            vbox.pack_end(missing_scroll, True, True, 0)
            for folder in missing:
                missing_listbox.add(self._get_listbox_row("", gtk_safe(folder), ""))

            missing_label = self._get_label("No match found")
            vbox.pack_end(missing_label, False, False, 0)

        return vbox

    # Install from Setup

    def install_from_setup(self):
        """Install from a setup file"""
        self.stack.navigate_to_page(self.present_install_from_setup_page)

    def create_install_from_setup_page(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        label = self._get_label(_("Game name"))
        vbox.add(label)
        entry = Gtk.Entry()
        vbox.add(entry)

        self.continue_install_setup_button = Gtk.Button(_("Continue"))
        self.continue_install_setup_button.connect("clicked", self._on_install_setup_continue, entry)

        style_context = self.continue_install_setup_button.get_style_context()
        style_context.add_class("suggested-action")

        self.action_buttons.pack_end(self.continue_install_setup_button, False, False, 0)
        return vbox

    def present_install_from_setup_page(self):
        def on_exit_page():
            self.continue_install_setup_button.hide()

        self.title_label.set_markup(_("<b>Select setup file</b>"))
        self.stack.present_page("install_from_setup")
        self.continue_install_setup_button.show()
        return on_exit_page

    @watch_errors()
    def _on_install_setup_continue(self, button, entry):
        name = entry.get_text().strip()
        installer = {
            "name": name,
            "version": _("Setup file"),
            "slug": slugify(name) + "-setup",
            "game_slug": slugify(name),
            "runner": "wine",
            "script": {
                "game": {
                    "exe": AUTO_WIN32_EXE, "prefix": "$GAMEDIR"
                },
                "files": [
                    {"setupfile": "N/A:%s" % _("Select the setup file")}
                ],
                "installer": [
                    {"task": {"name": "wineexec", "executable": "setupfile"}}
                ]
            }
        }
        application = Gio.Application.get_default()
        application.show_installer_window([installer])
        self.destroy()

    # Install from Script

    def install_from_script(self):
        """Install from a YAML file"""
        script_dlg = FileDialog(_("Select a Lutris installer"), parent=self)
        if script_dlg.filename:
            installers = get_installers(installer_file=script_dlg.filename)
            application = Gio.Application.get_default()
            application.show_installer_window(installers)
            self.destroy()

    # Add Local Game

    def add_local_game(self):
        """Manually configure game"""
        AddGameDialog(parent=self)
        GLib.idle_add(self.destroy)  # defer destory so the game dialog can be centered first

    # Implementation

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

    def _get_listbox_row(self, left_icon_name, text, subtext, right_icon_name=""):
        row = Gtk.ListBoxRow(visible=True)
        row.set_selectable(False)
        row.set_activatable(True)

        box = Gtk.Box(
            spacing=12,
            margin_right=12,
            margin_left=12,
            margin_top=12,
            margin_bottom=12,
            visible=True)

        if left_icon_name:
            icon = self._get_icon(left_icon_name)
            box.pack_start(icon, False, False, 0)
        label = self._get_label(f"<b>{text}</b>\n{subtext}")
        box.pack_start(label, True, True, 0)
        if left_icon_name:
            next_icon = self._get_icon(right_icon_name, small=True)
            box.pack_start(next_icon, False, False, 0)
        row.add(box)
        return row
