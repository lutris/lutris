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
        self.log_buffer = None
        self.log_textview = None

        self._cancel_files_func = None

        self.title_label = InstallerWindow.MarkupLabel(selectable=False)
        self.vbox.add(self.title_label)

        self.status_label = InstallerWindow.MarkupLabel()
        self.vbox.add(self.status_label)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.SLIDE_LEFT)
        self.vbox.pack_start(self.stack, True, True, 0)

        self.vbox.add(Gtk.HSeparator())

        button_box = Gtk.Box()
        self.cache_button = Gtk.Button(_("Cache"))
        self.cache_button.connect("clicked", self.on_cache_clicked)
        button_box.add(self.cache_button)

        self.action_buttons = Gtk.Box(spacing=6)
        action_buttons_alignment = Gtk.Alignment.new(1, 0, 0, 0)
        action_buttons_alignment.add(self.action_buttons)
        button_box.pack_end(action_buttons_alignment, True, True, 0)
        self.vbox.pack_start(button_box, False, True, 0)

        self.cancel_button = self.add_button(
            _("C_ancel"), self.confirm_cancel, tooltip=_("Abort and revert the installation")
        )
        self.eject_button = self.add_button(_("_Eject"), self.on_eject_clicked)
        self.source_button = self.add_button(_("_View source"), self.on_source_clicked)
        self.install_button = self.add_button(_("_Install"), self.on_install_clicked)
        self.continue_button = self.add_button(_("_Continue"))
        self.play_button = self.add_button(_("_Launch"), self.launch_game)
        self.close_button = self.add_button(_("_Close"), self.on_destroy)

        self.continue_handler = None
        self.stack_pages = {}

        self.show_all()
        self.close_button.hide()
        self.play_button.hide()
        self.install_button.hide()
        self.source_button.hide()
        self.eject_button.hide()
        self.continue_button.hide()
        self.install_in_progress = True
        self.stack.show()
        self.title_label.show()
        self.present_choose_installer_page()

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

    def present_choose_installer_page(self):
        """Stage where we choose an install script."""
        self.validate_scripts()
        base_script = self.installers[0]
        self.title_label.set_markup(_("<b>Install %s</b>") % gtk_safe(base_script["name"]))

        def create_page():
            installer_picker = InstallerPicker(self.installers)
            installer_picker.connect("installer-selected", self.on_installer_selected)
            scrolledwindow = Gtk.ScrolledWindow(
                hexpand=True,
                vexpand=True,
                child=installer_picker,
                visible=True
            )
            scrolledwindow.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
            return scrolledwindow

        self.present_page("choose_installer", create_page)

    @watch_errors()
    def on_cache_clicked(self, _button):
        """Open the cache configuration dialog"""
        CacheConfigurationDialog(parent=self)

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
        self.select_install_folder()

    def select_install_folder(self):
        """Stage where we select the install directory."""
        if not self.interpreter.installer.creates_game_folder:
            self.start_install()
            return
        default_path = self.interpreter.get_default_target()
        self.present_destination_page(default_path)
        if self.continue_handler:
            self.continue_button.disconnect(self.continue_handler)
        self.continue_button.hide()
        self.source_button.show()
        self.install_button.grab_focus()
        self.install_button.show()

    @watch_errors()
    def on_target_changed(self, entry, _data=None):
        """Set the installation target for the game."""
        self.interpreter.target_path = os.path.expanduser(entry.get_text())

    @watch_errors()
    def on_install_clicked(self, button):
        """Let the interpreter take charge of the next stages."""
        self.start_install()

    def present_destination_page(self, default_path=None):
        """Display the destination chooser."""
        self.install_button.set_visible(False)
        self.continue_button.show()
        self.continue_button.set_sensitive(False)
        self.set_status(_("Select installation directory"))

        def create_page():
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            location_entry = FileChooserEntry(
                "Select folder",
                Gtk.FileChooserAction.SELECT_FOLDER,
                path=default_path,
                warn_if_non_empty=True,
                warn_if_ntfs=True
            )
            location_entry.connect("changed", self.on_target_changed)
            vbox.pack_start(location_entry, False, False, 5)

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

        self.present_page("destination_page", create_page)

    def start_install(self):
        self.install_button.hide()
        self.source_button.hide()
        GLib.idle_add(self.launch_install)

    @watch_errors()
    def launch_install(self):
        # This is a shim method to allow exceptions from
        # the interpreter to be reported via watch_errors().
        if not self.interpreter.launch_install(self):
            self.install_button.show()
            self.source_button.show()

    def present_ask_for_disc_page(self, message, callback, requires):
        """Ask the user to do insert a CD-ROM."""

        def wrapped_callback(*args, **kwargs):
            try:
                callback(*args, **kwargs)
            except Exception as err:
                ErrorDialog(str(err), parent=self)

        def create_page():
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
            return vbox

        self.present_page("ask_for_disc", create_page)

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

    def present_input_menu_page(self, alias, options, preselect, has_entry, callback):
        """Display an input request as a dropdown menu with options."""
        model = Gtk.ListStore(str, str)
        for option in options:
            key, label = option.popitem()
            model.append([key, label])
        # TODO: Need to _update_ the model too!

        def create_page():
            self.input_menu_combobox = Gtk.ComboBox.new_with_model(model)
            renderer_text = Gtk.CellRendererText()
            self.input_menu_combobox.pack_start(renderer_text, True)
            self.input_menu_combobox.add_attribute(renderer_text, "text", 1)
            self.input_menu_combobox.set_id_column(0)
            self.input_menu_combobox.set_active_id(preselect)
            self.input_menu_combobox.set_halign(Gtk.Align.CENTER)
            self.input_menu_combobox.connect("changed", self.on_input_menu_changed)
            return self.input_menu_combobox

        self.present_page("input_menu", create_page)

        if self.continue_handler:
            self.continue_button.disconnect(self.continue_handler)
        self.continue_handler = self.continue_button.connect("clicked", callback, alias, self.input_menu_combobox)
        self.continue_button.grab_focus()
        self.continue_button.show()
        self.on_input_menu_changed(self.input_menu_combobox)

    def on_input_menu_changed(self, widget):
        """Enable continue button if a non-empty choice is selected"""
        self.continue_button.set_sensitive(bool(widget.get_active_id()))

    @watch_errors()
    def on_runners_ready(self, _widget=None):
        """The runners are ready, proceed with file selection"""
        self.present_installer_files_page()

    def present_installer_files_page(self):
        """Show installer screen with the file picker / downloader"""
        if self.interpreter.extras is None:
            extras = self.interpreter.get_extras()
            if extras:
                self.present_extras_page(extras)
                return
        try:
            if self.installation_kind == InstallationKind.UPDATE:
                patch_version = self.interpreter.installer.version
            else:
                patch_version = None
            self.interpreter.installer.prepare_game_files(patch_version)
        except UnavailableGameError as ex:
            raise ScriptingError(str(ex)) from ex

        if not self.interpreter.installer.files:
            logger.debug("Installer doesn't require files")
            self.interpreter.launch_installer_commands()
            return

        self.set_status(_("Please review the files needed for the installation then click 'Continue'"))

        def create_page():
            self.installer_files_box = InstallerFilesBox(self.interpreter.installer, self)
            self.installer_files_box.connect("files-available", self.on_files_available)
            self.installer_files_box.connect("files-ready", self.on_files_ready)
            self._cancel_files_func = self.installer_files_box.stop_all
            scrolledwindow = Gtk.ScrolledWindow(
                hexpand=True,
                vexpand=True,
                child=self.installer_files_box,
                visible=True
            )
            scrolledwindow.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
            return scrolledwindow

        self.present_page("installer_files", create_page)

        self.continue_button.show()
        self.continue_button.set_sensitive(self.installer_files_box.is_ready)
        if self.continue_handler:
            self.continue_button.disconnect(self.continue_handler)
        self.continue_handler = self.continue_button.connect(
            "clicked", self.on_files_confirmed, self.installer_files_box
        )

    def get_extra_label(self, extra):
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

    def present_extras_page(self, all_extras):
        """Show installer screen with the extras picker"""
        self.set_status(_(
            "This game has extra content. \nSelect which one you want and "
            "they will be available in the 'extras' folder where the game is installed."
        ))
        extra_treestore = Gtk.TreeStore(
            bool,  # is selected?
            bool,  # is inconsistent?
            str,   # id
            str,   # label
        )
        for extra_source, extras in all_extras.items():
            parent = extra_treestore.append(None, (None, None, None, extra_source))
            for extra in extras:
                extra_treestore.append(parent, (False, False, extra["id"], self.get_extra_label(extra)))

        def create_page():
            treeview = Gtk.TreeView(extra_treestore)
            treeview.set_headers_visible(False)
            treeview.expand_all()
            renderer_toggle = Gtk.CellRendererToggle()
            renderer_toggle.connect("toggled", self.on_extra_toggled, extra_treestore)
            renderer_text = Gtk.CellRendererText()

            installed_column = Gtk.TreeViewColumn(None, renderer_toggle, active=0, inconsistent=1)
            treeview.append_column(installed_column)

            label_column = Gtk.TreeViewColumn(None, renderer_text)
            label_column.add_attribute(renderer_text, "text", 3)
            label_column.set_property("min-width", 80)
            treeview.append_column(label_column)

            scrolledwindow = Gtk.ScrolledWindow(
                hexpand=True,
                vexpand=True,
                child=treeview,
                visible=True
            )
            scrolledwindow.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
            return scrolledwindow

        self.present_page("extras", create_page)

        self.continue_button.show()
        self.continue_button.set_sensitive(True)
        if self.continue_handler:
            self.continue_button.disconnect(self.continue_handler)
        self.continue_handler = self.continue_button.connect("clicked", self.on_extras_confirmed, extra_treestore)

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
    def on_extras_confirmed(self, _button, extra_store):
        """Resume install when user has selected extras to download"""
        selected_extras = []

        def save_extra(store, path, iter_):
            selected, _inconsistent, id_, _label = store[iter_]
            if selected and id_:
                selected_extras.append(id_)
        extra_store.foreach(save_extra)

        self.interpreter.extras = selected_extras
        GLib.idle_add(self.present_installer_files_page)

    def on_files_ready(self, _widget, files_ready):
        """Toggle state of continue button based on ready state"""
        self.continue_button.set_sensitive(files_ready)

    @watch_errors()
    def on_files_confirmed(self, _button, file_box):
        """Call this when the user confirms the install files
        This will start the downloads.
        """
        self.set_status("")
        self.cache_button.set_sensitive(False)
        self.continue_button.set_sensitive(False)
        try:
            file_box.start_all()
            self.continue_button.disconnect(self.continue_handler)
        except PermissionError as ex:
            self.continue_button.set_sensitive(True)
            raise ScriptingError(_("Unable to get files: %s") % ex) from ex

    @watch_errors()
    def on_files_available(self, widget):
        """All files are available, continue the install"""
        logger.info("All files are available, continuing install")
        self._cancel_files_func = None
        self.continue_button.hide()
        self.interpreter.game_files = widget.get_game_files()
        self.present_nothing()
        self.interpreter.launch_installer_commands()

    def finish_install(self, game_id):
        self.present_nothing()

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

        self.stack.show()

        self.eject_button.hide()
        self.cancel_button.hide()
        self.continue_button.hide()
        self.install_button.hide()
        if game and game.id:
            self.play_button.show()

        self.close_button.grab_focus()
        self.close_button.show()
        if not self.is_active():
            self.set_urgency_hint(True)  # Blink in taskbar
            self.connect("focus-in-event", self.on_window_focus)

    def on_window_focus(self, _widget, *_args):
        """Remove urgency hint (flashing indicator) when window receives focus"""
        self.set_urgency_hint(False)

    def show_install_error_message(self, message):
        self.present_nothing()
        self.set_status(message)
        self.cancel_button.grab_focus()

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
            if self.confirm_cancel():
                return True
        else:
            if self.interpreter:
                self.interpreter.cleanup()
            self.destroy()

    def on_create_desktop_shortcut_clicked(self, checkbutton):
        self.config["create_desktop_shortcut"] = checkbutton.get_active()

    def on_create_menu_shortcut_clicked(self, checkbutton):
        self.config["create_menu_shortcut"] = checkbutton.get_active()

    def on_create_steam_shortcut_clicked(self, checkbutton):
        self.config["create_steam_shortcut"] = checkbutton.get_active()

    def create_shortcut(self, desktop=False):
        """Create desktop or global menu shortcuts."""
        game_slug = self.interpreter.installer.game_slug
        game_id = self.interpreter.installer.game_id
        game_name = self.interpreter.installer.game_name

        if desktop:
            xdgshortcuts.create_launcher(game_slug, game_id, game_name, desktop=True)
        else:
            xdgshortcuts.create_launcher(game_slug, game_id, game_name, menu=True)

    def confirm_cancel(self, _widget=None):
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
        if self._cancel_files_func:
            self._cancel_files_func()
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

    def present_nothing(self):
        def create_page():
            return Gtk.Box()

        self.present_page("nothing", create_page)

    def present_spinner_page(self):
        """Show a spinner in the middle of the view"""

        def create_page():
            spinner = Gtk.Spinner()
            spinner.show()
            spinner.start()
            return spinner

        self.present_page("spinner", create_page)

    def present_log_page(self, command):
        """Creates a TextBuffer and attach it to a command"""
        self.log_buffer = Gtk.TextBuffer()
        command.set_log_buffer(self.log_buffer)

        def create_page():
            # TODO: Update log buffer!
            self.log_textview = LogTextView(self.log_buffer)
            scrolledwindow = Gtk.ScrolledWindow(hexpand=True, vexpand=True, child=self.log_textview)
            scrolledwindow.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
            scrolledwindow.show()
            self.log_textview.show()
            return scrolledwindow

        self.present_page("logger", create_page)

    def present_page(self, name, factory, show_all=True):
        if name not in self.stack_pages:
            page = factory()
            if show_all:
                page.show_all()

            self.stack.add_named(page, name)
            self.stack_pages[name] = page

        self.stack.set_visible_child_name(name)
        return self.stack_pages[name]

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
