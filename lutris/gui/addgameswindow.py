import os
from gettext import gettext as _
from gettext import ngettext

from gi.repository import Gdk, Gio, Gtk

from lutris import api, sysoptions
from lutris.config import LutrisConfig
from lutris.gui.config.add_game_dialog import AddGameDialog
from lutris.gui.dialogs import ErrorDialog, ModelessDialog
from lutris.gui.dialogs.game_import import ImportGameDialog
from lutris.gui.widgets.common import FileChooserEntry, KeyValueDropDown
from lutris.gui.widgets.navigation_stack import NavigationStack
from lutris.installer import AUTO_WIN32_EXE, get_installers
from lutris.scanners import playtron as playtron_scanner
from lutris.util import datapath
from lutris.util.jobs import COMPLETED_IDLE_TASK, AsyncCall, schedule_at_idle
from lutris.util.strings import gtk_safe, slugify
from lutris.util.wine.proton import is_proton_version
from lutris.util.wine.wine import GE_PROTON_LATEST


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
            "application-x-executable-symbolic",
            "go-next-symbolic",
            _("Install a Windows game from an executable"),
            _("Launch a Windows executable (.exe) installer"),
            "install_from_setup",
        ),
        (
            "x-office-document-symbolic",
            "go-next-symbolic",
            _("Install from a local install script"),
            _("Run a YAML install script"),
            "install_from_script",
        ),
        (
            "application-x-firmware-symbolic",
            "go-next-symbolic",
            _("Import ROMs"),
            _("Import ROMs referenced in TOSEC, No-intro or Redump"),
            "import_rom",
        ),
        (
            "media:playtron",
            "go-next-symbolic",
            _("Import from Playtron"),
            _("Import games installed via Playtron GameOS"),
            "import_playtron",
        ),
        (
            "list-add-symbolic",
            "view-more-horizontal-symbolic",
            _("Add locally installed game"),
            _("Manually configure a game available locally"),
            "add_local_game",
        ),
    ]

    def __init__(self, **kwargs):
        ModelessDialog.__init__(self, title=_("Add games to Lutris"), use_header_bar=True, **kwargs)
        self.set_default_size(640, 450)
        self.search_entry = None
        self.search_frame = None
        self.search_explanation_label = None
        self.search_listbox = None
        self.search_timer_task = COMPLETED_IDLE_TASK
        self.search_spinner = None
        self.text_query = None
        self.search_result_label = None

        content_area = self.get_content_area()

        self.page_title_label = Gtk.Label(visible=True)
        content_area.append(self.page_title_label)

        shortcut_controller = Gtk.ShortcutController()
        shortcut_controller.set_scope(Gtk.ShortcutScope.LOCAL)
        shortcut_controller.add_shortcut(Gtk.Shortcut(
            trigger=Gtk.ShortcutTrigger.parse_string("<Alt>Left"),
            action=Gtk.CallbackAction.new(lambda w, _: self.on_back_clicked(None)),
        ))
        shortcut_controller.add_shortcut(Gtk.Shortcut(
            trigger=Gtk.ShortcutTrigger.parse_string("<Alt>Home"),
            action=Gtk.CallbackAction.new(lambda w, _: self.on_navigate_home()),
        ))
        self.add_controller(shortcut_controller)

        header_bar = self.get_header_bar()

        self.back_button = Gtk.Button(label=_("Back"), visible=False)
        self.back_button.connect("clicked", self.on_back_clicked)
        header_bar.pack_start(self.back_button)

        self.continue_button = Gtk.Button(label=_("_Continue"), visible=False, use_underline=True)
        header_bar.pack_end(self.continue_button)
        self.continue_handler = None

        self.cancel_button = Gtk.Button(label=_("Cancel"), use_underline=True)
        self.cancel_button.connect("clicked", self.on_cancel_clicked)
        header_bar.pack_start(self.cancel_button)
        header_bar.set_show_title_buttons(False)

        content_area.set_margin_top(18)
        content_area.set_margin_bottom(18)
        content_area.set_margin_end(18)
        content_area.set_margin_start(18)
        content_area.set_spacing(12)

        self.stack = NavigationStack(self.back_button, cancel_button=self.cancel_button)
        self.stack.set_vexpand(True)
        content_area.append(self.stack)

        # Pre-create some controls so they can be used in signal handlers

        self.scan_directory_chooser = FileChooserEntry(
            title=_("Select folder"), action=Gtk.FileChooserAction.SELECT_FOLDER
        )

        self.install_from_setup_game_name_entry = Gtk.Entry()
        self.install_from_setup_game_slug_checkbox = Gtk.CheckButton(label=_("Identifier"))
        self.install_from_setup_game_slug_entry = Gtk.Entry(sensitive=False)
        focus_controller = Gtk.EventControllerFocus()
        focus_controller.connect("leave", self.on_install_from_setup_game_slug_entry_focus_out)
        self.install_from_setup_game_slug_entry.add_controller(focus_controller)
        self.install_preset_dropdown = KeyValueDropDown()
        self.install_locale_dropdown = KeyValueDropDown()

        self.install_script_file_chooser = FileChooserEntry(title=_("Select script"), action=Gtk.FileChooserAction.OPEN)

        self.import_rom_file_chooser = FileChooserEntry(
            title=_("Select ROMs"), action=Gtk.FileChooserAction.SELECT_FOLDER
        )

        self.import_playtron_result_label = Gtk.Label()

        self.stack.add_named_factory("initial", self.create_initial_page)
        self.stack.add_named_factory("search_installers", self.create_search_installers_page)
        self.stack.add_named_factory("install_from_setup", self.create_install_from_setup_page)
        self.stack.add_named_factory("install_from_script", self.create_install_from_script_page)
        self.stack.add_named_factory("import_rom", self.create_import_rom_page)
        self.stack.add_named_factory("import_playtron", self.create_import_playtron_page)

        self.present()

        self.load_initial_page()

    def on_back_clicked(self, _widget):
        self.stack.navigate_back()

    def on_navigate_home(self):
        self.stack.navigate_home()

    def on_cancel_clicked(self, _widget):
        self.destroy()

    # Initial Page

    def load_initial_page(self):
        self.stack.navigate_to_page(self.present_inital_page)

    def create_initial_page(self):
        frame = Gtk.Frame()
        listbox = Gtk.ListBox()
        listbox.set_activate_on_single_click(True)
        for icon, next_icon, text, subtext, callback_name in self.sections:
            row = self._get_listbox_row(icon, text, subtext, next_icon)
            row.callback_name = callback_name

            listbox.append(row)
        listbox.connect("row-activated", self.on_row_activated)
        frame.set_child(listbox)
        return frame

    def present_inital_page(self):
        self.set_page_title_markup(None)
        self.stack.present_page("initial")
        self.display_cancel_button()

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
            self.search_result_label.set_visible(False)
            self.search_frame.set_visible(False)
            self.search_explanation_label.set_visible(True)
        self.stack.navigate_to_page(self.present_search_installers_page)

    def create_search_installers_page(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, visible=True)
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, visible=True)
        self.search_entry = Gtk.SearchEntry(visible=True)
        self.search_entry.set_hexpand(True)
        hbox.append(self.search_entry)
        self.search_spinner = Gtk.Spinner(visible=False)
        self.search_spinner.set_margin_start(6)
        hbox.append(self.search_spinner)
        vbox.append(hbox)
        self.search_result_label = self._get_label("")
        self.search_result_label.set_visible(False)
        vbox.append(self.search_result_label)
        self.search_entry.connect("changed", self._on_search_updated)

        explanation = _(
            "Lutris will search Lutris.net for games matching the terms you enter, and any "
            "that it finds will appear here.\n\n"
            "When you click on a game that it found, the installer window will appear to "
            "perform the installation."
        )

        self.search_explanation_label = self._get_explanation_label(explanation)
        vbox.append(self.search_explanation_label)

        self.search_frame = Gtk.Frame()
        self.search_listbox = Gtk.ListBox(visible=True)
        self.search_listbox.connect("row-activated", self._on_game_selected)
        scroll = Gtk.ScrolledWindow(visible=True)
        scroll.set_vexpand(True)
        scroll.set_child(self.search_listbox)
        self.search_frame.set_child(scroll)

        self.search_frame.set_vexpand(True)
        vbox.append(self.search_frame)
        return vbox

    def present_search_installers_page(self):
        self.set_page_title_markup(_("<b>Search Lutris.net</b>"))
        self.stack.present_page("search_installers")
        self.search_entry.grab_focus()
        self.display_cancel_button()

    def _on_search_updated(self, entry):
        self.search_timer_task.unschedule()
        self.text_query = entry.get_text().strip()
        self.search_timer_task = schedule_at_idle(self.update_search_results, delay_seconds=0.75)

    def update_search_results(self) -> None:
        # Don't start a search while another is going; defer it instead.
        if self.search_spinner.get_visible():
            self.search_timer_task = schedule_at_idle(self.update_search_results, delay_seconds=0.75)
            return

        if self.text_query:
            self.search_spinner.set_visible(True)
            self.search_spinner.start()
            AsyncCall(api.search_games, self.update_search_results_cb, self.text_query)

    def update_search_results_cb(self, api_games, error):
        if error:
            raise error

        self.search_spinner.stop()
        self.search_spinner.set_visible(False)
        total_count = api_games.get("count", 0)
        count = len(api_games.get("results", []))

        if not count:
            self.search_result_label.set_markup(_("No results"))
        elif count == total_count:
            text = ngettext("Showing <b>%d</b> result", "Showing <b>%d</b> results", count) % count
            self.search_result_label.set_markup(text)
        else:
            self.search_result_label.set_markup(_("<b>%s</b> results, only displaying first %s") % (total_count, count))
        child = self.search_listbox.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.search_listbox.remove(child)
            child = next_child
        for game in api_games.get("results", []):
            platforms = ",".join(gtk_safe(platform["name"]) for platform in game["platforms"])
            year = game["year"] or ""
            if platforms and year:
                platforms = ", " + platforms

            row = self._get_listbox_row("", gtk_safe(game["name"]), f"{year}{platforms}")
            row.api_info = game
            self.search_listbox.append(row)
        self.search_result_label.set_visible(True)
        self.search_frame.set_visible(True)
        self.search_explanation_label.set_visible(False)

    def _on_game_selected(self, listbox, row):
        game_slug = row.api_info["slug"]
        application = Gio.Application.get_default()
        application.show_lutris_installer_window(game_slug=game_slug)
        self.destroy()

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

        preset_label = Gtk.Label(label=_("Installer preset:"), visible=True)
        grid.attach(preset_label, 0, 3, 1, 1)

        self.install_preset_dropdown.append("win11", _("Windows 11 64-bit"))
        self.install_preset_dropdown.append("win10", _("Windows 10 64-bit (Default)"))
        self.install_preset_dropdown.append("win7", _("Windows 7 64-bit"))

        wine_version = LutrisConfig(runner_slug="wine").runner_config.get("version")
        if wine_version != GE_PROTON_LATEST and not is_proton_version(wine_version):
            self.install_preset_dropdown.append("winxp", _("Windows XP 32-bit"))
            self.install_preset_dropdown.append("win98", _("Windows 98 32-bit"))

        self.install_preset_dropdown.set_active_id("win10")

        grid.attach(self.install_preset_dropdown, 1, 3, 1, 1)
        self.install_preset_dropdown.set_halign(Gtk.Align.START)

        locale_label = Gtk.Label(label=_("Locale:"), visible=True)
        locale_label.set_xalign(0)
        grid.attach(locale_label, 0, 4, 1, 1)

        locale_list = sysoptions.get_locale_choices()
        for locale_humanized, locale in locale_list:
            self.install_locale_dropdown.append(locale, _(locale_humanized))

        self.install_locale_dropdown.set_selected(0)

        grid.attach(self.install_locale_dropdown, 1, 4, 1, 1)
        self.install_locale_dropdown.set_halign(Gtk.Align.START)

        grid.set_vexpand(True)
        return grid

    def on_install_from_setup_game_slug_entry_focus_out(self, *args):
        slug = slugify(self.install_from_setup_game_slug_entry.get_text())
        self.install_from_setup_game_slug_entry.set_text(slug)

    def present_install_from_setup_page(self):
        self.set_page_title_markup(_("<b>Select setup file</b>"))
        self.stack.present_page("install_from_setup")
        self.display_continue_button(self._on_install_setup_continue, label=_("_Install"))

    def on_install_from_setup_game_slug_toggled(self, checkbutton):
        self.install_from_setup_game_slug_entry.set_sensitive(checkbutton.get_active())
        self.on_install_from_setup_game_name_changed()

    def on_install_from_setup_game_name_changed(self, *_args):
        if not self.install_from_setup_game_slug_checkbox.get_active():
            name = self.install_from_setup_game_name_entry.get_text()
            proposed_slug = slugify(name) if name else ""
            self.install_from_setup_game_slug_entry.set_text(proposed_slug)

    def _on_install_setup_continue(self, button):
        name = self.install_from_setup_game_name_entry.get_text().strip()

        if not name:
            ErrorDialog(_("You must provide a name for the game you are installing."), parent=self)
            return

        if self.install_from_setup_game_slug_checkbox.get_active():
            game_slug = slugify(self.install_from_setup_game_slug_entry.get_text())
        else:
            game_slug = slugify(name)

        installer_preset = self.install_preset_dropdown.get_active_id() or "win10"
        arch = "win32" if installer_preset.startswith(("win98", "winxp")) else "win64"
        win_ver = installer_preset.split("-")[0]
        if win_ver != "win10":
            win_ver_task = {"task": {"name": "winetricks", "app": win_ver, "arch": arch}}
        else:
            win_ver_task = None

        locale_selected = self.install_locale_dropdown.get_active_id() or ""

        installer = {
            "name": name,
            "version": _("Setup file"),
            "slug": game_slug + "-setup",
            "game_slug": game_slug,
            "runner": "wine",
            "script": {
                "game": {"exe": AUTO_WIN32_EXE, "prefix": "$GAMEDIR"},
                "files": [{"setupfile": "N/A:%s" % _("Select the setup file")}],
                "installer": [{"task": {"name": "wineexec", "executable": "setupfile", "arch": arch}}],
                "system": {"env": {"LC_ALL": locale_selected}},
            },
        }
        if win_ver_task:
            installer["script"]["installer"].insert(0, win_ver_task)
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
        self.set_page_title_markup(_("<b>Select a Lutris installer</b>"))
        self.stack.present_page("install_from_script")
        self.display_continue_button(self.on_continue_install_from_script_clicked, label=_("_Install"))

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
            "Lutris will identify ROMs via its MD5 hash and download game "
            "information from Lutris.net.\n\n"
            "The ROM data used for this comes from  TOSEC, No-Intro and Redump projects.\n\n"
            "When you click 'Install' below, the process of installing the games will "
            "begin."
        )

        grid.attach(self._get_explanation_label(explanation), 0, 1, 2, 1)
        return grid

    def present_import_rom_page(self):
        self.set_page_title_markup(_("<b>Select ROMs</b>"))
        self.stack.present_page("import_rom")
        self.display_continue_button(self.on_continue_import_rom_clicked, label=_("_Install"))

    def on_continue_import_rom_clicked(self, _widget):
        paths = []
        for path, _dirs, files in os.walk(self.import_rom_file_chooser.get_text()):
            for file in files:
                paths.append(os.path.join(path, file))

        if not paths:
            ErrorDialog(_("You must select ROMs to install."), parent=self)
        else:
            application = Gio.Application.get_default()
            dialog = ImportGameDialog(paths, parent=application.window)
            dialog.present()
            self.destroy()

    # Import Playtron Page

    def import_playtron(self):
        """Import games from Playtron GameOS"""
        self.stack.navigate_to_page(self.present_import_playtron_page)

    def create_import_playtron_page(self):
        grid = Gtk.Grid(row_spacing=6, column_spacing=6)
        grid.set_valign(Gtk.Align.START)

        explanation = _("Import games installed via Playtron GameOS.")

        grid.attach(self._get_explanation_label(explanation), 0, 0, 1, 1)

        # Result label for showing import progress/results
        self.import_playtron_result_label.set_xalign(0)
        grid.attach(self.import_playtron_result_label, 0, 1, 1, 1)

        return grid

    def present_import_playtron_page(self):
        self.set_page_title_markup(_("<b>Import from Playtron</b>"))
        self.stack.present_page("import_playtron")
        self.import_playtron_result_label.set_text("")
        self.display_continue_button(self.on_continue_import_playtron_clicked, label=_("_Import"))

    def on_continue_import_playtron_clicked(self, _widget):
        """Start the Playtron import process"""
        self.import_playtron_result_label.set_text(_("Scanning for games..."))
        self.continue_button.set_sensitive(False)
        self.back_button.set_sensitive(False)
        self.cancel_button.set_sensitive(False)
        AsyncCall(playtron_scanner.scan_all_libraries, self.on_playtron_import_complete)

    def on_playtron_import_complete(self, result, error):
        """Handle completion of Playtron import"""
        self.back_button.set_sensitive(True)
        self.cancel_button.set_sensitive(True)

        if error:
            self.import_playtron_result_label.set_text(_("Error during import: %s") % str(error))
            self.continue_button.set_sensitive(True)
            return

        game_ids = result or []
        count = len(game_ids)

        if count == 0:
            self.import_playtron_result_label.set_text(_("No new games found to import."))
        else:
            self.import_playtron_result_label.set_text(
                ngettext("Successfully imported %d game.", "Successfully imported %d games.", count) % count
            )
            # Refresh the game library
            application = Gio.Application.get_default()
            if application and hasattr(application, "window"):
                application.window.refresh_view()

        self.continue_button.set_sensitive(True)
        self.display_continue_button(lambda _w: self.destroy(), label=_("_Close"), suggested_action=False)

    # Add Local Game

    def add_local_game(self):
        """Manually configure game"""
        # We use the LutrisWindow as the parent because we would
        # destroy this window before the AddGameDialog could disconnect.
        # We've tried to be clever here, but it didn't work reliably.
        # This does center the AddGameDialog over the main window, which
        # isn't terrible.
        application = Gio.Application.get_default()
        AddGameDialog(parent=application.window).present()
        self.destroy()

    # Subtitle Label

    def set_page_title_markup(self, markup):
        """Places some text at the top of the page; set markup to 'None' to remove it."""
        if markup:
            self.page_title_label.set_markup(markup)
            self.page_title_label.set_visible(True)
        else:
            self.page_title_label.set_visible(False)

    # Continue Button

    def display_continue_button(self, handler, label=_("_Continue"), suggested_action=True):
        self.continue_button.set_label(label)

        if suggested_action:
            self.continue_button.add_css_class("suggested-action")
        else:
            self.continue_button.remove_css_class("suggested-action")

        if self.continue_handler:
            self.continue_button.disconnect(self.continue_handler)

        self.continue_handler = self.continue_button.connect("clicked", handler)

        self.continue_button.set_visible(True)
        self.cancel_button.set_label(_("Cancel"))
        self.stack.set_cancel_allowed(True)

    def display_cancel_button(self, label=_("Cancel")):
        self.cancel_button.set_label(label)
        self.stack.set_cancel_allowed(True)
        self.continue_button.set_visible(False)

    def display_no_continue_button(self):
        self.continue_button.set_visible(False)
        self.stack.set_cancel_allowed(False)

        if self.continue_handler:
            self.continue_button.disconnect(self.continue_handler)
            self.continue_handler = None

    # Implementation

    def _get_icon(self, name, small=False):
        if small:
            pixel_size = 16
        else:
            pixel_size = 32

        # Check if it's a media file reference (e.g., "media:playtron")
        if name.startswith("media:"):
            media_name = name[6:]
            # Pick themed variant based on dark/light mode
            application = Gio.Application.get_default()
            theme_suffix = "dark"
            if application and hasattr(application, "style_manager"):
                theme_suffix = "dark" if application.style_manager.is_dark else "light"
            icon_path = os.path.join(datapath.get(), "media", f"{media_name}-{theme_suffix}.svg")
            if not os.path.exists(icon_path):
                icon_path = os.path.join(datapath.get(), "media", f"{media_name}.svg")
            if os.path.exists(icon_path):
                texture = Gdk.Texture.new_from_filename(icon_path)
                icon = Gtk.Image.new_from_paintable(texture)
                icon.set_pixel_size(pixel_size)
                icon.set_visible(True)
                return icon

        icon = Gtk.Image.new_from_icon_name(name)
        if not small:
            icon.set_icon_size(Gtk.IconSize.LARGE)
        icon.set_pixel_size(pixel_size)
        return icon

    def _get_label(self, text):
        label = Gtk.Label(visible=True)
        label.set_markup(text)
        label.set_xalign(0)
        return label

    def _get_explanation_label(self, markup):
        label = Gtk.Label(visible=True, margin_end=12, margin_start=12, margin_top=12, margin_bottom=12)
        label.set_markup(markup)
        label.set_wrap(True)
        return label

    def _get_listbox_row(self, left_icon_name, text, subtext, right_icon_name=""):
        row = Gtk.ListBoxRow(visible=True)
        row.set_selectable(False)
        row.set_activatable(True)

        box = Gtk.Box(spacing=12, margin_end=12, margin_start=12, margin_top=12, margin_bottom=12, visible=True)

        if left_icon_name:
            icon = self._get_icon(left_icon_name)
            box.append(icon)
        label = self._get_label(f"<b>{text}</b>\n{subtext}")
        label.set_hexpand(True)
        box.append(label)
        if left_icon_name:
            next_icon = self._get_icon(right_icon_name, small=True)
            box.append(next_icon)
        row.set_child(box)
        return row
