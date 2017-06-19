# -*- coding: utf-8 -*-
import os
import time
import yaml
import webbrowser

from gi.repository import Gtk, Pango

from lutris import pga, settings
from lutris.services import xdg
from lutris.installer import interpreter
from lutris.installer.errors import ScriptingError
from lutris.game import Game
from lutris.gui.config_dialogs import AddGameDialog
from lutris.gui.dialogs import NoInstallerDialog, DirectoryDialog, InstallerSourceDialog
from lutris.gui.widgets.download_progress import DownloadProgressBox
from lutris.gui.widgets.common import FileChooserEntry
from lutris.gui.logwindow import LogTextView
from lutris.util import jobs
from lutris.util import system
from lutris.util.log import logger
from lutris.util.strings import add_url_tags


class InstallerDialog(Gtk.Window):
    """GUI for the install process."""
    game_dir = None
    download_progress = None

    def __init__(self, game_slug=None, installer_file=None, revision=None, parent=None):
        Gtk.Window.__init__(self)
        self.set_default_icon_name('lutris')
        self.interpreter = None
        self.selected_directory = None  # Latest directory chosen by user
        self.parent = parent
        self.game_slug = game_slug
        self.installer_file = installer_file
        self.revision = revision

        self.log_buffer = None
        self.log_textview = None

        # Dialog properties
        self.set_size_request(600, 480)
        self.set_default_size(600, 480)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(False)

        self.vbox = Gtk.VBox()
        self.add(self.vbox)

        # Default signals
        self.connect('destroy', self.on_destroy)

        # GUI Setup

        # Title label
        self.title_label = Gtk.Label()
        self.vbox.pack_start(self.title_label, False, False, 20)

        self.status_label = Gtk.Label()
        self.status_label.set_max_width_chars(80)
        self.status_label.set_property('wrap', True)
        self.status_label.set_selectable(True)
        self.vbox.pack_start(self.status_label, False, False, 15)

        # Main widget box
        self.widget_box = Gtk.VBox()
        self.widget_box.set_margin_right(25)
        self.widget_box.set_margin_left(25)
        self.vbox.pack_start(self.widget_box, True, True, 15)

        self.location_entry = None

        # Separator
        self.vbox.pack_start(Gtk.HSeparator(), False, False, 0)

        # Buttons
        action_buttons_alignment = Gtk.Alignment.new(0.95, 0, 0.15, 0)
        self.action_buttons = Gtk.HBox()
        action_buttons_alignment.add(self.action_buttons)
        self.vbox.pack_start(action_buttons_alignment, False, True, 20)

        self.cancel_button = Gtk.Button.new_with_mnemonic("C_ancel")
        self.cancel_button.set_tooltip_text("Abort and revert the "
                                            "installation")
        self.cancel_button.connect('clicked', self.on_cancel_clicked)
        self.action_buttons.add(self.cancel_button)

        self.eject_button = self.add_button("_Eject", self.on_eject_clicked)
        self.source_button = self.add_button("_View source", self.on_source_clicked)
        self.install_button = self.add_button("_Install", self.on_install_clicked)
        self.continue_button = self.add_button("_Continue")
        self.play_button = self.add_button("_Launch game", self.launch_game)
        self.close_button = self.add_button("_Close", self.close)

        self.continue_handler = None

        self.get_scripts()

        # l33t haxx to make Window.present() actually work.
        self.set_keep_above(True)
        self.present()
        self.set_keep_above(False)
        self.present()

    def add_button(self, label, handler=None):
        button = Gtk.Button.new_with_mnemonic(label)
        button.set_margin_left(20)
        if handler:
            button.connect('clicked', handler)
        self.action_buttons.add(button)
        return button

    # ---------------------------
    # "Get installer" stage
    # ---------------------------

    def get_scripts(self):
        if system.path_exists(self.installer_file):
            # local script
            logger.debug("Opening script: %s", self.installer_file)
            scripts = yaml.safe_load(open(self.installer_file, 'r').read())
            self.on_scripts_obtained(scripts)
        else:
            jobs.AsyncCall(interpreter.fetch_script, self.on_scripts_obtained,
                           self.game_slug, self.revision)

    def on_scripts_obtained(self, scripts, _error=None):
        if not scripts:
            self.destroy()
            self.run_no_installer_dialog()
            return

        if not isinstance(scripts, list):
            scripts = [scripts]
        self.scripts = scripts
        self.show_all()
        self.close_button.hide()
        self.play_button.hide()
        self.install_button.hide()
        self.source_button.hide()
        self.eject_button.hide()

        self.choose_installer()

    def run_no_installer_dialog(self):
        """Open dialog for 'no script available' situation."""
        dlg = NoInstallerDialog(self)
        if dlg.result == dlg.MANUAL_CONF:
            game_data = pga.get_game_by_field(self.game_slug, 'slug')
            game = Game(game_data['id'])
            AddGameDialog(
                self.parent,
                game=game,
                callback=lambda: self.notify_install_success(game_data['id'])
            )
        elif dlg.result == dlg.NEW_INSTALLER:
            webbrowser.open(settings.GAME_URL % self.game_slug)

    # ---------------------------
    # "Choose installer" stage
    # ---------------------------

    def choose_installer(self):
        """Stage where we choose an install script."""
        self.title_label.set_markup('<b>Select which version to install</b>')
        self.installer_choice_box = Gtk.VBox()
        self.installer_choice = 0
        radio_group = None

        # Build list
        for index, script in enumerate(self.scripts):
            for item in ['description', 'notes']:
                script[item] = script.get(item) or ''
            for item in ['runner', 'version']:
                if item not in script:
                    raise ScriptingError('Missing field "%s" in install script' % item)

            runner = script['runner']
            version = script['version']
            label = "{} ({})".format(version, runner)
            btn = Gtk.RadioButton.new_with_label_from_widget(radio_group,
                                                             label)
            btn.connect('toggled', self.on_installer_toggled, index)
            self.installer_choice_box.pack_start(btn, False, False, 10)
            if not radio_group:
                radio_group = btn

        def _create_label(padding, text):
            label = Gtk.Label()
            label.set_max_width_chars(60)
            label.set_line_wrap(True)
            label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            label.set_alignment(0, .5)
            label.set_margin_left(50)
            label.set_margin_right(50)
            label.set_markup(text)
            self.installer_choice_box.pack_start(label, True, True, padding)
            return label

        self.description_label = _create_label(
            10, "<i><b>{}</b></i>".format(self.scripts[0]['description'])
        )
        self.notes_label = _create_label(
            5, "<i>{}</i>".format(self.scripts[0]['notes'])
        )

        self.widget_box.pack_start(self.installer_choice_box, False, False, 10)
        self.installer_choice_box.show_all()

        self.continue_button.grab_focus()
        self.continue_button.show()
        self.continue_handler = self.continue_button.connect(
            'clicked', self.on_installer_selected
        )

    def on_installer_toggled(self, btn, script_index):
        description = self.scripts[script_index]['description']
        self.description_label.set_markup(
            "<i><b>{}</b></i>".format(description)
        )
        self.notes_label.set_markup(
            "<i>{}</i>".format(self.scripts[script_index]['notes'])
        )
        if btn.get_active():
            self.installer_choice = script_index

    def on_installer_selected(self, widget):
        self.prepare_install(self.installer_choice)
        self.installer_choice_box.destroy()
        self.show_non_empty_warning()

    def prepare_install(self, script_index):
        script = self.scripts[script_index]
        self.interpreter = interpreter.ScriptInterpreter(script, self)
        game_name = self.interpreter.game_name.replace('&', '&amp;')
        self.title_label.set_markup(u"<b>Installing {}</b>".format(game_name))
        self.select_install_folder()

    # --------------------------
    # "Select install dir" stage
    # --------------------------

    def select_install_folder(self):
        """Stage where we select the install directory."""
        if self.interpreter.creates_game_folder:
            self.set_message("Select installation directory")
            default_path = self.interpreter.get_default_target()
            self.set_path_chooser(self.on_target_changed, 'folder',
                                  default_path)
            self.non_empty_label = Gtk.Label()
            self.non_empty_label.set_markup(
                "<b>Warning!</b> The selected path "
                "contains files, installation might not work properly."
            )
            self.widget_box.pack_start(self.non_empty_label, False, False, 10)
        else:
            self.set_message("Click install to continue")
        if self.continue_handler:
            self.continue_button.disconnect(self.continue_handler)
        self.continue_button.hide()
        self.source_button.show()
        self.install_button.grab_focus()
        self.install_button.show()

    def on_target_changed(self, text_entry):
        """Set the installation target for the game."""
        path = text_entry.get_text()
        self.interpreter.target_path = os.path.expanduser(path)
        self.show_non_empty_warning()

    def show_non_empty_warning(self):
        """Display a warning if destination folder is not empty."""
        if not self.location_entry:
            return
        path = self.location_entry.get_text()
        if os.path.exists(path) and os.listdir(path):
            self.non_empty_label.show()
        else:
            self.non_empty_label.hide()

    # ---------------------
    # "Get the files" stage
    # ---------------------

    def on_install_clicked(self, button):
        """Let the interpreter take charge of the next stages."""
        button.hide()
        self.source_button.hide()
        self.interpreter.check_runner_install()

    def ask_user_for_file(self, message):
        self.clean_widgets()
        self.set_message(message)
        if self.selected_directory:
            path = self.selected_directory
        else:
            path = os.path.expanduser('~')
        self.set_path_chooser(None, 'file', default_path=path)

    def set_path_chooser(self, callback_on_changed, action=None,
                         default_path=None):
        """Display a file/folder chooser."""
        if action == 'file':
            title = 'Select file'
            action = Gtk.FileChooserAction.OPEN
        elif action == 'folder':
            title = 'Select folder'
            action = Gtk.FileChooserAction.SELECT_FOLDER

        if self.location_entry:
            self.location_entry.destroy()
        self.location_entry = FileChooserEntry(title, action, default_path)
        self.location_entry.show_all()
        if callback_on_changed:
            self.location_entry.entry.connect('changed', callback_on_changed)
        else:
            self.install_button.set_visible(False)
            self.continue_button.connect('clicked', self.on_file_selected)
            self.continue_button.grab_focus()
            self.continue_button.show()
        self.widget_box.pack_start(self.location_entry, False, False, 0)

    def on_file_selected(self, widget):
        file_path = os.path.expanduser(self.location_entry.get_text())
        if os.path.isfile(file_path):
            self.selected_directory = os.path.dirname(file_path)
        else:
            logger.warning('%s is not a file', file_path)
            return
        self.interpreter.file_selected(file_path)

    def start_download(self, file_uri, dest_file, callback=None, data=None):
        self.clean_widgets()
        logger.debug("Downloading %s to %s", file_uri, dest_file)
        self.download_progress = DownloadProgressBox(
            {'url': file_uri, 'dest': dest_file}, cancelable=True
        )
        self.download_progress.cancel_button.hide()
        callback = callback or self.on_download_complete
        self.download_progress.connect('complete', callback, data)
        self.widget_box.pack_start(self.download_progress, False, False, 10)
        self.download_progress.show()
        self.download_progress.start()
        self.interpreter.abort_current_task = self.download_progress.cancel

    def on_download_complete(self, widget, data, more_data=None):
        """Action called on a completed download."""
        self.interpreter.abort_current_task = None
        self.interpreter.iter_game_files()

    # ----------------
    # "Commands" stage
    # ----------------

    def ask_for_disc(self, message, callback, requires):
        """Ask the user to do insert a CD-ROM."""
        time.sleep(0.3)
        self.clean_widgets()
        label = Gtk.Label(label=message)
        label.set_use_markup(True)
        self.widget_box.add(label)
        label.show()

        buttons_box = Gtk.Box()
        buttons_box.show()
        buttons_box.set_margin_top(40)
        buttons_box.set_margin_bottom(40)
        self.widget_box.add(buttons_box)

        autodetect_button = Gtk.Button(label='Autodetect')
        autodetect_button.connect('clicked', callback, requires)
        autodetect_button.grab_focus()
        autodetect_button.show()
        buttons_box.pack_start(autodetect_button, True, True, 40)

        browse_button = Gtk.Button(label='Browse…')
        callback_data = {
            'callback': callback,
            'requires': requires
        }
        browse_button.connect('clicked', self.on_browse_clicked, callback_data)
        browse_button.show()
        buttons_box.pack_start(browse_button, True, True, 40)

    def on_browse_clicked(self, widget, callback_data):
        dialog = DirectoryDialog("Select the folder where the disc is mounted",
                                 parent=self)
        folder = dialog.folder
        callback = callback_data['callback']
        requires = callback_data['requires']
        callback(widget, requires, folder)

    def on_eject_clicked(self, widget, data=None):
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
            'clicked', callback, alias, combobox)
        if not preselect:
            self.continue_button.set_sensitive(False)
        self.continue_button.grab_focus()
        self.continue_button.show()

    def on_input_menu_changed(self, widget):
        if widget.get_active_id():
            self.continue_button.set_sensitive(True)

    # ----------------
    # "Finalize" stage
    # ----------------

    def on_install_finished(self):
        """Actual game installation."""
        self.status_label.set_text("Installation finished!")
        self.notify_install_success()
        self.clean_widgets()

        # Shortcut checkboxes
        self.desktop_shortcut_box = Gtk.CheckButton("Create desktop shortcut")
        self.menu_shortcut_box = Gtk.CheckButton("Create application menu "
                                                 "shortcut")
        self.widget_box.pack_start(self.desktop_shortcut_box, False, False, 5)
        self.widget_box.pack_start(self.menu_shortcut_box, False, False, 5)
        self.widget_box.show_all()

        if settings.read_setting('create_desktop_shortcut') == 'True':
            self.desktop_shortcut_box.set_active(True)
        if settings.read_setting('create_menu_shortcut') == 'True':
            self.menu_shortcut_box.set_active(True)

        self.connect('destroy', self.create_shortcuts)

        # Buttons
        self.eject_button.hide()
        self.cancel_button.hide()
        self.continue_button.hide()
        self.install_button.hide()
        self.source_button.hide()
        self.play_button.show()
        self.close_button.grab_focus()
        self.close_button.show()

        if not self.is_active():
            self.set_urgency_hint(True)  # Blink in taskbar
            self.connect('focus-in-event', self.on_window_focus)

    def notify_install_success(self, game_id=None):

        # Nothing to notify in case of extends scripts
        if self.interpreter.extends:
            return

        game_id = game_id or self.interpreter.game_id
        if self.parent:
            self.parent.view.emit('game-installed', game_id)

    def on_window_focus(self, widget, *args):
        self.set_urgency_hint(False)

    def on_install_error(self, message):
        self.set_status(message)
        self.clean_widgets()
        self.cancel_button.grab_focus()

    # --------------------
    # "Afer the end" stage
    # --------------------

    def launch_game(self, widget, _data=None):
        """Launch a game after it's been installed."""
        widget.set_sensitive(False)
        self.close(widget)
        if self.parent:
            self.parent.on_game_run(game_id=self.interpreter.game_id)
        else:
            game = Game(self.interpreter.game_id)
            game.play()

    def close(self, _widget):
        self.destroy()

    def on_destroy(self, widget):
        if self.interpreter:
            self.interpreter.cleanup()
        if self.parent:
            self.destroy()
        else:
            Gtk.main_quit()

    def create_shortcuts(self, *args):
        """Create desktop and global menu shortcuts."""
        game_slug = self.interpreter.game_slug
        game_id = self.interpreter.game_id
        game_name = self.interpreter.game_name
        create_desktop_shortcut = self.desktop_shortcut_box.get_active()
        create_menu_shortcut = self.menu_shortcut_box.get_active()

        if create_desktop_shortcut:
            xdg.create_launcher(game_slug, game_id, game_name, desktop=True)
        if create_menu_shortcut:
            xdg.create_launcher(game_slug, game_id, game_name, menu=True)

        settings.write_setting('create_desktop_shortcut',
                               create_desktop_shortcut)
        settings.write_setting('create_menu_shortcut', create_menu_shortcut)

    # --------------
    # Cancel install
    # --------------

    def on_cancel_clicked(self, _button):
        if self.interpreter:
            self.interpreter.revert()
        self.destroy()
    
    # -------------
    # View Source
    # -------------

    def on_source_clicked(self, _button):
        InstallerSourceDialog(self.interpreter.script_pretty, self.interpreter.game_name, self)

    # -------------
    # Utility stuff
    # -------------

    def clean_widgets(self):
        """Cleanup before displaying the next stage."""
        for child_widget in self.widget_box.get_children():
            child_widget.destroy()

    def set_status(self, text):
        """Display a short status text."""
        self.status_label.set_text(text)

    def set_message(self, message):
        """Display a message."""
        label = Gtk.Label()
        label.set_markup('<b>%s</b>' % add_url_tags(message))
        label.set_max_width_chars(80)
        label.set_property('wrap', True)
        label.set_alignment(0, 0)
        label.show()
        self.widget_box.pack_start(label, False, False, 10)

    def add_spinner(self):
        """Display a wait icon."""
        self.clean_widgets()
        spinner = Gtk.Spinner()
        self.widget_box.pack_start(spinner, False, False, 10)
        spinner.show()
        spinner.start()

    def attach_logger(self, thread):
        self.log_buffer = Gtk.TextBuffer()
        thread.log_buffer = self.log_buffer
        self.log_textview = LogTextView(self.log_buffer)
        scrolledwindow = Gtk.ScrolledWindow(hexpand=True, vexpand=True,
                                            child=self.log_textview)
        scrolledwindow.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        self.widget_box.pack_end(scrolledwindow, True, True, 10)
        scrolledwindow.show()
        self.log_textview.show()
