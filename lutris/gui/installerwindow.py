"""Window used for game installers"""

# pylint: disable=too-many-lines
import os
import traceback
from gettext import gettext as _

from gi.repository import Gdk, Gio, GLib, Gtk

from lutris import settings
from lutris.config import LutrisConfig
from lutris.game import Game
from lutris.gui.dialogs import (
    DirectoryDialog,
    InstallerSourceDialog,
    ModelessDialog,
    QuestionDialog,
    display_error,
)
from lutris.gui.dialogs.cache import CacheConfigurationDialog
from lutris.gui.dialogs.delegates import DialogInstallUIDelegate
from lutris.gui.installer.files_box import InstallerFilesBox
from lutris.gui.installer.script_picker import InstallerPicker
from lutris.gui.widgets import NotificationSource
from lutris.gui.widgets.common import FileChooserEntry
from lutris.gui.widgets.log_text_view import LogTextView
from lutris.gui.widgets.navigation_stack import NavigationStack
from lutris.installer import InstallationKind, interpreter
from lutris.installer.errors import MissingGameDependencyError, ScriptingError
from lutris.installer.interpreter import ScriptInterpreter
from lutris.util import xdgshortcuts
from lutris.util.jobs import AsyncCall
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import get_log_contents, logger
from lutris.util.steam import shortcut as steam_shortcut
from lutris.util.strings import human_size
from lutris.util.system import is_removeable

INSTALLATION_FAILED = NotificationSource()
INSTALLATION_COMPLETED = NotificationSource()


class MarkupLabel(Gtk.Label):
    """Label for installer window"""

    def __init__(self, markup=None, **kwargs):
        super().__init__(label=markup, use_markup=True, wrap=True, max_width_chars=80, **kwargs)
        self.set_alignment(0.5, 0)


