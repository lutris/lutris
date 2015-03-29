"""Widget generators and their signal handlers"""
import os
from gi.repository import Gtk, Gdk
from lutris.gui.widgets import VBox, Label, PADDING
from lutris.util.log import logger
from lutris.runners import import_runner
from lutris import sysoptions


class ConfigBox(VBox):
    """Dynamically generate a vbox built upon on a python dict."""
    def __init__(self, config_type, caller, game=None):
        super(ConfigBox, self).__init__()
        self.options = None
        # Section of the configuration file to save options in. Can be "game",
        # "runner" or "system"
        self.config_type = config_type
        self.caller = caller
        self.game = game

    def generate_widgets(self):
        """Parse the config dict and generates widget accordingly."""
        # Select what data to load based on caller.
        if self.caller == "system":
            self.real_config = self.lutris_config.system_config
        elif self.caller == "runner":
            self.real_config = self.lutris_config.runner_config
        elif self.caller == "game":
            self.real_config = self.lutris_config.game_config

        # Select part of config to load or create it.
        if self.config_type in self.real_config:
            config = self.real_config[self.config_type]
        else:
            config = self.real_config[self.config_type] = {}

        # Go thru all options.
        for option in self.options:
            option_key = option["option"]
            wrapper = Gtk.VBox()

            # Load value if there is one.
            value = config.get(option_key, option.get('default'))

            # Different types of widgets.
            if option["type"] == "choice":
                self.generate_combobox(wrapper,
                                       option_key,
                                       option["choices"],
                                       option["label"], value)
            elif option["type"] == "choice_with_entry":
                self.generate_combobox(wrapper,
                                       option_key,
                                       option["choices"],
                                       option["label"], value, has_entry=True)
            elif option["type"] == "bool":
                self.generate_checkbox(wrapper, option, value)
            elif option["type"] == "range":
                self.generate_range(wrapper,
                                    option_key,
                                    option["min"],
                                    option["max"],
                                    option["label"], value)
            elif option["type"] == "string":
                if 'label' not in option:
                    raise ValueError("Option %s has no label" % option)
                self.generate_entry(wrapper,
                                    option_key,
                                    option["label"], value)
            elif option["type"] == "directory_chooser":
                self.generate_directory_chooser(wrapper,
                                                option_key,
                                                option["label"],
                                                value)
            elif option["type"] == "file":
                self.generate_file_chooser(wrapper, option, value)
            elif option["type"] == "multiple":
                self.generate_multiple_file_chooser(wrapper,
                                                    option_key,
                                                    option["label"], value)
            elif option["type"] == "label":
                self.generate_label(wrapper, option["label"])
            else:
                raise ValueError("Unknown widget type %s" % option["type"])

            # Tooltip
            helptext = option.get("help")
            if helptext:
                wrapper.props.has_tooltip = True
                wrapper.connect('query-tooltip', self.on_query_tooltip,
                                helptext)

            self.pack_start(wrapper, False, False, 0)

    # Label
    def generate_label(self, wrapper, text):
        """Generate a simple label."""
        label = Label(text)
        label.show()
        wrapper.pack_start(label, False, False, PADDING)

    # Checkbox
    def generate_checkbox(self, wrapper, option, value=None):
        """Generates a checkbox."""
        checkbox = Gtk.CheckButton(label=option["label"])
        if value:
            checkbox.set_active(value)
        checkbox.connect("toggled", self.checkbox_toggle, option['option'])
        checkbox.set_margin_left(20)
        checkbox.show()
        wrapper.pack_start(checkbox, False, False, PADDING)

    def checkbox_toggle(self, widget, option_name):
        """Action for the checkbox's toggled signal."""
        self.real_config[self.config_type][option_name] = widget.get_active()

    # Entry
    def generate_entry(self, wrapper, option_name, label, value=None):
        """Generate an entry box."""
        hbox = Gtk.HBox()
        label = Label(label)
        entry = Gtk.Entry()
        if value:
            entry.set_text(value)
        entry.connect("changed", self.entry_changed, option_name)
        label.set_alignment(0.5, 0.5)
        hbox.pack_start(label, False, False, 20)
        hbox.pack_start(entry, True, True, 20)
        hbox.show_all()
        wrapper.pack_start(hbox, False, False, PADDING)

    def entry_changed(self, entry, option_name):
        """Action triggered for entry 'changed' signal."""
        entry_text = entry.get_text()
        self.real_config[self.config_type][option_name] = entry_text

    # ComboBox
    def generate_combobox(self, wrapper, option_name, choices, label,
                          value=None, has_entry=False):
        """Generate a combobox (drop-down menu)."""
        hbox = Gtk.HBox()
        liststore = Gtk.ListStore(str, str)
        for choice in choices:
            if type(choice) is str:
                choice = [choice, choice]
            liststore.append(choice)

        if has_entry:
            combobox = Gtk.ComboBox.new_with_model_and_entry(liststore)
            combobox.set_entry_text_column(1)
            if value:
                combobox.get_child().set_text(value)
        else:
            combobox = Gtk.ComboBox.new_with_model(liststore)
            cell = Gtk.CellRendererText()
            combobox.pack_start(cell, True)
            combobox.add_attribute(cell, 'text', 0)

            index = selected_index = -1
            for choice in choices:
                if choice[1] == value:
                    selected_index = index + 1
                    break
                index += 1
            combobox.set_active(selected_index)

        combobox.connect('changed', self.on_combobox_change, option_name)
        label = Label(label)
        label.set_alignment(0.5, 0.5)
        hbox.pack_start(label, False, False, 20)
        hbox.pack_start(combobox, True, True, 20)
        hbox.show_all()
        wrapper.pack_start(hbox, False, False, PADDING)

    def on_combobox_change(self, combobox, option):
        """Action triggered on combobox 'changed' signal."""
        if combobox.get_has_entry():
            option_value = combobox.get_child().get_text()
        else:
            model = combobox.get_model()
            active = combobox.get_active()
            if active < 0:
                return None
            option_value = model[active][1]
        self.real_config[self.config_type][option] = option_value

    # Range
    def generate_range(self, wrapper, option_name, min_val, max_val, label,
                       value=None):
        """Generate a ranged spin button."""
        adjustment = Gtk.Adjustment(float(min_val), float(min_val),
                                    float(max_val), 1, 0, 0)
        spin_button = Gtk.SpinButton()
        spin_button.set_adjustment(adjustment)
        if value:
            spin_button.set_value(value)
        spin_button.connect('changed',
                            self.on_spin_button_changed, option_name)
        hbox = Gtk.HBox()
        label = Label(label)
        label.set_alignment(0.5, 0.5)
        hbox.pack_start(label, False, False, 20)
        hbox.pack_start(spin_button, True, True, 20)
        hbox.show_all()
        wrapper.pack_start(hbox, False, False, PADDING)

    def on_spin_button_changed(self, spin_button, option):
        """Action triggered on spin button 'changed' signal."""
        value = spin_button.get_value_as_int()
        self.real_config[self.config_type][option] = value

    # File chooser
    def generate_file_chooser(self, wrapper, option, path=None):
        """Generate a file chooser button to select a file."""
        option_name = option['option']
        label = Label(option['label'])
        hbox = Gtk.HBox()
        file_chooser = Gtk.FileChooserButton("Choose a file for %s" % label)
        file_chooser.set_size_request(200, 30)

        if 'default_path' in option:
            config_key = option['default_path']
            default_path = self.lutris_config.config['system'].get(config_key)
            if default_path and os.path.exists(default_path):
                file_chooser.set_current_folder(default_path)

        file_chooser.set_action(Gtk.FileChooserAction.OPEN)
        file_chooser.connect("file-set", self.on_chooser_file_set, option_name)

        if path:
            # If path is relative, complete with game dir
            if not os.path.isabs(path):
                path = os.path.join(self.game.directory, path)
            file_chooser.unselect_all()
            file_chooser.select_filename(path)
        label.set_alignment(0.5, 0.5)
        hbox.pack_start(label, False, False, 20)
        hbox.pack_start(file_chooser, True, True, 20)
        wrapper.pack_start(hbox, False, False, PADDING)

    # Directory chooser
    def generate_directory_chooser(self, wrapper, option_name, label_text,
                                   value=None):
        """Generate a file chooser button to select a directory."""
        hbox = Gtk.HBox()
        label = Label(label_text)
        directory_chooser = Gtk.FileChooserButton(
            title="Choose a directory for %s" % label_text
        )
        directory_chooser.set_action(Gtk.FileChooserAction.SELECT_FOLDER)
        if value:
            directory_chooser.set_current_folder(value)
        directory_chooser.connect("file-set", self.on_chooser_file_set,
                                  option_name)
        label.set_alignment(0.5, 0.5)
        hbox.pack_start(label, False, False, 20)
        hbox.pack_start(directory_chooser, True, True, 20)
        wrapper.pack_start(hbox, False, False, PADDING)

    def on_chooser_file_set(self, filechooser_widget, option):
        """Action triggered on file select dialog 'file-set' signal."""
        filename = filechooser_widget.get_filename()
        self.real_config[self.config_type][option] = filename

    # Multiple file selector
    def generate_multiple_file_chooser(self, wrapper, option_name, label,
                                       value=None):
        """Generate a multiple file selector."""
        hbox = Gtk.HBox()
        label = Label(label)
        self.files_chooser_dialog = Gtk.FileChooserDialog(
            title="Select files",
            parent=self.get_parent_window(),
            action=Gtk.FileChooserAction.OPEN,
            buttons=(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE,
                     Gtk.STOCK_ADD, Gtk.ResponseType.OK)
        )
        self.files_chooser_dialog.set_select_multiple(True)
        files_chooser_button = Gtk.FileChooserButton(self.files_chooser_dialog)
        files_chooser_button.connect('file-set', self.add_files_callback,
                                     option_name)
        game_path = self.lutris_config.get_path(os.path.expanduser('~'))
        if game_path:
            files_chooser_button.set_current_folder(game_path)
        if value:
            files_chooser_button.set_filename(value[0])

        label.set_alignment(0.5, 0.5)
        hbox.pack_start(label, False, False, 20)
        hbox.pack_start(files_chooser_button, True, True, 20)
        wrapper.pack_start(hbox, False, False, PADDING)
        if value:
            if type(value) == str:
                self.files = [value]
            else:
                self.files = value
        else:
            self.files = []
        self.files_list_store = Gtk.ListStore(str)
        for filename in self.files:
            self.files_list_store.append([filename])
        cell_renderer = Gtk.CellRendererText()
        files_treeview = Gtk.TreeView(self.files_list_store)
        files_column = Gtk.TreeViewColumn("Files", cell_renderer, text=0)
        files_treeview.append_column(files_column)
        files_treeview.connect('key-press-event', self.on_files_treeview_event,
                               option_name)
        treeview_scroll = Gtk.ScrolledWindow()
        treeview_scroll.set_min_content_height(200)
        treeview_scroll.set_policy(Gtk.PolicyType.AUTOMATIC,
                                   Gtk.PolicyType.AUTOMATIC)
        treeview_scroll.add(files_treeview)
        wrapper.add(treeview_scroll)

    def on_files_treeview_event(self, treeview, event, option):
        """Action triggered when a row is deleted from the filechooser."""
        key = event.keyval
        if key == Gdk.KEY_Delete:
            selection = treeview.get_selection()
            (model, treepaths) = selection.get_selected_rows()
            for treepath in treepaths:
                row_index = int(str(treepath))
                treeiter = model.get_iter(treepath)
                model.remove(treeiter)
                self.real_config[self.config_type][option].pop(row_index)

    def add_files_callback(self, button, option=None):
        """Add several files to the configuration"""
        filenames = button.get_filenames()
        files = self.real_config[self.config_type].get(option, [])
        for filename in filenames:
            self.files_list_store.append([filename])
            if filename not in files:
                files.append(filename)
        self.real_config[self.config_type][option] = files
        self.files_chooser_dialog = None

    def on_query_tooltip(self, widget, x, y, keybmode, tooltip, text):
        """Prepare a custom tooltip with a fixed width"""
        label = Label(text)
        label.set_use_markup(True)
        label.set_max_width_chars(60)
        hbox = Gtk.HBox()
        hbox.pack_start(label, False, False, 0)
        hbox.show_all()
        tooltip.set_custom(hbox)
        return True


class GameBox(ConfigBox):
    def __init__(self, lutris_config, caller, game):
        ConfigBox.__init__(self, "game", caller, game)
        self.lutris_config = lutris_config
        self.lutris_config.config_type = "game"
        if game.runner_name:
            self.runner_name = game.runner_name
            runner = import_runner(self.runner_name)()
            self.options = runner.game_options
        else:
            logger.warning("No runner in game supplied to GameBox")
            self.options = []
        self.generate_widgets()


class RunnerBox(ConfigBox):
    def __init__(self, lutris_config, caller, runner_name):
        ConfigBox.__init__(self, runner_name, caller)
        runner = import_runner(runner_name)()

        self.options = runner.runner_options
        self.lutris_config = lutris_config
        self.generate_widgets()


class SystemBox(ConfigBox):
    def __init__(self, lutris_config, caller):
        """Box init"""
        ConfigBox.__init__(self, "system", caller)
        self.lutris_config = lutris_config
        self.options = sysoptions.system_options
        self.generate_widgets()
