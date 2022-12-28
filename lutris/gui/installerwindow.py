"""Window used for game installers"""
import os
from gettext import gettext as _

from gi.repository import GLib, Gtk

from lutris.config import LutrisConfig
from lutris.exceptions import UnavailableGameError, watch_errors
from lutris.game import Game
from lutris.gui.dialogs import DirectoryDialog, ErrorDialog, InstallerSourceDialog, QuestionDialog
from lutris.gui.dialogs.cache import CacheConfigurationDialog
from lutris.gui.dialogs.delegates import DialogInstallUIDelegate
from lutris.gui.installer.files_box import InstallerFilesBox
from lutris.gui.installer.script_picker import InstallerPicker
from lutris.gui.widgets.common import FileChooserEntry
from lutris.gui.widgets.log_text_view import LogTextView
from lutris.gui.widgets.window import BaseApplicationWindow
from lutris.installer import InstallationKind, get_installers, interpreter
from lutris.installer.errors import MissingGameDependency, ScriptingError
from lutris.util import xdgshortcuts
from lutris.util.log import logger
from lutris.util.steam import shortcut as steam_shortcut
from lutris.util.strings import gtk_safe, human_size
from lutris.util.system import is_removeable


class InstallerWindow(BaseApplicationWindow, DialogInstallUIDelegate):  # pylint: disable=too-many-public-methods
    """GUI for the install process."""

    def __init__(
        self,
        installers,
        service=None,
        appid=None,
        application=None,
        installation_kind=InstallationKind.INSTALL
    ):
        super().__init__(application=application)
        self.set_default_size(540, 320)
        self.installers = installers
        self.config = {}
        self.service = service
        self.appid = appid
        self.install_in_progress = False
        self.interpreter = None
        self.installation_kind = installation_kind
        self.log_buffer = Gtk.TextBuffer()

        button_box = Gtk.Box(spacing=6)
        self.back_button = Gtk.Button(_("Back"), sensitive=False)
        self.back_button.connect("clicked", self.on_back_clicked)
        button_box.add(self.back_button)

        self.cache_button = Gtk.Button(_("Cache"))
        self.cache_button.connect("clicked", self.on_cache_clicked)
        button_box.add(self.cache_button)

        self.title_label = InstallerWindow.MarkupLabel(selectable=False)
        self.title_label.set_markup(_("<b>Install %s</b>") % gtk_safe(self.installers[0]["name"]))
        self.vbox.add(self.title_label)

        self.status_label = InstallerWindow.MarkupLabel()
        self.vbox.add(self.status_label)

        self.stack = InstallerWindow.NavigationStack(self.back_button)
        self.stack.add_named_factory("choose_installer", self.create_choose_installer_page)
        self.stack.add_named_factory("destination", self.create_destination_page)
        self.stack.add_named_factory("installer_files", self.create_installer_files_page)
        self.stack.add_named_factory("extras", self.create_extras_page)
        self.stack.add_named_factory("spinner", self.create_spinner_page)
        self.stack.add_named_factory("log", self.create_log_page)
        self.stack.add_named_factory("nothing", lambda *x: Gtk.Box())
        self.vbox.pack_start(self.stack, True, True, 0)

        self.vbox.add(Gtk.HSeparator())

        self.action_buttons = Gtk.Box(spacing=6)
        action_buttons_alignment = Gtk.Alignment.new(1, 0, 0, 0)
        action_buttons_alignment.add(self.action_buttons)
        button_box.pack_end(action_buttons_alignment, True, True, 0)
        self.vbox.pack_start(button_box, False, True, 0)

        self.cancel_button = self.add_button(
            _("C_ancel"), self.on_cancel_clicked, tooltip=_("Abort and revert the installation")
        )
        self.eject_button = self.add_button(_("_Eject"), self.on_eject_clicked)
        self.source_button = self.add_button(_("_View source"), self.on_source_clicked)
        self.continue_button = self.add_button(_("_Continue"))
        self.play_button = self.add_button(_("_Launch"), self.launch_game)
        self.close_button = self.add_button(_("_Close"), self.on_destroy)

        self.continue_handler = None

        self.extras_tree_store = Gtk.TreeStore(
            bool,  # is selected?
            bool,  # is inconsistent?
            str,   # id
            str,   # label
        )

        self.location_entry = FileChooserEntry(
            "Select folder",
            Gtk.FileChooserAction.SELECT_FOLDER,
            warn_if_non_empty=True,
            warn_if_ntfs=True
        )
        self.location_entry.connect("changed", self.on_location_entry_changed)

        self.installer_files_box = InstallerFilesBox()
        self.installer_files_box.connect("files-available", self.on_files_available)
        self.installer_files_box.connect("files-ready", self.on_files_ready)

        self.show_all()
        self.install_in_progress = True
        self.stack.show()
        self.title_label.show()

        self.load_choose_installer_page()
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

    @watch_errors()
    def on_cache_clicked(self, _button):
        """Open the cache configuration dialog"""
        CacheConfigurationDialog(parent=self)

    @watch_errors()
    def on_back_clicked(self, _button):
        self.stack.navigate_back()

    def launch_game(self, widget, _data=None):
        """Launch a game after it's been installed."""
        widget.set_sensitive(False)
        self.on_destroy(widget)
        game = Game(self.interpreter.installer.game_id)
        if game.id:
            game.emit("game-launch")
        else:
            logger.error("Game has no ID, launch button should not be drawn")

    def on_destroy(self, _widget, _data=None):
        """destroy event handler"""
        if self.install_in_progress:
            if self.on_cancel_clicked(_widget):
                return True
        else:
            if self.interpreter:
                self.interpreter.cleanup()
            self.destroy()

    def on_cancel_clicked(self, _widget=None):
        """Ask a confirmation before cancelling the install"""
        widgets = []

        remove_checkbox = Gtk.CheckButton.new_with_label(_("Remove game files"))
        if self.interpreter and self.interpreter.target_path and \
                self.installation_kind == InstallationKind.INSTALL and \
                is_removeable(self.interpreter.target_path, LutrisConfig().system_config):
            remove_checkbox.set_active(self.interpreter.game_dir_created)
            remove_checkbox.show()
            widgets.append(remove_checkbox)

        confirm_cancel_dialog = QuestionDialog(
            {
                "parent": self,
                "question": _("Are you sure you want to cancel the installation?"),
                "title": _("Cancel installation?"),
                "widgets": widgets
            }
        )
        if confirm_cancel_dialog.result != Gtk.ResponseType.YES:
            logger.debug("User aborted installation cancellation")
            return True
        self.installer_files_box.stop_all()
        if self.interpreter:
            self.interpreter.revert(remove_game_dir=remove_checkbox.get_active())
            self.interpreter.cleanup()  # still remove temporary downloads in any case
        self.destroy()

    @watch_errors()
    def on_source_clicked(self, _button):
        InstallerSourceDialog(
            self.interpreter.installer.script_pretty,
            self.interpreter.installer.game_name,
            self
        )

    def on_watched_error(self, error):
        ErrorDialog(str(error), parent=self)

    def set_status(self, text):
        """Display a short status text."""
        self.status_label.set_text(text)

    # Choose Installer Page

    def load_choose_installer_page(self):
        self.validate_scripts()
        self.stack.navigate_to_page(self.present_choose_installer_page)

    def create_choose_installer_page(self):
        installer_picker = InstallerPicker(self.installers)
        installer_picker.connect("installer-selected", self.on_installer_selected)
        return Gtk.ScrolledWindow(
            hexpand=True,
            vexpand=True,
            child=installer_picker,
            shadow_type=Gtk.ShadowType.ETCHED_IN
        )

    def present_choose_installer_page(self):
        """Stage where we choose an install script."""
        self.set_status("")
        self.stack.present_page("choose_installer")
        self.display_no_buttons()

    @watch_errors()
    def on_installer_selected(self, _widget, installer_version):
        """Sets the script interpreter to the correct script then proceed to
        install folder selection.

        If the installed game depends on another one and it's not installed,
        prompt the user to install it and quit this installer.
        """
        try:
            script = None
            for _script in self.installers:
                if _script["version"] == installer_version:
                    script = _script
            self.interpreter = interpreter.ScriptInterpreter(script, self)
            self.interpreter.connect("runners-installed", self.on_runners_ready)
        except MissingGameDependency as ex:
            dlg = QuestionDialog(
                {
                    "parent": self,
                    "question": _("This game requires %s. Do you want to install it?") % ex.slug,
                    "title": _("Missing dependency"),
                }
            )
            if dlg.result == Gtk.ResponseType.YES:
                installers = get_installers(game_slug=ex.slug)
                self.application.show_installer_window(installers)
            return

        self.title_label.set_markup(_("<b>Installing {}</b>").format(gtk_safe(self.interpreter.installer.game_name)))
        self.load_destination_page()

    def validate_scripts(self):
        """Auto-fixes some script aspects and checks for mandatory fields"""
        if not self.installers:
            raise ScriptingError(_("No installer available"))
        for script in self.installers:
            for item in ["description", "notes"]:
                script[item] = script.get(item) or ""
            for item in ["name", "runner", "version"]:
                if item not in script:
                    logger.error("Invalid script: %s", script)
                    raise ScriptingError(_('Missing field "%s" in install script') % item)

    # Destination Page

    def load_destination_page(self):
        """Stage where we select the install directory."""
        if not self.interpreter.installer.creates_game_folder:
            self.on_destination_confirmed()
            return

        default_path = self.interpreter.get_default_target()
        self.location_entry.set_text(default_path)

        self.stack.navigate_to_page(self.present_destination_page)
        self.continue_button.grab_focus()

    def create_destination_page(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.pack_start(self.location_entry, False, False, 5)

        desktop_shortcut_button = Gtk.CheckButton(_("Create desktop shortcut"), visible=True)
        desktop_shortcut_button.connect("clicked", self.on_create_desktop_shortcut_clicked)
        vbox.pack_start(desktop_shortcut_button, False, False, 5)

        menu_shortcut_button = Gtk.CheckButton(_("Create application menu shortcut"), visible=True)
        menu_shortcut_button.connect("clicked", self.on_create_menu_shortcut_clicked)
        vbox.pack_start(menu_shortcut_button, False, False, 5)

        if steam_shortcut.vdf_file_exists():
            steam_shortcut_button = Gtk.CheckButton(_("Create steam shortcut"), visible=True)
            steam_shortcut_button.connect("clicked", self.on_create_steam_shortcut_clicked)
            vbox.pack_start(steam_shortcut_button, False, False, 5)
        return vbox

    def present_destination_page(self):
        """Display the destination chooser."""

        self.set_status(_("Select installation directory"))
        self.stack.present_page("destination")
        self.display_continue_button(self.on_destination_confirmed, show_source_button=True)

    @watch_errors()
    def on_destination_confirmed(self, _button=None):
        """Let the interpreter take charge of the next stages."""
        self.load_spinner_page(_("Preparing Lutris for installation"))
        GLib.idle_add(self.launch_install)

    def launch_install(self):
        # This is a shim method to allow exceptions from
        # the interpreter to be reported via watch_errors().
        try:
            if not self.interpreter.launch_install(self):
                self.stack.navigate_reset()
        except Exception as ex:
            ErrorDialog(str(ex), parent=self)
            self.stack.navigate_reset()

    @watch_errors()
    def on_location_entry_changed(self, entry, _data=None):
        """Set the installation target for the game."""
        self.interpreter.target_path = os.path.expanduser(entry.get_text())

    def on_create_desktop_shortcut_clicked(self, checkbutton):
        self.config["create_desktop_shortcut"] = checkbutton.get_active()

    def on_create_menu_shortcut_clicked(self, checkbutton):
        self.config["create_menu_shortcut"] = checkbutton.get_active()

    def on_create_steam_shortcut_clicked(self, checkbutton):
        self.config["create_steam_shortcut"] = checkbutton.get_active()

    @watch_errors()
    def on_runners_ready(self, _widget=None):
        self.load_extras_page()

    # Extras Page

    def load_extras_page(self):
        def get_extra_label(extra):
            """Return a label for the extras picker"""
            label = extra["name"]
            _infos = []
            if extra.get("total_size"):
                _infos.append(human_size(extra["total_size"]))
            if extra.get("type"):
                _infos.append(extra["type"])
            if _infos:
                label += " (%s)" % ", ".join(_infos)
            return label

        if self.interpreter.extras is None:
            all_extras = self.interpreter.get_extras()
            if all_extras:
                self.extras_tree_store.clear()
                for extra_source, extras in all_extras.items():
                    parent = self.extras_tree_store.append(None, (None, None, None, extra_source))
                    for extra in extras:
                        self.extras_tree_store.append(parent, (False, False, extra["id"], get_extra_label(extra)))

                self.stack.navigate_to_page(self.present_extras_page)
                return

        self.on_extras_ready()

    def create_extras_page(self):
        treeview = Gtk.TreeView(self.extras_tree_store)
        treeview.set_headers_visible(False)
        treeview.expand_all()
        renderer_toggle = Gtk.CellRendererToggle()
        renderer_toggle.connect("toggled", self.on_extra_toggled, self.extras_tree_store)
        renderer_text = Gtk.CellRendererText()

        installed_column = Gtk.TreeViewColumn(None, renderer_toggle, active=0, inconsistent=1)
        treeview.append_column(installed_column)

        label_column = Gtk.TreeViewColumn(None, renderer_text)
        label_column.add_attribute(renderer_text, "text", 3)
        label_column.set_property("min-width", 80)
        treeview.append_column(label_column)

        return Gtk.ScrolledWindow(
            hexpand=True,
            vexpand=True,
            child=treeview,
            visible=True,
            shadow_type=Gtk.ShadowType.ETCHED_IN
        )

    def present_extras_page(self):
        """Show installer screen with the extras picker"""

        def on_continue(_button):
            self.on_extras_confirmed(self.extras_tree_store)

        self.set_status(_(
            "This game has extra content. \nSelect which one you want and "
            "they will be available in the 'extras' folder where the game is installed."
        ))
        self.stack.present_page("extras")
        self.display_continue_button(on_continue)

    @watch_errors()
    def on_extra_toggled(self, _widget, path, model):
        toggled_row = model[path]
        toggled_row_iter = model.get_iter(path)

        toggled_row[0] = not toggled_row[0]
        toggled_row[1] = False

        if model.iter_has_child(toggled_row_iter):
            extra_iter = model.iter_children(toggled_row_iter)
            while extra_iter:
                extra_row = model[extra_iter]
                extra_row[0] = toggled_row[0]
                extra_iter = model.iter_next(extra_iter)
        else:
            for heading_row in model:
                all_extras_active = True
                any_extras_active = False
                extra_iter = model.iter_children(heading_row.iter)
                while extra_iter:
                    extra_row = model[extra_iter]
                    if extra_row[0]:
                        any_extras_active = True
                    else:
                        all_extras_active = False
                    extra_iter = model.iter_next(extra_iter)

                heading_row[0] = all_extras_active
                heading_row[1] = any_extras_active

    @watch_errors()
    def on_extras_confirmed(self, extra_store):
        """Resume install when user has selected extras to download"""
        selected_extras = []

        def save_extra(store, path, iter_):
            selected, _inconsistent, id_, _label = store[iter_]
            if selected and id_:
                selected_extras.append(id_)
        extra_store.foreach(save_extra)

        self.interpreter.extras = selected_extras
        GLib.idle_add(self.on_extras_ready)

    @watch_errors()
    def on_extras_ready(self, *args):
        if not self.load_installer_files_page():
            logger.debug("Installer doesn't require files")
            self.launch_installer_commands()

    # Installer Files & Downloading Page

    def load_installer_files_page(self):
        try:
            if self.installation_kind == InstallationKind.UPDATE:
                patch_version = self.interpreter.installer.version
            else:
                patch_version = None
            self.interpreter.installer.prepare_game_files(patch_version)
        except UnavailableGameError as ex:
            raise ScriptingError(str(ex)) from ex

        if not self.interpreter.installer.files:
            return False

        self.installer_files_box.load_installer(self.interpreter.installer)
        self.stack.navigate_to_page(self.present_installer_files_page)
        return True

    def create_installer_files_page(self):
        return Gtk.ScrolledWindow(
            hexpand=True,
            vexpand=True,
            child=self.installer_files_box,
            visible=True,
            shadow_type=Gtk.ShadowType.ETCHED_IN
        )

    def present_installer_files_page(self):
        """Show installer screen with the file picker / downloader"""

        self.set_status(_(
            "Please review the files needed for the installation then click 'Continue'"))
        self.cache_button.set_sensitive(True)
        self.stack.present_page("installer_files")
        self.display_install_button(self.on_files_confirmed, sensitive=self.installer_files_box.is_ready)

    def present_downloading_files_page(self):
        def on_exit_page():
            self.installer_files_box.stop_all()

        self.set_status(_("Downloading game data"))
        self.cache_button.set_sensitive(False)
        self.stack.present_page("installer_files")
        self.display_install_button(None, sensitive=False)
        return on_exit_page

    def on_files_ready(self, _widget, files_ready):
        """Toggle state of continue button based on ready state"""
        self.display_install_button(self.on_files_confirmed, sensitive=files_ready)

    @watch_errors()
    def on_files_confirmed(self, _button):
        """Call this when the user confirms the install files
        This will start the downloads.
        """
        try:
            self.installer_files_box.start_all()
            self.stack.jump_to_page(self.present_downloading_files_page)
        except PermissionError as ex:
            raise ScriptingError(_("Unable to get files: %s") % ex) from ex

    @watch_errors()
    def on_files_available(self, widget):
        """All files are available, continue the install"""
        logger.info("All files are available, continuing install")
        self.interpreter.game_files = widget.get_game_files()
        self.launch_installer_commands()

    def launch_installer_commands(self):
        self.load_spinner_page(_("Installing game data"))
        self.stack.discard_navigation()  # once we really start installing, no going back!
        self.interpreter.launch_installer_commands()

    # Spinner Page

    def load_spinner_page(self, status):
        self.stack.jump_to_page(lambda *x: self.present_spinner_page(status))

    def create_spinner_page(self):
        spinner = Gtk.Spinner()
        spinner.start()
        return spinner

    def present_spinner_page(self, status):
        """Show a spinner in the middle of the view"""

        def on_exit_page():
            self.stack.set_back_allowed(True)

        self.set_status(status)
        self.stack.present_page("spinner")
        self.display_no_buttons()
        self.stack.set_back_allowed(False)
        return on_exit_page

    # Log Page

    def load_log_page(self, command):
        command.set_log_buffer(self.log_buffer)
        self.stack.jump_to_page(self.present_log_page)

    def create_log_page(self):
        log_textview = LogTextView(self.log_buffer)
        return Gtk.ScrolledWindow(
            hexpand=True,
            vexpand=True,
            child=log_textview,
            shadow_type=Gtk.ShadowType.ETCHED_IN
        )

    def present_log_page(self):
        """Creates a TextBuffer and attach it to a command"""

        self.stack.present_page("log")
        self.display_no_buttons()

    # Input Menu Page

    def load_input_menu_page(self, alias, options, preselect, callback):
        def present_input_menu_page():
            """Display an input request as a dropdown menu with options."""
            def on_continue(_button):
                callback(alias, combobox)

            model = Gtk.ListStore(str, str)

            for option in options:
                key, label = option.popitem()
                model.append([key, label])

            combobox = Gtk.ComboBox.new_with_model(model)
            renderer_text = Gtk.CellRendererText()
            combobox.pack_start(renderer_text, True)
            combobox.add_attribute(renderer_text, "text", 1)
            combobox.set_id_column(0)
            combobox.set_halign(Gtk.Align.CENTER)
            combobox.set_active_id(preselect)
            combobox.connect("changed", self.on_input_menu_changed)

            self.stack.present_replacement_page("input_menu", combobox)
            self.display_continue_button(on_continue)
            self.continue_button.grab_focus()
            self.on_input_menu_changed(combobox)

        # we must use jump_to_page() here since it would be unsave to return
        # back to this page and re-execute the callback.
        self.stack.jump_to_page(present_input_menu_page)

    def on_input_menu_changed(self, combobox):
        """Enable continue button if a non-empty choice is selected"""
        self.continue_button.set_sensitive(bool(combobox.get_active_id()))

    # Ask for Disc Page

    def load_ask_for_disc_page(self, message, installer, callback, requires):
        def present_ask_for_disc_page():
            """Ask the user to do insert a CD-ROM."""

            def wrapped_callback(*args, **kwargs):
                try:
                    callback(*args, **kwargs)
                except Exception as err:
                    ErrorDialog(str(err), parent=self)

            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            label = InstallerWindow.MarkupLabel(message)
            label.show()
            vbox.add(label)

            buttons_box = Gtk.Box()
            buttons_box.show()
            buttons_box.set_margin_top(40)
            buttons_box.set_margin_bottom(40)
            vbox.add(buttons_box)

            autodetect_button = Gtk.Button(label=_("Autodetect"))
            autodetect_button.connect("clicked", wrapped_callback, requires)
            autodetect_button.grab_focus()
            autodetect_button.show()
            buttons_box.pack_start(autodetect_button, True, True, 40)

            browse_button = Gtk.Button(label=_("Browse…"))
            callback_data = {"callback": wrapped_callback, "requires": requires}
            browse_button.connect("clicked", self.on_browse_clicked, callback_data)
            browse_button.show()
            buttons_box.pack_start(browse_button, True, True, 40)

            self.stack.present_replacement_page("ask_for_disc", vbox)
            if installer.runner == "wine":
                self.display_eject_button()
            else:
                self.display_no_buttons()

        self.stack.jump_to_page(present_ask_for_disc_page)

    @watch_errors()
    def on_browse_clicked(self, widget, callback_data):
        dialog = DirectoryDialog(_("Select the folder where the disc is mounted"), parent=self)
        folder = dialog.folder
        callback = callback_data["callback"]
        requires = callback_data["requires"]
        callback(widget, requires, folder)

    @watch_errors()
    def on_eject_clicked(self, _widget, data=None):
        self.interpreter.eject_wine_disc()

    # Error Message Page

    def load_error_message_page(self, message):
        self.stack.navigate_to_page(lambda *x: self.present_error_page(message))
        self.cancel_button.grab_focus()

    def present_error_page(self, message):
        self.set_status(message)
        self.stack.present_page("nothing")
        self.display_cancel_button()

    # Finished Page

    def load_finish_install_page(self, game_id, status):
        if self.config.get("create_desktop_shortcut"):
            self.create_shortcut(desktop=True)
        if self.config.get("create_menu_shortcut"):
            self.create_shortcut()

        # Save game to trigger a game-updated signal,
        # but take care not to create a blank game
        if game_id:
            game = Game(game_id)
            if self.config.get("create_steam_shortcut"):
                steam_shortcut.create_shortcut(game)
            game.save()

        self.install_in_progress = False

        self.stack.jump_to_page(lambda *x: self.present_finished_page(game_id, status))
        self.stack.discard_navigation()
        self.close_button.grab_focus()

        if not self.is_active():
            self.set_urgency_hint(True)  # Blink in taskbar
            self.connect("focus-in-event", self.on_window_focus)

    def present_finished_page(self, game_id, status):
        self.set_status(status)
        self.stack.present_page("nothing")
        self.display_close_button(show_play_button=bool(game_id))

    def on_window_focus(self, _widget, *_args):
        """Remove urgency hint (flashing indicator) when window receives focus"""
        self.set_urgency_hint(False)

    def create_shortcut(self, desktop=False):
        """Create desktop or global menu shortcuts."""
        game_slug = self.interpreter.installer.game_slug
        game_id = self.interpreter.installer.game_id
        game_name = self.interpreter.installer.game_name

        if desktop:
            xdgshortcuts.create_launcher(game_slug, game_id, game_name, desktop=True)
        else:
            xdgshortcuts.create_launcher(game_slug, game_id, game_name, menu=True)

    # Buttons

    def display_continue_button(self, handler,
                                continue_button_label=_("Continue"),
                                show_source_button=False,
                                sensitive=True):
        if show_source_button:
            self.present_buttons([self.source_button, self.continue_button])
        else:
            self.present_buttons([self.continue_button])

        self.continue_button.set_label(continue_button_label)
        self.continue_button.set_sensitive(sensitive)
        if self.continue_handler:
            self.continue_button.disconnect(self.continue_handler)

        if handler:
            self.continue_handler = self.continue_button.connect("clicked", handler)
        else:
            self.continue_handler = None

    def display_install_button(self, handler, sensitive=True):
        self.display_continue_button(handler, continue_button_label=_(
            "_Install"), sensitive=sensitive, show_source_button=True)

    def display_cancel_button(self):
        self.present_buttons([self.cancel_button])

    def display_close_button(self, show_play_button):
        to_show = [self.close_button]
        if show_play_button:
            to_show.append(self.play_button)
        self.present_buttons(to_show)

        if self.continue_handler:
            self.continue_button.disconnect(self.continue_handler)

    def display_eject_button(self):
        self.present_buttons([self.eject_button])

    def display_no_buttons(self):
        self.present_buttons([])

        if self.continue_handler:
            self.continue_button.disconnect(self.continue_handler)

    def present_buttons(self, buttons):
        all_buttons = [self.cancel_button,
                       self.eject_button,
                       self.source_button,
                       self.continue_button,
                       self.play_button,
                       self.close_button]

        for b in all_buttons:
            b.set_visible(b in buttons)

    class MarkupLabel(Gtk.Label):
        """Label for installer window"""

        def __init__(self, markup=None, selectable=True):
            super().__init__(
                label=markup,
                use_markup=True,
                wrap=True,
                max_width_chars=80,
                selectable=selectable)
            self.set_alignment(0.5, 0)

    class NavigationStack(Gtk.Stack):
        def __init__(self, back_button, **kwargs):
            super().__init__(**kwargs)

            self.back_button = back_button
            self.page_factories = {}
            self.stack_pages = {}
            self.navigation_stack = []
            self.navigation_exit_hander = None
            self.current_page_presenter = None
            self.back_allowed = True

        def add_named_factory(self, name, factory):
            self.page_factories[name] = factory

        def set_back_allowed(self, is_allowed=True):
            self.back_allowed = is_allowed
            self._update_back_button()

        def _update_back_button(self):
            self.back_button.set_sensitive(self.back_allowed and self.navigation_stack)

        def navigate_to_page(self, page_presenter):
            if self.current_page_presenter:
                self.navigation_stack.append(self.current_page_presenter)
                self._update_back_button()
            self.current_page_presenter = page_presenter

            self.jump_to_page(page_presenter)

        def jump_to_page(self, page_presenter):
            exit_handler = self.navigation_exit_hander
            self.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT)
            self.navigation_exit_hander = page_presenter()
            if exit_handler:
                exit_handler()

        def navigate_back(self):
            if self.navigation_stack:
                try:
                    exit_handler = self.navigation_exit_hander
                    self.current_page_presenter = self.navigation_stack.pop()
                    self.set_transition_type(Gtk.StackTransitionType.SLIDE_RIGHT)
                    self.navigation_exit_hander = self.current_page_presenter()

                    if exit_handler:
                        exit_handler()
                finally:
                    self._update_back_button()

        def navigate_reset(self):
            if self.current_page_presenter:
                try:
                    exit_handler = self.navigation_exit_hander
                    self.set_transition_type(Gtk.StackTransitionType.SLIDE_RIGHT)
                    self.navigation_exit_hander = self.current_page_presenter()

                    if exit_handler:
                        exit_handler()
                finally:
                    self._update_back_button()

        def discard_navigation(self):
            self.navigation_stack.clear()
            self._update_back_button()

        def present_page(self, name):
            if name not in self.stack_pages:
                factory = self.page_factories[name]
                page = factory()
                page.show_all()

                self.add_named(page, name)
                self.stack_pages[name] = page

            self.set_visible_child_name(name)
            return self.stack_pages[name]

        def present_replacement_page(self, name, page):
            old_page = self.stack_pages.get(name)

            if old_page:
                self.remove(old_page)

            page.show_all()

            self.add_named(page, name)
            self.stack_pages[name] = page

            self.set_visible_child_name(name)
            return page
