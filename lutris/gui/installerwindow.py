"""Window used for game installers"""
import os
import time
import webbrowser

from gi.repository import Gtk

from lutris import api, pga, settings
from lutris.installer import interpreter
from lutris.installer.errors import ScriptingError, MissingGameDependency
from lutris.game import Game
from lutris.gui.config.add_game import AddGameDialog
from lutris.gui.dialogs import (
    NoInstallerDialog, DirectoryDialog, InstallerSourceDialog, QuestionDialog
)
from lutris.gui.widgets.common import FileChooserEntry, InstallerLabel
from lutris.gui.widgets.installer import InstallerPicker, InstallerFilesBox
from lutris.gui.widgets.log_text_view import LogTextView
from lutris.gui.widgets.window import BaseApplicationWindow

from lutris.util import jobs
from lutris.util import system
from lutris.util import xdgshortcuts
from lutris.util.log import logger
from lutris.util.strings import add_url_tags, gtk_safe


class InstallerWindow(BaseApplicationWindow):
    """GUI for the install process."""
    def __init__(
            self,
            game_slug=None,
            installer_file=None,
            revision=None,
            parent=None,
            application=None,
    ):
        super().__init__(application=application)

        self.install_in_progress = False
        self.interpreter = None
        self.parent = parent
        self.game_slug = game_slug
        self.revision = revision

        self.log_buffer = None
        self.log_textview = None

        self.title_label = InstallerLabel()
        self.vbox.add(self.title_label)

        self.status_label = InstallerLabel()
        self.status_label.set_max_width_chars(80)
        self.status_label.set_property("wrap", True)
        self.status_label.set_selectable(True)
        self.vbox.add(self.status_label)

        self.widget_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.vbox.pack_start(self.widget_box, True, True, 0)

        self.vbox.add(Gtk.HSeparator())

        self.action_buttons = Gtk.Box(spacing=6)
        action_buttons_alignment = Gtk.Alignment.new(1, 0, 0, 0)
        action_buttons_alignment.add(self.action_buttons)
        self.vbox.pack_start(action_buttons_alignment, False, True, 0)

        self.cancel_button = self.add_button("C_ancel", self.cancel_installation,
                                             tooltip="Abort and revert the installation")
        self.eject_button = self.add_button("_Eject", self.on_eject_clicked)
        self.source_button = self.add_button("_View source", self.on_source_clicked)
        self.install_button = self.add_button("_Install", self.on_install_clicked)
        self.continue_button = self.add_button("_Continue")
        self.play_button = self.add_button("_Launch", self.launch_game)
        self.close_button = self.add_button("_Close", self.on_destroy)

        self.continue_handler = None

        # check if installer is local or online
        if system.path_exists(installer_file):
            self.on_scripts_obtained(interpreter.read_script(installer_file))
        else:
            self.title_label.set_markup("Waiting for response from %s" % (settings.SITE_URL))
            self.add_spinner()
            self.widget_box.show()
            self.title_label.show()
            jobs.AsyncCall(
                interpreter.fetch_script,
                self.on_scripts_obtained,
                self.game_slug,
                self.revision,
            )
        self.present()

    def add_button(self, label, handler=None, tooltip=None):
        """Add a button to the action buttons box"""
        button = Gtk.Button.new_with_mnemonic(label)
        if tooltip:
            button.set_tooltip_text(tooltip)
        if handler:
            button.connect("clicked", handler)

        self.action_buttons.add(button)
        return button

    def on_scripts_obtained(self, scripts, _error=None):
        """Continue the install process when the scripts are available"""
        if not scripts:
            self.destroy()
            self.run_no_installer_dialog()
            return

        if not isinstance(scripts, list):
            scripts = [scripts]
        self.clean_widgets()
        self.scripts = scripts
        self.show_all()
        self.close_button.hide()
        self.play_button.hide()
        self.install_button.hide()
        self.source_button.hide()
        self.eject_button.hide()
        self.continue_button.hide()
        self.install_in_progress = True

        self.choose_installer()

    def run_no_installer_dialog(self):
        """Open dialog for 'no script available' situation."""
        dlg = NoInstallerDialog(self)
        if dlg.result == dlg.MANUAL_CONF:
            game_data = pga.get_game_by_field(self.game_slug, "slug")

            if game_data and "slug" in game_data:
                # Game data already exist locally.
                game = Game(game_data["id"])
            else:
                # Try to load game data from remote.
                games = api.get_api_games([self.game_slug])

                if games and len(games) >= 1:
                    remote_game = games[0]
                    game_data = {
                        "name": remote_game["name"],
                        "slug": remote_game["slug"],
                        "year": remote_game["year"],
                        "updated": remote_game["updated"],
                        "steamid": remote_game["steamid"],
                    }
                    game = Game(pga.add_game(**game_data))
                else:
                    game = None
            AddGameDialog(self.parent, game=game)
        elif dlg.result == dlg.NEW_INSTALLER:
            webbrowser.open(settings.GAME_URL % self.game_slug)

    def validate_scripts(self):
        """Auto-fixes some script aspects and checks for mandatory fields"""
        for script in self.scripts:
            for item in ["description", "notes"]:
                script[item] = script.get(item) or ""
            for item in ["name", "runner", "version"]:
                if item not in script:
                    logger.error("Invalid script: %s", script)
                    raise ScriptingError('Missing field "%s" in install script' % item)

    def choose_installer(self):
        """Stage where we choose an install script."""
        self.validate_scripts()
        base_script = self.scripts[0]
        self.title_label.set_markup("<b>Install %s</b>" % gtk_safe(base_script["name"]))
        installer_picker = InstallerPicker(self.scripts)
        installer_picker.connect("installer-selected", self.on_installer_selected)
        scrolledwindow = Gtk.ScrolledWindow(
            hexpand=True,
            vexpand=True,
            child=installer_picker,
            visible=True
        )
        scrolledwindow.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        self.widget_box.pack_end(scrolledwindow, True, True, 10)

    def get_script_from_slug(self, script_slug):
        """Return a installer script from its slug, raise an error if one isn't found"""
        install_script = None
        for script in self.scripts:
            if script["slug"] == script_slug:
                install_script = script
        if not install_script:
            raise ValueError("Could not find script %s" % script_slug)
        return install_script

    def on_installer_selected(self, _widget, installer_slug):
        """Sets the script interpreter to the correct script then proceed to
        install folder selection.

        If the installed game depends on another one and it's not installed,
        prompt the user to install it and quit this installer.
        """
        self.clean_widgets()
        try:
            self.interpreter = interpreter.ScriptInterpreter(
                self.get_script_from_slug(installer_slug),
                self
            )
        except MissingGameDependency as ex:
            dlg = QuestionDialog(
                {
                    "question": "This game requires %s. Do you want to install it?" % ex.slug,
                    "title": "Missing dependency",
                }
            )
            if dlg.result == Gtk.ResponseType.YES:
                InstallerWindow(
                    game_slug=ex.slug,
                    parent=self.parent,
                    application=self.application,
                )
            self.destroy()
            return
        self.title_label.set_markup(
            u"<b>Installing {}</b>".format(
                gtk_safe(self.interpreter.installer.game_name)
            )
        )
        self.select_install_folder()

    def select_install_folder(self):
        """Stage where we select the install directory."""
        if self.interpreter.installer.creates_game_folder:
            self.set_message("Select installation directory")
            default_path = self.interpreter.get_default_target()
            self.set_install_destination(default_path)
        else:
            self.set_message("Click install to continue")
        if self.continue_handler:
            self.continue_button.disconnect(self.continue_handler)
        self.continue_button.hide()
        self.source_button.show()
        self.install_button.grab_focus()
        self.install_button.show()

    def on_target_changed(self, text_entry, _data=None):
        """Set the installation target for the game."""
        self.interpreter.target_path = os.path.expanduser(text_entry.get_text())

    def on_install_clicked(self, button):
        """Let the interpreter take charge of the next stages."""
        button.hide()
        self.source_button.hide()
        self.interpreter.connect("runners-installed", self.on_runners_ready)
        self.interpreter.launch_install()

    def set_install_destination(self, default_path=None):
        """Display the destination chooser."""
        self.install_button.set_visible(False)
        self.continue_button.show()
        self.continue_button.set_sensitive(False)
        location_entry = FileChooserEntry(
            "Select folder",
            Gtk.FileChooserAction.SELECT_FOLDER,
            path=default_path,
            warn_if_non_empty=True,
            warn_if_ntfs=True
        )
        location_entry.entry.connect("changed", self.on_target_changed)
        self.widget_box.pack_start(location_entry, False, False, 0)

    def ask_for_disc(self, message, callback, requires):
        """Ask the user to do insert a CD-ROM."""
        time.sleep(0.3)
        self.clean_widgets()
        label = InstallerLabel(message)
        label.show()
        self.widget_box.add(label)

        buttons_box = Gtk.Box()
        buttons_box.show()
        buttons_box.set_margin_top(40)
        buttons_box.set_margin_bottom(40)
        self.widget_box.add(buttons_box)

        autodetect_button = Gtk.Button(label="Autodetect")
        autodetect_button.connect("clicked", callback, requires)
        autodetect_button.grab_focus()
        autodetect_button.show()
        buttons_box.pack_start(autodetect_button, True, True, 40)

        browse_button = Gtk.Button(label="Browse…")
        callback_data = {"callback": callback, "requires": requires}
        browse_button.connect("clicked", self.on_browse_clicked, callback_data)
        browse_button.show()
        buttons_box.pack_start(browse_button, True, True, 40)

    def on_browse_clicked(self, widget, callback_data):
        dialog = DirectoryDialog(
            "Select the folder where the disc is mounted", parent=self
        )
        folder = dialog.folder
        callback = callback_data["callback"]
        requires = callback_data["requires"]
        callback(widget, requires, folder)

    def on_eject_clicked(self, _widget, data=None):
        self.interpreter.eject_wine_disc()

    def input_menu(self, alias, options, preselect, has_entry, callback):
        """Display an input request as a dropdown menu with options."""
        time.sleep(0.3)
        self.clean_widgets()

        model = Gtk.ListStore(str, str)
        for option in options:
            key, label = option.popitem()
            model.append([key, label])
        combobox = Gtk.ComboBox.new_with_model(model)
        renderer_text = Gtk.CellRendererText()
        combobox.pack_start(renderer_text, True)
        combobox.add_attribute(renderer_text, "text", 1)
        combobox.set_id_column(0)
        combobox.set_active_id(preselect)
        combobox.set_halign(Gtk.Align.CENTER)
        self.widget_box.pack_start(combobox, True, False, 100)

        combobox.connect("changed", self.on_input_menu_changed)
        combobox.show()
        self.continue_handler = self.continue_button.connect(
            "clicked", callback, alias, combobox
        )
        self.continue_button.grab_focus()
        self.continue_button.show()

        self.on_input_menu_changed(combobox)

    def on_input_menu_changed(self, widget):
        """Enable continue button if a non-empty choice is selected"""
        self.continue_button.set_sensitive(bool(widget.get_active_id()))

    def on_runners_ready(self, _widget):
        """The runners are ready, proceed with file selection"""
        self.clean_widgets()
        self.interpreter.installer.prepare_game_files()
        self.set_status("Please review the files needed for the installation then click 'Continue'")
        installer_files_box = InstallerFilesBox(self.interpreter.installer.files, self)
        installer_files_box.connect("files-available", self.on_files_available)
        scrolledwindow = Gtk.ScrolledWindow(
            hexpand=True,
            vexpand=True,
            child=installer_files_box,
            visible=True
        )
        scrolledwindow.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        self.widget_box.pack_end(scrolledwindow, True, True, 10)

        self.continue_button.show()
        self.continue_button.set_sensitive(True)
        self.continue_handler = self.continue_button.connect(
            "clicked", self.on_files_confirmed, installer_files_box
        )

    def on_files_confirmed(self, _button, file_box):
        """Call this when the user confirms the install files
        This will start the downloads.
        """
        self.continue_button.set_sensitive(False)
        self.continue_button.disconnect(self.continue_handler)
        file_box.start_all()

    def on_files_available(self, widget):
        """All files are available, continue the install"""
        logger.info("All files are available, continuing install")
        self.continue_button.hide()
        self.interpreter.game_files = widget.get_game_files()
        self.clean_widgets()
        self.interpreter.launch_installer_commands()

    def on_install_finished(self):
        self.clean_widgets()
        self.install_in_progress = False

        self.desktop_shortcut_box = Gtk.CheckButton("Create desktop shortcut", visible=True)
        self.menu_shortcut_box = Gtk.CheckButton("Create application menu " "shortcut", visible=True)
        self.widget_box.pack_start(self.desktop_shortcut_box, False, False, 5)
        self.widget_box.pack_start(self.menu_shortcut_box, False, False, 5)
        self.widget_box.show()

        if settings.read_setting("create_desktop_shortcut") == "True":
            self.desktop_shortcut_box.set_active(True)
        if settings.read_setting("create_menu_shortcut") == "True":
            self.menu_shortcut_box.set_active(True)

        self.connect("delete-event", self.create_shortcuts)

        self.eject_button.hide()
        self.cancel_button.hide()
        self.continue_button.hide()
        self.install_button.hide()
        self.play_button.show()
        self.close_button.grab_focus()
        self.close_button.show()
        if not self.is_active():
            self.set_urgency_hint(True)  # Blink in taskbar
            self.connect("focus-in-event", self.on_window_focus)

    def on_window_focus(self, _widget, *_args):
        """Remove urgency hint (flashing indicator) when window receives focus"""
        self.set_urgency_hint(False)

    def on_install_error(self, message):
        self.set_status(message)
        self.clean_widgets()
        self.cancel_button.grab_focus()

    def launch_game(self, widget, _data=None):
        """Launch a game after it's been installed."""
        widget.set_sensitive(False)
        self.on_destroy(widget)
        self.application.launch(Game(self.interpreter.installer.game_id))

    def on_destroy(self, _widget, _data=None):
        """destroy event handler"""
        if self.install_in_progress:
            abort_close = self.cancel_installation()
            if abort_close:
                return True
        else:
            if self.interpreter:
                self.interpreter.cleanup()
            self.destroy()

    def create_shortcuts(self, *args):
        """Create desktop and global menu shortcuts."""
        game_slug = self.interpreter.installer.game_slug
        game_id = self.interpreter.installer.game_id
        game_name = self.interpreter.installer.game_name
        create_desktop_shortcut = self.desktop_shortcut_box.get_active()
        create_menu_shortcut = self.menu_shortcut_box.get_active()

        if create_desktop_shortcut:
            xdgshortcuts.create_launcher(game_slug, game_id, game_name, desktop=True)
        if create_menu_shortcut:
            xdgshortcuts.create_launcher(game_slug, game_id, game_name, menu=True)

        settings.write_setting("create_desktop_shortcut", create_desktop_shortcut)
        settings.write_setting("create_menu_shortcut", create_menu_shortcut)

    def cancel_installation(self, _widget=None):
        """Ask a confirmation before cancelling the install"""
        remove_checkbox = Gtk.CheckButton.new_with_label("Remove game files")
        if self.interpreter:
            remove_checkbox.set_active(self.interpreter.game_dir_created)
            remove_checkbox.show()
        confirm_cancel_dialog = QuestionDialog(
            {
                "question": "Are you sure you want to cancel the installation?",
                "title": "Cancel installation?",
                "widgets": [remove_checkbox]
            }
        )
        if confirm_cancel_dialog.result != Gtk.ResponseType.YES:
            logger.debug("User cancelled installation")
            return True
        if self.interpreter:
            self.interpreter.revert()
            self.interpreter.cleanup()
        self.destroy()

    def on_source_clicked(self, _button):
        InstallerSourceDialog(
            self.interpreter.installer.script_pretty,
            self.interpreter.installer.game_name,
            self
        )

    def clean_widgets(self):
        """Cleanup before displaying the next stage."""
        for child_widget in self.widget_box.get_children():
            child_widget.destroy()

    def set_status(self, text):
        """Display a short status text."""
        self.status_label.set_text(text)

    def set_message(self, message):
        """Display a message."""
        label = InstallerLabel()
        label.set_markup("<b>%s</b>" % add_url_tags(message))
        label.show()
        self.widget_box.pack_start(label, False, False, 18)

    def add_spinner(self):
        """Display a wait icon."""
        self.clean_widgets()
        spinner = Gtk.Spinner()
        self.widget_box.pack_start(spinner, False, False, 18)
        spinner.show()
        spinner.start()

    def attach_logger(self, command):
        """Creates a TextBuffer and attach it to a command"""
        self.log_buffer = Gtk.TextBuffer()
        command.set_log_buffer(self.log_buffer)
        self.log_textview = LogTextView(self.log_buffer)
        scrolledwindow = Gtk.ScrolledWindow(
            hexpand=True, vexpand=True, child=self.log_textview
        )
        scrolledwindow.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        self.widget_box.pack_end(scrolledwindow, True, True, 10)
        scrolledwindow.show()
        self.log_textview.show()
