import os
import time
from gi.repository import Gtk
import yaml

from lutris import installer
from lutris.game import Game
from lutris.gui.widgets import DownloadProgressBox, FileChooserEntry
from lutris.util.log import logger
from lutris.util.strings import add_url_tags


class InstallerDialog(Gtk.Window):
    """ Gtk Dialog used during the install process """
    game_dir = None
    download_progress = None

    def __init__(self, game_ref, parent=None):
        Gtk.Window.__init__(self)
        self.interpreter = None
        self.selected_directory = None  # Latest directory chosen by user
        self.parent = parent
        self.game_ref = game_ref
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

        self.install_button = Gtk.Button(label='Install')
        self.install_button.connect('clicked', self.on_install_clicked)
        self.action_buttons.add(self.install_button)

        self.continue_button = Gtk.Button(label='Continue')
        self.continue_button.set_margin_left(20)
        self.continue_handler = None
        self.action_buttons.add(self.continue_button)

        self.play_button = Gtk.Button(label="Launch game")
        self.play_button.set_margin_left(20)
        self.play_button.connect('clicked', self.launch_game)
        self.action_buttons.add(self.play_button)

        self.close_button = Gtk.Button(label="Close")
        self.close_button.set_margin_left(20)
        self.close_button.connect('clicked', self.close)
        self.action_buttons.add(self.close_button)

        if os.path.isfile(game_ref):
            # local script
            logger.debug("Opening script: %s", game_ref)
            self.scripts = yaml.safe_load(open(game_ref, 'r').read())
        else:
            self.scripts = installer.fetch_script(self, game_ref)
        if not self.scripts:
            self.destroy()
            return
        if not isinstance(self.scripts, list):
            self.scripts = [self.scripts]
        self.show_all()
        self.close_button.hide()
        self.play_button.hide()
        self.install_button.hide()

        self.choose_installer()

    def launch_install(self, script_index):
        script = self.scripts[script_index]
        self.interpreter = installer.ScriptInterpreter(script, self)
        game_name = self.interpreter.game_name.replace('&', '&amp;')
        self.title_label.set_markup(u"<b>Installing {}</b>".format(game_name))
        self.continue_install()

    def continue_install(self):
        # Target chooser
        if not self.interpreter.requires and self.interpreter.files:
            self.set_message("Select installation directory")
            default_path = self.interpreter.default_target
            self.set_location_entry(self.on_target_changed, 'folder',
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
        self.continue_button.connect('clicked', self.on_file_selected)
        self.install_button.grab_focus()
        self.install_button.show()

    def choose_installer(self):
        self.title_label.set_markup('<b>Select which version to install</b>')
        self.installer_choice_box = Gtk.VBox()
        self.installer_choice = 0
        radio_group = None

        # Build list
        for index, script in enumerate(self.scripts):
            label = script['version']
            btn = Gtk.RadioButton.new_with_label_from_widget(radio_group, label)
            btn.connect('toggled', self.on_installer_toggled, index)
            self.installer_choice_box.pack_start(btn, False, False, 0)
            if not radio_group:
                radio_group = btn

        self.widget_box.pack_start(self.installer_choice_box, False, False, 10)
        self.installer_choice_box.show_all()

        self.continue_button.grab_focus()
        self.continue_button.show()
        self.continue_handler = self.continue_button.connect(
            'clicked', self.on_installer_selected
        )

    def on_installer_toggled(self, btn, script_index):
        if btn.get_active():
            self.installer_choice = script_index

    def on_installer_selected(self, widget):
        self.launch_install(self.installer_choice)
        self.installer_choice_box.destroy()
        self.show_non_empty_warning()

    def on_destroy(self, widget):
        if self.interpreter:
            self.interpreter.cleanup()
        if self.parent:
            self.destroy()
        else:
            Gtk.main_quit()

    def show_non_empty_warning(self):
        if not self.location_entry:
            return
        path = self.location_entry.get_text()
        if os.path.exists(path) and os.listdir(path):
            self.non_empty_label.show()
        else:
            self.non_empty_label.hide()

    def set_message(self, message):
        label = Gtk.Label()
        label.set_markup('<b>%s</b>' % add_url_tags(message))
        label.set_max_width_chars(80)
        label.set_property('wrap', True)
        label.set_alignment(0, 0)
        label.show()
        self.widget_box.pack_start(label, False, False, 10)

    def set_location_entry(self, callback, action=None, default_path=None):
        if action == 'file':
            action = Gtk.FileChooserAction.OPEN
        elif action == 'folder':
            action = Gtk.FileChooserAction.SELECT_FOLDER

        if self.location_entry:
            self.location_entry.destroy()
        self.location_entry = FileChooserEntry(action, default_path)
        self.location_entry.show_all()
        if callback:
            self.location_entry.entry.connect('changed', callback)
        else:
            self.install_button.set_visible(False)
            self.continue_button.grab_focus()
            self.continue_button.show()
        self.widget_box.pack_start(self.location_entry, False, False, 0)

    def on_target_changed(self, text_entry):
        """ Sets the installation target for the game """
        path = text_entry.get_text()
        self.interpreter.target_path = path
        self.show_non_empty_warning()

    def on_install_clicked(self, button):
        button.hide()
        self.interpreter.iter_game_files()

    def ask_user_for_file(self, message):
        self.clean_widgets()
        self.set_message(message)
        if self.selected_directory:
            path = self.selected_directory
        else:
            path = os.path.expanduser('~')
        self.set_location_entry(None, 'file', default_path=path)

    def on_file_selected(self, widget):
        file_path = os.path.expanduser(self.location_entry.get_text())
        if os.path.isfile(file_path):
            self.selected_directory = os.path.dirname(file_path)
        else:
            return
        self.interpreter.file_selected(file_path)

    def clean_widgets(self):
        for child_widget in self.widget_box.get_children():
            child_widget.destroy()

    def set_status(self, text):
        self.status_label.set_text(text)

    def add_spinner(self):
        self.clean_widgets()
        spinner = Gtk.Spinner()
        self.widget_box.pack_start(spinner, True, False, 10)
        spinner.show()
        spinner.start()

    def start_download(self, file_uri, dest_file, callback=None, data=None):
        self.clean_widgets()
        logger.debug("Downloading %s to %s", file_uri, dest_file)
        self.download_progress = DownloadProgressBox(
            {'url': file_uri, 'dest': dest_file}, cancelable=True
        )
        callback_function = callback or self.download_complete
        self.download_progress.connect('complete', callback_function, data)
        self.widget_box.pack_start(self.download_progress, False, False, 10)
        self.download_progress.show()
        self.download_progress.start()

    def wait_for_user_action(self, message, callback, data=None):
        time.sleep(0.3)
        self.clean_widgets()
        label = Gtk.Label(label=message)
        label.set_use_markup(True)
        self.widget_box.add(label)
        label.show()
        button = Gtk.Button(label='Ok')
        button.connect('clicked', callback, data)
        self.widget_box.add(button)
        button.grab_focus()
        button.show()

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

    def download_complete(self, widget, data, more_data=None):
        """Action called on a completed download"""
        self.interpreter.iter_game_files()

    def on_steam_downloaded(self, widget, *args, **kwargs):
        self.interpreter.complete_steam_install(widget.dest)

    def on_install_finished(self):
        """Actual game installation"""
        self.status_label.set_text("Installation finished !")
        self.clean_widgets()
        self.notify_install_success()
        self.continue_button.hide()
        self.install_button.hide()
        self.play_button.show()
        self.close_button.grab_focus()
        self.close_button.show()
        if not self.is_active():
            self.set_urgency_hint(True)  # Blink in taskbar
            self.connect('focus-in-event', self.on_window_focus)

    def notify_install_success(self):
        if self.parent:
            self.parent.view.emit('game-installed', self.game_ref)

    def on_window_focus(self, widget, *args):
        self.set_urgency_hint(False)

    def on_install_error(self, message):
        self.status_label.set_text(message)
        self.clean_widgets()
        self.close_button.grab_focus()
        self.close_button.show()

    def launch_game(self, widget, _data=None):
        """Launch a game after it's been installed"""
        widget.set_sensitive(False)
        game = Game(self.interpreter.game_slug)
        game.play()
        self.close(widget)

    def close(self, _widget):
        self.destroy()