class InstallerWindow(ModelessDialog, DialogInstallUIDelegate, ScriptInterpreter.InterpreterUIDelegate):  # pylint: disable=too-many-public-methods
    """GUI for the install process.

    This window is divided into pages; as you go through the install each page
    is created and displayed to you. You can also go back and visit previous pages
    again. Going *forward* triggers installation work- it does not all way until the
    very end.

    Most pages are defined by a load_X_page() function that initializes the page
    when arriving at it, and which presents it. But this uses a present_X_page() page
    that shows the page (and is used alone for the 'Back' button), and this in turn
    uses a create_X_page() function to create the page the first time it is visited.
    """

    def __init__(self, installers, service=None, appid=None, installation_kind=InstallationKind.INSTALL, **kwargs):
        ModelessDialog.__init__(self, use_header_bar=True, **kwargs)
        ScriptInterpreter.InterpreterUIDelegate.__init__(self, service, appid)
        self.set_default_size(740, 460)
        self.installers = installers
        self.config = {}
        self.selected_extras = []
        self.install_in_progress = False
        self.install_complete = False
        self.interpreter = None
        self.installation_kind = installation_kind
        self.continue_handler = None

        self.accelerators = Gtk.AccelGroup()
        self.add_accel_group(self.accelerators)

        content_area = self.get_content_area()

        content_area.set_margin_top(18)
        content_area.set_margin_bottom(18)
        content_area.set_margin_right(18)
        content_area.set_margin_left(18)
        content_area.set_spacing(12)

        # Header labels
        self.status_label = MarkupLabel(no_show_all=True)
        content_area.pack_start(self.status_label, False, False, 0)

        # Header bar buttons
        self.back_button = self.add_start_button(_("Back"), self.on_back_clicked)
        self.back_button.set_no_show_all(True)
        key, mod = Gtk.accelerator_parse("<Alt>Left")
        self.back_button.add_accelerator("clicked", self.accelerators, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse("<Alt>Home")
        self.accelerators.connect(key, mod, Gtk.AccelFlags.VISIBLE, self.on_navigate_home)

        self.cancel_button = self.add_start_button(_("Cancel"), self.on_cancel_clicked)
        self.get_header_bar().set_show_close_button(False)

        self.continue_button = self.add_end_button(_("_Continue"))

        # The cancel button doubles as 'Close' and 'Abort' depending on the state of the install
        key, mod = Gtk.accelerator_parse("Escape")
        self.cancel_button.add_accelerator("clicked", self.accelerators, key, mod, Gtk.AccelFlags.VISIBLE)

        # Navigation stack
        self.stack = NavigationStack(self.back_button, cancel_button=self.cancel_button)
        self.register_page_creators()
        content_area.pack_start(self.stack, True, True, 0)

        # Menu buttons
        menu_icon = Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.MENU)
        self.menu_button = Gtk.MenuButton(child=menu_icon)
        self.menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, visible=True, halign=Gtk.Align.END)
        self.menu_box.set_border_width(9)
        self.menu_box.set_spacing(3)
        self.menu_box.set_can_focus(False)
        self.menu_button.set_popover(Gtk.Popover(child=self.menu_box, can_focus=False, relative_to=self.menu_button))
        self.get_header_bar().pack_end(self.menu_button)

        self.cache_button = self.add_menu_button(
            _("Configure download cache"),
            self.on_cache_clicked,
            tooltip=_("Change where Lutris downloads game installer files."),
        )

        self.source_button = self.add_menu_button(_("View installer source"), self.on_source_clicked)

        # Pre-create some UI bits we need to refer to in several places.
        # (We lazy allocate more of it, but these are a pain.)

        self.extras_tree_store = Gtk.TreeStore(
            bool,  # is selected?
            bool,  # is inconsistent?
            object,  # extras dict
            str,  # label
        )

        self.location_entry = FileChooserEntry(
            "Select folder",
            Gtk.FileChooserAction.SELECT_FOLDER,
            warn_if_non_empty=True,
            warn_if_non_writable_parent=True,
            warn_if_ntfs=True,
        )
        self.location_entry.connect("changed", self.on_location_entry_changed)

        self.installer_files_box = InstallerFilesBox()
        self.installer_files_box.connect("files-available", self.on_files_available)
        self.installer_files_box.connect("files-ready", self.on_files_ready)

        self.log_buffer = Gtk.TextBuffer()
        self.error_details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, no_show_all=True)
        self.error_details_buffer = Gtk.TextBuffer()
        self.error_reporter = self.load_error_page

        application = Gio.Application.get_default()
        if application and application.window and not application.window.download_queue.is_empty:
            download_queue = application.window.download_queue

            def on_start_installation(*args):
                self.load_choose_installer_page()
                download_queue.disconnect(dc_handler)

            self.load_spinner_page("Waiting for Lutris component installation")
            self.display_continue_button(on_start_installation)

            def on_download_complete(*args):
                if download_queue.is_empty:
                    on_start_installation()

            dc_handler = download_queue.connect("download-completed", on_download_complete)
        else:
            self.load_choose_installer_page()

        # And... go!
        self.show_all()
        self.present()

    def add_start_button(self, label, handler=None, tooltip=None, sensitive=True):
        button = Gtk.Button.new_with_mnemonic(label)
        button.set_sensitive(sensitive)
        button.set_no_show_all(True)
        if tooltip:
            button.set_tooltip_text(tooltip)
        if handler:
            button.connect("clicked", handler)

        header_bar = self.get_header_bar()
        header_bar.pack_start(button)
        return button

    def add_end_button(self, label, handler=None, tooltip=None, sensitive=True):
        """Add a button to the action buttons box"""
        button = Gtk.Button.new_with_mnemonic(label)
        button.set_sensitive(sensitive)
        button.set_no_show_all(True)
        if tooltip:
            button.set_tooltip_text(tooltip)
        if handler:
            button.connect("clicked", handler)

        header_bar = self.get_header_bar()
        header_bar.pack_end(button)
        return button

    def add_menu_button(self, label, handler=None, tooltip=None, sensitive=True):
        """Add a button to the menu in the header bar"""
        button = Gtk.ModelButton(label, visible=True, xalign=0.0)
        button.set_sensitive(sensitive)
        button.set_no_show_all(True)
        if tooltip:
            button.set_tooltip_text(tooltip)
        if handler:
            button.connect("clicked", handler)

        self.menu_box.pack_start(button, False, False, 0)
        return button

    def on_cache_clicked(self, _button):
        """Open the cache configuration dialog"""
        CacheConfigurationDialog(parent=self)

    def on_response(self, dialog, response: Gtk.ResponseType) -> None:
        if response in (Gtk.ResponseType.CLOSE, Gtk.ResponseType.CANCEL, Gtk.ResponseType.DELETE_EVENT):
            self.on_cancel_clicked()
        else:
            super().on_response(dialog, response)

    def on_back_clicked(self, _button):
        self.stack.navigate_back()

    def on_navigate_home(self, _accel_group, _window, _keyval, _modifier):
        self.stack.navigate_home()

    def on_cancel_clicked(self, _button=None):
        """Ask a confirmation before cancelling the installation, if it has started."""
        if self.install_in_progress:
            widgets = []

            remove_checkbox = Gtk.CheckButton.new_with_label(_("Remove game files"))
            if (
                self.interpreter
                and self.interpreter.target_path
                and self.interpreter.game_dir_created
                and self.installation_kind == InstallationKind.INSTALL
                and is_removeable(self.interpreter.target_path, LutrisConfig().system_config)
            ):
                remove_checkbox.set_active(self.interpreter.game_dir_created)
                remove_checkbox.show()
                widgets.append(remove_checkbox)

            confirm_cancel_dialog = QuestionDialog(
                {
                    "parent": self,
                    "question": _("Are you sure you want to cancel the installation?"),
                    "title": _("Cancel installation?"),
                    "widgets": widgets,
                }
            )
            if confirm_cancel_dialog.result != Gtk.ResponseType.YES:
                logger.debug("User aborted installation cancellation")
                return

            self.installer_files_box.stop_all()
            if self.interpreter:
                self.interpreter.revert(remove_game_dir=remove_checkbox.get_active())
        else:
            self.installer_files_box.stop_all()

        if self.interpreter:
            self.interpreter.cleanup()  # still remove temporary downloads in any case

        if self.interpreter and not self.install_in_progress:
            INSTALLATION_COMPLETED.fire()
        else:
            INSTALLATION_FAILED.fire()

        self.destroy()

    def on_source_clicked(self, _button):
        InstallerSourceDialog(self.interpreter.installer.script_pretty, self.interpreter.installer.game_name, self)

    def on_signal_error(self, error):
        self._handle_callback_error(error)

    def on_idle_error(self, error):
        self._handle_callback_error(error)

    def _handle_callback_error(self, error):
        if self.install_in_progress:
            self.load_error_page(error)
        else:
            display_error(error, parent=self)
            self.stack.navigation_reset()

    def set_status(self, text):
        """Display a short status text."""
        self.status_label.set_text(text)
        self.status_label.set_visible(bool(text))

    def get_status(self):
        return self.status_label.get_text() if self.status_label.get_visible() else ""

    def register_page_creators(self):
        self.stack.add_named_factory("choose_installer", self.create_choose_installer_page)
        self.stack.add_named_factory("destination", self.create_destination_page)
        self.stack.add_named_factory("installer_files", self.create_installer_files_page)
        self.stack.add_named_factory("extras", self.create_extras_page)
        self.stack.add_named_factory("spinner", self.create_spinner_page)
        self.stack.add_named_factory("log", self.create_log_page)
        self.stack.add_named_factory("error", self.create_error_page)
        self.stack.add_named_factory("nothing", lambda *x: Gtk.Box())

    # Interpreter UI Delegate
    #
    # These methods are called from the ScriptInterpreter, and defer work until idle time
    # so the installation itself is not interrupted or paused for UI updates.

    def report_error(self, error):
        GLib.idle_add(self.error_reporter, error)

    def report_status(self, status):
        GLib.idle_add(self.set_status, status)

    def attach_log(self, command):
        # Hook the log buffer right now, lest we miss updates.
        command.set_log_buffer(self.log_buffer)
        GLib.idle_add(self.load_log_page)

    def begin_disc_prompt(self, message, requires, installer, callback):
        GLib.idle_add(
            self.load_ask_for_disc_page,
            message,
            requires,
            installer,
            callback,
        )

    def begin_input_menu(self, alias, options, preselect, callback):
        GLib.idle_add(self.load_input_menu_page, alias, options, preselect, callback)

    def report_finished(self, game_id, status):
        GLib.idle_add(self.load_finish_install_page, game_id, status)

    # Choose Installer Page
    #
    # This page offers a choice of installer scripts to run.

    def load_choose_installer_page(self):
        self.validate_scripts(self.installers)
        self.stack.navigate_to_page(self.present_choose_installer_page)

    def create_choose_installer_page(self):
        installer_picker = InstallerPicker(self.installers)
        installer_picker.connect("installer-selected", self.on_installer_selected)
        return Gtk.ScrolledWindow(
            hexpand=True, vexpand=True, child=installer_picker, shadow_type=Gtk.ShadowType.ETCHED_IN
        )

    def present_choose_installer_page(self):
        """Stage where we choose an install script."""
        self.set_status("")
        self.set_title(_("Install %s") % self.installers[0]["name"])
        self.stack.present_page("choose_installer")
        self.display_cancel_button(extra_buttons=[self.cache_button])

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
        except MissingGameDependencyError as ex:
            dlg = QuestionDialog(
                {
                    "parent": self,
                    "question": _("This game requires %s. Do you want to install it?") % ex.slug,
                    "title": _("Missing dependency"),
                }
            )
            if dlg.result == Gtk.ResponseType.YES:
                application = Gio.Application.get_default()
                application.show_lutris_installer_window(game_slug=ex.slug)
            return

        self.set_title(_("Installing {}").format(self.interpreter.installer.game_name))
        self.load_destination_page()

    def validate_scripts(self, installers):
        """Auto-fixes some script aspects and checks for mandatory fields"""
        if not installers:
            raise ScriptingError(_("No installer available"))
        for script in installers:
            for item in ["description", "notes"]:
                script[item] = script.get(item) or ""
            for item in ["name", "runner", "version"]:
                if item not in script:
                    raise ScriptingError(_('Missing field "%s" in install script') % item)
            for file_desc in script["script"].get("files", {}):
                if len(file_desc) > 1:
                    raise ScriptingError(_('Improperly formatted file "%s"') % file_desc)

    # Destination Page
    #
    # This page selects the directory where the game will be installed,
    # as well as few other minor options.

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
        installer_create_desktop_shortcut = settings.read_bool_setting("installer_create_desktop_shortcut", False)
        installer_create_menu_shortcut = settings.read_bool_setting("installer_create_menu_shortcut", False)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.pack_start(self.location_entry, False, False, 0)

        desktop_shortcut_button = Gtk.CheckButton(_("Create desktop shortcut"), visible=True)
        desktop_shortcut_button.set_active(installer_create_desktop_shortcut)
        desktop_shortcut_button.connect("clicked", self.on_create_desktop_shortcut_clicked)
        self.config["create_desktop_shortcut"] = installer_create_desktop_shortcut

        vbox.pack_start(desktop_shortcut_button, False, False, 0)

        menu_shortcut_button = Gtk.CheckButton(_("Create application menu shortcut"), visible=True)
        menu_shortcut_button.set_active(installer_create_menu_shortcut)
        menu_shortcut_button.connect("clicked", self.on_create_menu_shortcut_clicked)
        self.config["create_menu_shortcut"] = installer_create_menu_shortcut

        vbox.pack_start(menu_shortcut_button, False, False, 0)

        if steam_shortcut.vdf_file_exists():
            steam_shortcut_button = Gtk.CheckButton(_("Create Steam shortcut"), visible=True)
            steam_shortcut_button.set_active(settings.read_bool_setting("installer_create_steam_shortcut", False))
            steam_shortcut_button.connect("clicked", self.on_create_steam_shortcut_clicked)
            vbox.pack_start(steam_shortcut_button, False, False, 0)
        return vbox

    def present_destination_page(self):
        """Display the destination chooser."""

        self.set_status(_("Select installation directory"))
        self.stack.present_page("destination")
        self.display_continue_button(
            self.on_destination_confirmed, extra_buttons=[self.cache_button, self.source_button]
        )

    def on_destination_confirmed(self, _button=None):
        """Let the interpreter take charge of the next stages."""

        self.load_spinner_page(
            _("Preparing Lutris for installation"),
            cancellable=False,
            extra_buttons=[self.cache_button, self.source_button],
        )
        GLib.idle_add(self.launch_install)

    def launch_install(self):
        if not self.interpreter.launch_install(self):
            self.stack.navigation_reset()

    def on_location_entry_changed(self, entry, _data=None):
        """Set the installation target for the game."""
        self.interpreter.target_path = os.path.expanduser(entry.get_text())

    def on_create_desktop_shortcut_clicked(self, checkbutton):
        settings.write_setting("installer_create_desktop_shortcut", checkbutton.get_active())
        self.config["create_desktop_shortcut"] = checkbutton.get_active()

    def on_create_menu_shortcut_clicked(self, checkbutton):
        settings.write_setting("installer_create_menu_shortcut", checkbutton.get_active())
        self.config["create_menu_shortcut"] = checkbutton.get_active()

    def on_create_steam_shortcut_clicked(self, checkbutton):
        settings.write_setting("installer_create_steam_shortcut", checkbutton.get_active())
        self.config["create_steam_shortcut"] = checkbutton.get_active()

    def on_runners_ready(self, _widget=None):
        AsyncCall(self.interpreter.get_extras, self.on_extras_loaded)

    # Extras Page
    #
    # This pages offers to download the extras that come with the game; the
    # user specifies the specific extras desired.
    #
    # If there are no extras, the page triggers as if the user had clicked 'Continue',
    # moving on to pre-installation, then the installer files page.

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

    def on_extras_loaded(self, all_extras, error):
        if error:
            self._handle_callback_error(error)
            return

        if all_extras:
            self.extras_tree_store.clear()
            for extra_source, extras in all_extras.items():
                parent = self.extras_tree_store.append(None, (None, None, None, extra_source))
                for extra in extras:
                    self.extras_tree_store.append(parent, (False, False, extra, self.get_extra_label(extra)))

            self.stack.navigate_to_page(self.present_extras_page)
        else:
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
            hexpand=True, vexpand=True, child=treeview, visible=True, shadow_type=Gtk.ShadowType.ETCHED_IN
        )

    def present_extras_page(self):
        """Show installer screen with the extras picker"""
        logger.debug("Showing extras page")

        def on_continue(_button):
            self.on_extras_confirmed(self.extras_tree_store)

        self.set_status(
            _(
                "This game has extra content. \nSelect which one you want and "
                "they will be available in the 'extras' folder where the game is installed."
            )
        )
        self.stack.present_page("extras")
        self.display_continue_button(on_continue, extra_buttons=[self.cache_button, self.source_button])

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

    def on_extras_confirmed(self, extra_store):
        """Resume install when user has selected extras to download"""
        selected_extras = []

        def save_extra(model, path, iter_):
            selected, _inconsistent, extra, _label = model[iter_]
            if selected and extra:
                selected_extras.append(extra)

        extra_store.foreach(save_extra)

        self.selected_extras = selected_extras
        GLib.idle_add(self.on_extras_ready)

    def on_extras_ready(self, *args):
        self.load_installer_files_page()

    # Installer Files & Downloading Page
    #
    # This page shows the files that are needed, and can download them. The user can
    # also select pre-existing files. The downloading page uses the same page widget,
    # but different buttons at the bottom.

    def load_installer_files_page(self):
        if self.installation_kind == InstallationKind.UPDATE:
            patch_version = self.interpreter.installer.version
        else:
            patch_version = None

        AsyncCall(
            self.interpreter.installer.prepare_game_files, self.on_files_prepared, self.selected_extras, patch_version
        )

    def on_files_prepared(self, _result, error):
        if error:
            self._handle_callback_error(error)
            return

        if not self.interpreter.installer.files:
            logger.debug("Installer doesn't require files")
            self.launch_installer_commands()
            return

        logger.debug("Game files prepared.")
        self.installer_files_box.load_installer(self.interpreter.installer)
        self.stack.navigate_to_page(self.present_installer_files_page)

    def create_installer_files_page(self):
        return Gtk.ScrolledWindow(
            hexpand=True,
            vexpand=True,
            child=self.installer_files_box,
            visible=True,
            shadow_type=Gtk.ShadowType.ETCHED_IN,
        )

    def present_installer_files_page(self):
        """Show installer screen with the file picker / downloader"""
        logger.debug("Presenting installer files page")
        self.set_status(_("Please review the files needed for the installation then click 'Install'"))
        self.stack.present_page("installer_files")
        self.display_install_button(self.on_files_confirmed, sensitive=self.installer_files_box.is_ready)

    def present_downloading_files_page(self):
        def on_exit_page():
            self.installer_files_box.stop_all()

        self.set_status(_("Downloading game data"))
        self.stack.present_page("installer_files")
        self.display_install_button(None, sensitive=False)
        return on_exit_page

    def on_files_ready(self, _widget, files_ready):
        """Toggle state of continue button based on ready state"""
        self.display_install_button(self.on_files_confirmed, sensitive=files_ready)

    def on_files_confirmed(self, _button):
        """Call this when the user confirms the install files
        This will start the downloads.
        """
        try:
            self.installer_files_box.start_all()
            self.stack.jump_to_page(self.present_downloading_files_page)
        except PermissionError as ex:
            raise ScriptingError(_("Unable to get files: %s") % ex) from ex

    def on_files_available(self, widget):
        """All files are available, continue the install"""
        logger.info("All files are available, continuing install")
        self.interpreter.game_files = widget.get_game_files()
        # Idle-add here to ensure that the launch occurs after
        # on_files_confirmed(), since they can race when no actual
        # download is required.
        GLib.idle_add(self.launch_installer_commands)

    def launch_installer_commands(self):
        logger.info("Launching installer commands")
        self.install_in_progress = True
        self.load_spinner_page(_("Installing game data"))
        self.stack.discard_navigation()  # once we really start installing, no going back!
        self.interpreter.installer.install_extras()
        self.interpreter.launch_installer_commands()

    # Spinner Page
    #
    # Provides a generic progress spinner and displays a status. The back button
    # is disabled for this page.

    def load_spinner_page(self, status, cancellable=True, extra_buttons=None):
        def present_spinner_page():
            """Show a spinner in the middle of the view"""

            def on_exit_page():
                self.stack.set_back_allowed(True)

            self.set_status(status)
            self.stack.present_page("spinner")

            if cancellable:
                self.display_cancel_button(extra_buttons=extra_buttons)
            else:
                self.display_buttons(extra_buttons or [])

            self.stack.set_back_allowed(False)
            return on_exit_page

        self.stack.jump_to_page(present_spinner_page)

    def create_spinner_page(self):
        spinner = Gtk.Spinner(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        spinner.start()
        return spinner

    # Log Page
    #
    # This page shos a LogTextView where an installer command can display
    # output. This appears when summons by the installer script.

    def load_log_page(self):
        self.stack.jump_to_page(self.present_log_page)

    def create_log_page(self):
        log_textview = LogTextView(self.log_buffer)
        return Gtk.ScrolledWindow(hexpand=True, vexpand=True, child=log_textview, shadow_type=Gtk.ShadowType.ETCHED_IN)

    def present_log_page(self):
        """Creates a TextBuffer and attach it to a command"""

        def on_exit_page():
            self.error_reporter = saved_reporter

        def on_error(error):
            self.set_status(str(error))

        saved_reporter = self.error_reporter
        self.error_reporter = on_error
        self.stack.present_page("log")
        self.display_cancel_button()
        return on_exit_page

    # Input Menu Page
    #
    # This page shows a list of choices to the user, and calls
    # back into a callback when the user makes a choice. This is summoned
    # by the installer script as well.

    def load_input_menu_page(self, alias, options, preselect, callback):
        def present_input_menu_page():
            """Display an input request as a dropdown menu with options."""

            def on_continue(_button):
                try:
                    callback(alias, combobox)
                    self.stack.restore_current_page(previous_page)
                except Exception as err:
                    # If the callback fails, the installation does not continue
                    # to run, so we'll go to error page.
                    self.load_error_page(err)

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
            combobox.set_valign(Gtk.Align.START)
            combobox.set_active_id(preselect)
            combobox.connect("changed", self.on_input_menu_changed)

            self.stack.present_replacement_page("input_menu", combobox)
            self.display_continue_button(on_continue)
            self.continue_button.grab_focus()
            self.on_input_menu_changed(combobox)

        # we must use jump_to_page() here since it would be unsave to return
        # back to this page and re-execute the callback.
        previous_page = self.stack.save_current_page()
        self.stack.jump_to_page(present_input_menu_page)

    def on_input_menu_changed(self, combobox):
        """Enable continue button if a non-empty choice is selected"""
        self.continue_button.set_sensitive(bool(combobox.get_active_id()))

    # Ask for Disc Page
    #
    # This page asks the user for a disc; it also has a callback used when
    # the user selects a disc. Again, this is summoned by the installer script.

    def load_ask_for_disc_page(self, message, requires, installer, callback):
        def present_ask_for_disc_page():
            """Ask the user to do insert a CD-ROM."""

            def wrapped_callback(*args, **kwargs):
                try:
                    callback(*args, **kwargs)
                    self.stack.restore_current_page(previous_page)
                except Exception as err:
                    # If the callback fails, the installation does not continue
                    # to run, so we'll go to error page.
                    self.load_error_page(err)

            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            label = MarkupLabel(message)
            vbox.pack_start(label, False, False, 0)

            buttons_box = Gtk.Box()
            buttons_box.set_margin_top(40)
            buttons_box.set_margin_bottom(40)
            vbox.pack_start(buttons_box, False, False, 0)

            if not LINUX_SYSTEM.is_flatpak():
                # Lutris flatplak doesn't autodetect files on CD-ROM properly
                # and selecting this option doesn't let the user click "Back"
                # so the only option is to cancel the install.
                autodetect_button = Gtk.Button(label=_("Autodetect"))
                autodetect_button.connect("clicked", wrapped_callback, requires)
                autodetect_button.grab_focus()
                buttons_box.pack_start(autodetect_button, True, True, 40)

            browse_button = Gtk.Button(label=_("Browse…"))
            callback_data = {"callback": wrapped_callback, "requires": requires}
            browse_button.connect("clicked", self.on_browse_clicked, callback_data)
            buttons_box.pack_start(browse_button, True, True, 40)

            self.stack.present_replacement_page("ask_for_disc", vbox)
            if installer.runner == "wine":
                eject_button = Gtk.Button(_("Eject"), halign=Gtk.Align.END)
                eject_button.connect("clicked", self.on_eject_clicked)
                vbox.pack_end(eject_button, False, False, 0)
                vbox.pack_end(Gtk.Separator(), False, False, 0)

            vbox.show_all()
            self.display_cancel_button()

        previous_page = self.stack.save_current_page()
        self.stack.jump_to_page(present_ask_for_disc_page)

    def on_browse_clicked(self, widget, callback_data):
        dialog = DirectoryDialog(_("Select the folder where the disc is mounted"), parent=self)
        folder = dialog.folder
        callback = callback_data["callback"]
        requires = callback_data["requires"]
        callback(widget, requires, folder)

    def on_eject_clicked(self, _widget, data=None):
        self.interpreter.eject_wine_disc()

    # Error Message Page
    #
    # This is used to display an error; such an error halts the installation,
    # and isn't recoverable. Used by the installer script.

    def load_error_page(self, error: BaseException) -> None:
        self.stack.navigate_to_page(lambda *x: self.present_error_page(error))
        self.stack.set_back_allowed(False)
        self.cancel_button.grab_focus()

    def present_error_page(self, error: BaseException) -> None:
        self.set_status(str(error))

        is_expected = hasattr(error, "is_expected") and error.is_expected

        if is_expected:
            formatted = traceback.format_exception(type(error), error, error.__traceback__)
            formatted = "\n".join(formatted).strip()

            log = get_log_contents()
            if log:
                formatted = f"{formatted}\n\nLutris log:\n{log}".strip()

            self.error_details_buffer.set_text(formatted)

        self.error_details_box.set_visible(not is_expected)

        self.stack.present_page("error")
        self.display_cancel_button()

    def create_error_page(self) -> Gtk.Widget:
        def on_copy_clicked(_button):
            status = self.get_status()
            details = self.error_details_buffer.get_text(
                self.error_details_buffer.get_start_iter(), self.error_details_buffer.get_end_iter(), True
            )
            text = f"{status}\n\n{details}"
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(text, -1)

        error_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        label = Gtk.Label(xalign=0.0, wrap=True)
        label.set_markup(
            _(
                "An unexpected error has occurred while installing this game. "
                "Please share the details below with the Lutris team on "
                "<a href='https://github.com/lutris/lutris'>GitHub</a> or "
                "<a href='https://discordapp.com/invite/Pnt5CuY'>Discord</a>."
            )
        )
        self.error_details_box.pack_start(label, False, False, 0)

        frame = Gtk.Frame(shadow_type=Gtk.ShadowType.ETCHED_IN)

        details_textview = Gtk.TextView(editable=False, buffer=self.error_details_buffer)

        scrolledwindow = Gtk.ScrolledWindow()
        scrolledwindow.add(details_textview)
        frame.add(scrolledwindow)
        self.error_details_box.pack_start(frame, True, True, 0)
        error_box.pack_start(self.error_details_box, True, True, 0)

        copy_button = Gtk.Button(_("Copy Details to Clipboard"), halign=Gtk.Align.START)
        error_box.pack_end(copy_button, False, True, 0)
        copy_button.connect("clicked", on_copy_clicked)

        return error_box

    # Finished Page
    #
    # This is used to inidcate that the install is complete. The user
    # can launch the game a this point, or just close out of the window.
    #
    # Loading this page does some final installation steps before the UI updates.

    def load_finish_install_page(self, game_id, status):
        if self.config.get("create_desktop_shortcut"):
            AsyncCall(self.create_shortcut, None, True)
        if self.config.get("create_menu_shortcut"):
            AsyncCall(self.create_shortcut, None)

        # Save game to trigger a game-updated signal,
        # but take care not to create a blank game
        if game_id:
            game = Game(game_id)
            if self.config.get("create_steam_shortcut"):
                AsyncCall(steam_shortcut.create_shortcut, None, game)
            game.save()

        self.install_in_progress = False
        self.install_complete = True

        self.stack.jump_to_page(lambda *x: self.present_finished_page(game_id, status))
        self.stack.discard_navigation()
        self.cancel_button.grab_focus()

        if not self.is_active():
            self.set_urgency_hint(True)  # Blink in taskbar
            self.connect("focus-in-event", self.on_window_focus)

    def present_finished_page(self, game_id, status):
        self.set_status(status)
        self.stack.present_page("nothing")
        self.display_continue_button(self.on_launch_clicked, continue_button_label=_("_Launch"), suggested_action=False)

    def on_launch_clicked(self, button):
        """Launch a game after it's been installed."""
        button.set_sensitive(False)
        game = Game(self.interpreter.installer.game_id)
        if game.is_db_stored:
            # Since we're closing this window, we can't use
            # it as the delegate.
            application = Gio.Application.get_default()
            game.launch(application.launch_ui_delegate)
        else:
            logger.error("Game has no ID, launch button should not be drawn")
        self.on_cancel_clicked(button)

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
    def display_continue_button(
        self, handler, continue_button_label=_("_Continue"), sensitive=True, suggested_action=True, extra_buttons=None
    ):
        """This shows the continue button, the close button, and any extra buttons you
        indicate. This will also set the label and sensitivity of the continue button.

        Finally, you cna provide the clicked handler for the continue button,
        though that can be None to leave it disconnected.

        We call this repeatedly, as we arrive at each page. Each call disconnects
        the previous clicked handler and connects the new one.
        """
        self.continue_button.set_label(continue_button_label)
        self.continue_button.set_sensitive(sensitive)

        style_context = self.continue_button.get_style_context()

        if suggested_action:
            style_context.add_class("suggested-action")
        else:
            style_context.remove_class("suggested-action")

        if self.continue_handler:
            self.continue_button.disconnect(self.continue_handler)

        if handler:
            self.continue_handler = self.continue_button.connect("clicked", handler)
        else:
            self.continue_handler = None

        buttons = [self.continue_button] + (extra_buttons or [])
        self.display_buttons(buttons)

    def display_install_button(self, handler, sensitive=True):
        """Displays the continue button, but labels it 'Install'."""
        self.display_continue_button(
            handler, continue_button_label=_("_Install"), sensitive=sensitive, extra_buttons=[self.source_button]
        )

    def display_cancel_button(self, extra_buttons=None):
        self.display_buttons(extra_buttons or [])

    def display_buttons(self, buttons):
        """Shows exactly the buttons given, and hides the others. Updates the close button
        according to whether the install has started."""

        style_context = self.cancel_button.get_style_context()

        if self.install_in_progress:
            self.cancel_button.set_label(_("_Abort"))
            self.cancel_button.set_tooltip_text(_("Abort and revert the installation"))
            style_context.add_class("destructive-action")
        else:
            self.cancel_button.set_label(_("_Close") if self.install_complete else _("Cancel"))
            self.cancel_button.set_tooltip_text("")
            style_context.remove_class("destructive-action")

        all_buttons = [self.cache_button, self.source_button, self.continue_button]

        for b in all_buttons:
            b.set_visible(b in buttons)

        any_visible = False
        for b in self.menu_box.get_children():
            if b.get_visible():
                any_visible = True
                break
        self.menu_button.set_visible(any_visible)
