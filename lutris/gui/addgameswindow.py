import os
from gettext import gettext as _
from gettext import ngettext

from gi.repository import GdkPixbuf, Gio, Gtk

from lutris import sysoptions
from lutris.config import LutrisConfig
from lutris.gui.config.add_game_dialog import AddGameDialog
from lutris.gui.dialogs import ErrorDialog, ModelessDialog
from lutris.gui.dialogs.game_import import ImportGameDialog
from lutris.gui.widgets.common import FileChooserEntry
from lutris.gui.widgets.navigation_stack import NavigationStack
from lutris.installer import AUTO_WIN32_EXE
from lutris.scanners import playtron as playtron_scanner
from lutris.util import datapath
from lutris.util.jobs import AsyncCall
from lutris.util.strings import slugify
from lutris.util.wine.proton import is_proton_version
from lutris.util.wine.wine import GE_PROTON_LATEST


class AddGamesWindow(ModelessDialog):  # pylint: disable=too-many-public-methods
    """Show a selection of ways to add games to Lutris"""

    sections = [
        (
            "application-x-executable-symbolic",
            "go-next-symbolic",
            _("Install a Windows game from an executable"),
            _("Launch a Windows executable (.exe) installer"),
            "install_from_setup",
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
        self.cancel_button.add_accelerator("clicked", self.accelerators, key, mod, Gtk.AccelFlags.VISIBLE)
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
        self.install_from_setup_game_slug_checkbox = Gtk.CheckButton(label=_("Identifier"))
        self.install_from_setup_game_slug_entry = Gtk.Entry(sensitive=False)
        self.install_from_setup_game_slug_entry.connect(
            "focus-out-event", self.on_install_from_setup_game_slug_entry_focus_out
        )
        self.installer_presets = Gtk.ListStore(str, str)
        self.install_preset_dropdown = Gtk.ComboBox.new_with_model(self.installer_presets)
        self.installer_locale = Gtk.ListStore(str, str)
        self.install_locale_dropdown = Gtk.ComboBox.new_with_model(self.installer_locale)

        self.import_rom_file_chooser = FileChooserEntry(
            title=_("Select ROMs"), action=Gtk.FileChooserAction.SELECT_FOLDER
        )

        self.import_playtron_result_label = Gtk.Label()

        self.stack.add_named_factory("initial", self.create_initial_page)
        self.stack.add_named_factory("install_from_setup", self.create_install_from_setup_page)
        self.stack.add_named_factory("import_rom", self.create_import_rom_page)
        self.stack.add_named_factory("import_playtron", self.create_import_playtron_page)

        self.show_all()

        self.load_initial_page()

    def on_back_clicked(self, _widget):
        self.stack.navigate_back()

    def on_navigate_home(self, _accel_group, _window, _keyval, _modifier):
        self.stack.navigate_home()

    def on_cancel_clicked(self, _widget):
        self.destroy()

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

    def on_row_activated(self, listbox, row):
        if row.callback_name:
            callback = getattr(self, row.callback_name)
            callback()

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

        self.installer_presets.append(["win11", _("Windows 11 64-bit")])
        self.installer_presets.append(["win10", _("Windows 10 64-bit (Default)")])
        self.installer_presets.append(["win7", _("Windows 7 64-bit")])

        wine_version = LutrisConfig(runner_slug="wine").runner_config.get("version")
        if wine_version != GE_PROTON_LATEST and not is_proton_version(wine_version):
            self.installer_presets.append(["winxp", _("Windows XP 32-bit")])
            self.installer_presets.append(["win98", _("Windows 98 32-bit")])

        renderer_text = Gtk.CellRendererText()
        self.install_preset_dropdown.pack_start(renderer_text, True)
        self.install_preset_dropdown.add_attribute(renderer_text, "text", 1)
        self.install_preset_dropdown.set_id_column(0)
        self.install_preset_dropdown.set_active_id("win10")

        grid.attach(self.install_preset_dropdown, 1, 3, 1, 1)
        self.install_preset_dropdown.set_halign(Gtk.Align.START)

        locale_label = Gtk.Label(label=_("Locale:"), visible=True)
        locale_label.set_xalign(0)
        grid.attach(locale_label, 0, 4, 1, 1)

        locale_list = sysoptions.get_locale_choices()
        for locale_humanized, locale in locale_list:
            self.installer_locale.append([locale, _(locale_humanized)])

        locale_renderer_text = Gtk.CellRendererText()
        self.install_locale_dropdown.pack_start(locale_renderer_text, True)
        self.install_locale_dropdown.add_attribute(locale_renderer_text, "text", 1)
        self.install_locale_dropdown.set_id_column(0)
        self.install_locale_dropdown.set_active(0)

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

        installer_preset = self.installer_presets[self.install_preset_dropdown.get_active()][0]
        arch = "win32" if installer_preset.startswith(("win98", "winxp")) else "win64"
        win_ver = installer_preset.split("-")[0]
        if win_ver != "win10":
            win_ver_task = {"task": {"name": "winetricks", "app": win_ver, "arch": arch}}
        else:
            win_ver_task = None

        locale_selected = self.installer_locale[self.install_locale_dropdown.get_active()][0]

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

    # Install ROM Page

    def import_rom(self):
        """Open the ROM import page."""
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
            dialog.show()
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
        AddGameDialog(parent=application.window)
        self.destroy()

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
            pixel_size = 16
        else:
            size = Gtk.IconSize.DND
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
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_path, pixel_size, pixel_size)
                icon = Gtk.Image.new_from_pixbuf(pixbuf)
                icon.show()
                return icon

        icon = Gtk.Image.new_from_icon_name(name, size)
        icon.show()
        return icon

    def _get_label(self, text):
        label = Gtk.Label(visible=True)
        label.set_markup(text)
        label.set_alignment(0, 0.5)
        return label

    def _get_explanation_label(self, markup):
        label = Gtk.Label(visible=True, margin_right=12, margin_left=12, margin_top=12, margin_bottom=12)
        label.set_markup(markup)
        label.set_line_wrap(True)
        return label

    def _get_listbox_row(self, left_icon_name, text, subtext, right_icon_name=""):
        row = Gtk.ListBoxRow(visible=True)
        row.set_selectable(False)
        row.set_activatable(True)

        box = Gtk.Box(spacing=12, margin_right=12, margin_left=12, margin_top=12, margin_bottom=12, visible=True)

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
