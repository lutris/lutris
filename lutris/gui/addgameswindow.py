import os
from gettext import gettext as _

from gi.repository import Gio, GLib, Gtk

from lutris import api
from lutris.exceptions import watch_errors
from lutris.gui.config.add_game_dialog import AddGameDialog
from lutris.gui.dialogs import ErrorDialog, ModelessDialog
from lutris.gui.dialogs.game_import import ImportGameDialog
from lutris.gui.widgets.common import FileChooserEntry
from lutris.gui.widgets.navigation_stack import NavigationStack
from lutris.installer import AUTO_WIN32_EXE, get_installers
from lutris.scanners.lutris import scan_directory
from lutris.util.jobs import AsyncCall
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.strings import gtk_safe, slugify


class AddGamesWindow(ModelessDialog):  # pylint: disable=too-many-public-methods
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
            "application-x-executable-symbolic",
            "go-next-symbolic",
            _("Install a Windows game from an executable"),
            _("Launch a Windows executable (.exe) installer"),
            "install_from_setup"
        ),
        (
            "x-office-document-symbolic",
            "go-next-symbolic",
            _("Install from a local install script"),
            _("Run a YAML install script"),
            "install_from_script"
        ),
        (
            "application-x-firmware-symbolic",
            "go-next-symbolic",
            _("Import a ROM"),
            _("Import a ROM that is known to Lutris"),
            "import_rom"
        ),
        (
            "list-add-symbolic",
            "view-more-horizontal-symbolic",
            _("Add locally installed game"),
            _("Manually configure a game available locally"),
            "add_local_game"
        )
    ]

    def __init__(self, **kwargs):
        ModelessDialog.__init__(self, title=_("Add games to Lutris"), use_header_bar=True, **kwargs)
        self.set_default_size(640, 450)
        self.search_entry = None
        self.search_frame = None
        self.search_explanation_label = None
        self.search_listbox = None
        self.search_timer_id = None
        self.search_spinner = None
        self.text_query = None
        self.search_result_label = None

        content_area = self.get_content_area()

        self.page_title_label = Gtk.Label(visible=True)
        content_area.pack_start(self.page_title_label, False, False, 0)

        self.accelerators = Gtk.AccelGroup()
        self.add_accel_group(self.accelerators)

        header_bar = self.get_header_bar()

        self.back_button = Gtk.Button(_("Back"), no_show_all=True)
        self.back_button.connect("clicked", self.on_back_clicked)
        key, mod = Gtk.accelerator_parse("<Alt>Left")
        self.back_button.add_accelerator("clicked", self.accelerators, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse("<Alt>Home")
        self.accelerators.connect(key, mod, Gtk.AccelFlags.VISIBLE, self.on_navigate_home)
        header_bar.pack_start(self.back_button)

        self.continue_button = Gtk.Button(_("_Continue"), no_show_all=True, use_underline=True)
        header_bar.pack_end(self.continue_button)
        self.continue_handler = None

        self.cancel_button = Gtk.Button(_("Cancel"), use_underline=True)
        self.cancel_button.connect("clicked", self.on_cancel_clicked)
        key, mod = Gtk.accelerator_parse("Escape")
        self.accelerators.connect(key, mod, Gtk.AccelFlags.VISIBLE, lambda *_args: self.destroy())
        header_bar.pack_start(self.cancel_button)
        header_bar.set_show_close_button(False)

        content_area.set_margin_top(18)
        content_area.set_margin_bottom(18)
        content_area.set_margin_right(18)
        content_area.set_margin_left(18)
        content_area.set_spacing(12)

        self.stack = NavigationStack(self.back_button, cancel_button=self.cancel_button)
        content_area.pack_start(self.stack, True, True, 0)

        # Pre-create some controls so they can be used in signal handlers

        self.scan_directory_chooser = FileChooserEntry(
            title=_("Select folder"), action=Gtk.FileChooserAction.SELECT_FOLDER
        )

        self.install_from_setup_game_name_entry = Gtk.Entry()
        self.install_from_setup_game_slug_checkbox = Gtk.CheckButton(label="Identifier")
        self.install_from_setup_game_slug_entry = Gtk.Entry(sensitive=False)
        self.install_from_setup_32bit_prefix_checkbox = None

        self.install_script_file_chooser = FileChooserEntry(
            title=_("Select script"), action=Gtk.FileChooserAction.OPEN
        )

        self.import_rom_file_chooser = FileChooserEntry(
            title=_("Select ROM file"), action=Gtk.FileChooserAction.OPEN
        )

        self.stack.add_named_factory("initial", self.create_initial_page)
        self.stack.add_named_factory("search_installers", self.create_search_installers_page)
        self.stack.add_named_factory("scan_folder", self.create_scan_folder_page)
        self.stack.add_named_factory("scanning_folder", self.create_scanning_folder_page)
        self.stack.add_named_factory("installed_games", self.create_installed_games_page)
        self.stack.add_named_factory("install_from_setup", self.create_install_from_setup_page)
        self.stack.add_named_factory("install_from_script", self.create_install_from_script_page)
        self.stack.add_named_factory("import_rom", self.create_import_rom_page)

        self.show_all()

        self.load_initial_page()

    @watch_errors()
    def on_back_clicked(self, _widget):
        self.stack.navigate_back()

    @watch_errors()
    def on_navigate_home(self, _accel_group, _window, _keyval, _modifier):
        self.stack.navigate_home()

    @watch_errors()
    def on_cancel_clicked(self, _widget):
        self.destroy()

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
        self.set_page_title_markup(None)
        self.stack.present_page("initial")
        self.display_cancel_button()

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
            self.search_result_label.set_text("")
            self.search_result_label.hide()
            self.search_frame.hide()
            self.search_explanation_label.show()
        self.stack.navigate_to_page(self.present_search_installers_page)

    def create_search_installers_page(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, no_show_all=True, spacing=6, visible=True)
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, visible=True)
        self.search_entry = Gtk.SearchEntry(visible=True)
        hbox.pack_start(self.search_entry, True, True, 0)
        self.search_spinner = Gtk.Spinner(visible=False)
        hbox.pack_end(self.search_spinner, False, False, 6)
        vbox.pack_start(hbox, False, False, 0)
        self.search_result_label = self._get_label("")
        self.search_result_label.hide()
        vbox.pack_start(self.search_result_label, False, False, 0)
        self.search_entry.connect("changed", self._on_search_updated)

        explanation = _(
            "Lutris will search Lutris.net for games matching the terms you enter, and any "
            "that it finds will appear here.\n\n"
            "When you click on a game that it found, the installer window will appear to "
            "perform the installation."
        )

        self.search_explanation_label = self._get_explanation_label(explanation)
        vbox.add(self.search_explanation_label)

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
        self.set_page_title_markup(_("<b>Search Lutris.net</b>"))
        self.stack.present_page("search_installers")
        self.search_entry.grab_focus()
        self.display_cancel_button()

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
            self.search_result_label.set_markup(_("No results"))
        elif count == total_count:
            self.search_result_label.set_markup(_(f"Showing <b>{count}</b> results"))
        else:
            self.search_result_label.set_markup(_(f"<b>{total_count}</b> results, only displaying first {count}"))
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
        self.search_result_label.show()
        self.search_frame.show()
        self.search_explanation_label.hide()

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
        self.stack.navigate_to_page(self.present_scan_folder_page)

    def create_scan_folder_page(self):
        grid = Gtk.Grid(row_spacing=6, column_spacing=6)
        label = self._get_label(_("Folder to scan"))
        grid.attach(label, 0, 0, 1, 1)
        grid.attach(self.scan_directory_chooser, 1, 0, 1, 1)
        self.scan_directory_chooser.set_hexpand(True)

        explanation = _(
            "Lutris will search this folder for sub-folders that contain games it recognizes.\n\n"
            "Any games it finds that are not already in Lutris will be added.\n\n"
            "When you click 'Continue' below, the search will begin, and any games found will "
            "be added at once."
        )

        grid.attach(self._get_explanation_label(explanation), 0, 1, 2, 1)
        return grid

    def present_scan_folder_page(self):
        self.set_page_title_markup("<b>Select folder to scan for games</b>")
        self.stack.present_page("scan_folder")
        self.display_continue_button(self.on_continue_scan_folder_clicked)

    @watch_errors()
    def on_continue_scan_folder_clicked(self, _widget):
        path = self.scan_directory_chooser.get_text()
        if not path:
            ErrorDialog(_("You must select a folder to scan for games."), parent=self)
        elif not os.path.isdir(path):
            ErrorDialog(_("No folder exists at '%s'.") % path, parent=self)
        else:
            self.load_scanning_folder_page(path)

    # Scanning Folder Page

    def load_scanning_folder_page(self, path):
        def present_scanning_folder_page():
            self.set_page_title_markup("<b>Importing games from a folder</b>")
            self.stack.present_page("scanning_folder")
            self.display_no_continue_button()
            AsyncCall(scan_directory, self._on_folder_scanned, path)

        self.stack.jump_to_page(present_scanning_folder_page)

    def create_scanning_folder_page(self):
        spinner = Gtk.Spinner()
        spinner.start()
        return spinner

    @watch_errors()
    def _on_folder_scanned(self, result, error):
        def present_installed_games_page():
            if installed or missing:
                self.set_page_title_markup(_("<b>Games found</b>"))
            else:
                self.set_page_title_markup(_("<b>No games found</b>"))

            page = self.create_installed_games_page(installed, missing)
            self.stack.present_replacement_page("installed_games", page)
            self.display_cancel_button(label=_("_Close"))

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

    # Install from Setup Page

    def install_from_setup(self):
        """Install from a setup file"""
        self.stack.navigate_to_page(self.present_install_from_setup_page)

    def create_install_from_setup_page(self):
        name_label = self._get_label(_("Game name"))

        self.install_from_setup_game_name_entry.set_hexpand(True)
        self.install_from_setup_game_slug_entry.set_hexpand(True)

        grid = Gtk.Grid(row_spacing=6, column_spacing=6)
        grid.set_column_homogeneous(False)
        grid.attach(name_label, 0, 0, 1, 1)
        grid.attach(self.install_from_setup_game_name_entry, 1, 0, 1, 1)
        grid.attach(self.install_from_setup_game_slug_checkbox, 0, 1, 1, 1)
        grid.attach(self.install_from_setup_game_slug_entry, 1, 1, 1, 1)

        self.install_from_setup_game_name_entry.connect("changed", self.on_install_from_setup_game_name_changed)
        self.install_from_setup_game_slug_checkbox.connect("toggled", self.on_install_from_setup_game_slug_toggled)

        explanation = _(
            "Enter the name of the game you will install.\n\nWhen you click 'Install' below, "
            "the installer window will appear and guide you through a simple installation.\n\n"
            "It will prompt you for a setup executable, and will use Wine to install it.\n\n"
            "If you know the Lutris identifier for the game, you can provide it for improved "
            "Lutris integration, such as Lutris provided banners."
        )

        grid.attach(self._get_explanation_label(explanation), 0, 2, 2, 1)

        if LINUX_SYSTEM.is_64_bit:
            self.install_from_setup_32bit_prefix_checkbox = Gtk.CheckButton(
                label=_("32-bit Wine prefix"))

            grid.attach(self.install_from_setup_32bit_prefix_checkbox, 0, 3, 2, 1)
            self.install_from_setup_32bit_prefix_checkbox.set_valign(Gtk.Align.END)
            self.install_from_setup_32bit_prefix_checkbox.set_vexpand(True)
        grid.set_vexpand(True)
        return grid

    def present_install_from_setup_page(self):
        self.set_page_title_markup(_("<b>Select setup file</b>"))
        self.stack.present_page("install_from_setup")
        self.display_continue_button(self._on_install_setup_continue, label=_("_Install"))

    @watch_errors()
    def on_install_from_setup_game_slug_toggled(self, checkbutton):
        self.install_from_setup_game_slug_entry.set_sensitive(checkbutton.get_active())
        self.on_install_from_setup_game_name_changed()

    @watch_errors()
    def on_install_from_setup_game_name_changed(self, *_args):
        if not self.install_from_setup_game_slug_checkbox.get_active():
            name = self.install_from_setup_game_name_entry.get_text()
            self.install_from_setup_game_slug_entry.set_text(slugify(name))

    @watch_errors()
    def _on_install_setup_continue(self, button):
        name = self.install_from_setup_game_name_entry.get_text().strip()

        if not name:
            ErrorDialog(_("You must provide a name for the game you are installing."), parent=self)
            return

        if self.install_from_setup_game_slug_checkbox.get_active():
            game_slug = self.install_from_setup_game_slug_entry.get_text()
        else:
            game_slug = slugify(name)

        if (self.install_from_setup_32bit_prefix_checkbox
                and not self.install_from_setup_32bit_prefix_checkbox.get_active()):
            arch = "win64"
        else:
            arch = "win32"

        installer = {
            "name": name,
            "version": _("Setup file"),
            "slug": game_slug + "-setup",
            "game_slug": game_slug,
            "runner": "wine",
            "script": {
                "game": {
                    "exe": AUTO_WIN32_EXE, "prefix": "$GAMEDIR"
                },
                "files": [
                    {"setupfile": "N/A:%s" % _("Select the setup file")}
                ],
                "installer": [
                    {"task": {"name": "wineexec", "executable": "setupfile", "arch": arch}}
                ]
            }
        }
        application = Gio.Application.get_default()
        application.show_installer_window([installer])
        self.destroy()

    # Install from Script Page

    def install_from_script(self):
        """Install from a YAML file"""
        self.stack.navigate_to_page(self.present_install_from_script_page)

    def create_install_from_script_page(self):
        grid = Gtk.Grid(row_spacing=6, column_spacing=6)
        label = self._get_label(_("Script file"))
        grid.attach(label, 0, 0, 1, 1)
        grid.attach(self.install_script_file_chooser, 1, 0, 1, 1)
        self.install_script_file_chooser.set_hexpand(True)

        explanation = _(
            "Lutris install scripts are YAML files that guide Lutris through "
            "the installation process.\n\n"
            "They can be obtained on Lutris.net, or written by hand.\n\n"
            "When you click 'Install' below, the installer window will "
            "appear and load the script, and it will guide the process from there."
        )

        grid.attach(self._get_explanation_label(explanation), 0, 1, 2, 1)
        return grid

    def present_install_from_script_page(self):
        self.set_page_title_markup("<b>Select a Lutris installer</b>")
        self.stack.present_page("install_from_script")
        self.display_continue_button(self.on_continue_install_from_script_clicked, label=_("_Install"))

    @watch_errors()
    def on_continue_install_from_script_clicked(self, _widget):
        path = self.install_script_file_chooser.get_text()
        if not path:
            ErrorDialog(_("You must select a script file to install."), parent=self)
        elif not os.path.isfile(path):
            ErrorDialog(_("No file exists at '%s'.") % path, parent=self)
        else:
            installers = get_installers(installer_file=path)
            application = Gio.Application.get_default()
            application.show_installer_window(installers)
            self.destroy()

    # Install ROM Page

    def import_rom(self):
        """Install from a YAML file"""
        self.stack.navigate_to_page(self.present_import_rom_page)

    def create_import_rom_page(self):
        grid = Gtk.Grid(row_spacing=6, column_spacing=6)
        label = self._get_label(_("ROM file"))
        grid.attach(label, 0, 0, 1, 1)
        grid.attach(self.import_rom_file_chooser, 1, 0, 1, 1)
        self.import_rom_file_chooser.set_hexpand(True)

        explanation = _(
            "Lutris will identify a ROM via its MD5 hash and download game "
            "information from Lutris.net.\n\n"
            "The ROM data used for this comes from the TOSEC project.\n\n"
            "When you click 'Install' below, the process of installing the game will "
            "begin."
        )

        grid.attach(self._get_explanation_label(explanation), 0, 1, 2, 1)
        return grid

    def present_import_rom_page(self):
        self.set_page_title_markup("<b>Select a ROM file</b>")
        self.stack.present_page("import_rom")
        self.display_continue_button(self.on_continue_import_rom_clicked, label=_("_Install"))

    @watch_errors()
    def on_continue_import_rom_clicked(self, _widget):
        path = self.import_rom_file_chooser.get_text()
        if not path:
            ErrorDialog(_("You must select a ROM file to install."), parent=self)
        elif not os.path.isfile(path):
            ErrorDialog(_("No file exists at '%s'.") % path, parent=self)
        else:
            application = Gio.Application.get_default()
            dialog = ImportGameDialog([path], parent=application.window)
            dialog.show()
            self.destroy()

    # Add Local Game

    def add_local_game(self):
        """Manually configure game"""
        AddGameDialog(parent=self)
        GLib.idle_add(self.destroy)  # defer destory so the game dialog can be centered first

    # Subtitle Label

    def set_page_title_markup(self, markup):
        """Places some text at the top of the page; set markup to 'None' to remove it."""
        if markup:
            self.page_title_label.set_markup(markup)
            self.page_title_label.show()
        else:
            self.page_title_label.hide()

    # Continue Button

    def display_continue_button(self, handler, label=_("_Continue"), suggested_action=True):
        self.continue_button.set_label(label)
        style_context = self.continue_button.get_style_context()

        if suggested_action:
            style_context.add_class("suggested-action")
        else:
            style_context.remove_class("suggested-action")

        if self.continue_handler:
            self.continue_button.disconnect(self.continue_handler)

        self.continue_handler = self.continue_button.connect("clicked", handler)

        self.continue_button.show()
        self.cancel_button.set_label(_("Cancel"))
        self.stack.set_cancel_allowed(True)

    def display_cancel_button(self, label=_("Cancel")):
        self.cancel_button.set_label(label)
        self.stack.set_cancel_allowed(True)
        self.continue_button.hide()

    def display_no_continue_button(self):
        self.continue_button.hide()
        self.stack.set_cancel_allowed(False)

        if self.continue_handler:
            self.continue_button.disconnect(self.continue_handler)
            self.continue_handler = None

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

    def _get_explanation_label(self, markup):
        label = Gtk.Label(
            visible=True,
            margin_right=12,
            margin_left=12,
            margin_top=12,
            margin_bottom=12)
        label.set_markup(markup)
        label.set_line_wrap(True)
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
