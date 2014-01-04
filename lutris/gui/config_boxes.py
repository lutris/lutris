"""Widget generators and their signal handlers"""
from gi.repository import Gtk, GObject, Gdk
from lutris.util.log import logger
from lutris.runners import import_runner
from lutris.util import display

PADDING = 5


class Label(Gtk.Label):
    """ Standardised label for config vboxes"""
    def __init__(self, message=None):
        """ Custom init of label """
        super(Label, self).__init__(message)
        #self.set_size_request(200, 30)
        #self.set_alignment(0.0, 0.5)
        self.set_line_wrap(True)


class ConfigBox(Gtk.VBox):
    """ Dynamically generates a vbox built upon on a python dict. """
    def __init__(self, config_type, caller):
        GObject.GObject.__init__(self)
        self.set_margin_top(30)
        self.options = None
        # Section of the configuration file to save options in. Can be "game",
        # "runner" or "system"
        self.config_type = config_type
        self.caller = caller

    def generate_widgets(self):
        """ Parses the config dict and generates widget accordingly."""
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

        #Go thru all options.
        for option in self.options:
            option_key = option["option"]

            #Load value if there is one.
            if option_key in config:
                value = config[option_key]
            else:
                value = None

            #Different types of widgets.
            if option["type"] == "one_choice":
                self.generate_combobox(option_key,
                                       option["choices"],
                                       option["label"], value)
            elif option["type"] == "bool":
                if value is None and 'default' in option:
                    value = option['default']
                self.generate_checkbox(option, value)
            elif option["type"] == "range":
                self.generate_range(option_key,
                                    option["min"],
                                    option["max"],
                                    option["label"], value)
            elif option["type"] == "string":
                if not 'label' in option:
                    raise ValueError("Option %s has no label" % option)
                self.generate_entry(option_key,
                                    option["label"], value)
            elif option["type"] == "directory_chooser":
                self.generate_directory_chooser(option_key,
                                                option["label"],
                                                value)
            elif option["type"] in ("file_chooser", "file"):
                if option["type"] == "file_chooser":
                    logger.warning("'file_chooser' option deprecated")
                self.generate_file_chooser(option, value)
            elif option["type"] == "multiple":
                self.generate_multiple_file_chooser(option_key,
                                                    option["label"], value)
            elif option["type"] == "label":
                self.generate_label(option["label"])
            else:
                raise ValueError("Unknown widget type %s" % option["type"])

    def generate_label(self, text):
        """ Generates a simple label. """
        label = Label(text)
        label.show()
        self.pack_start(label, True, True, PADDING)

    #Checkbox
    def generate_checkbox(self, option, value=None):
        """ Generates a checkbox. """
        checkbox = Gtk.CheckButton(option["label"])
        if value:
            checkbox.set_active(value)
        checkbox.connect("toggled", self.checkbox_toggle, option['option'])
        checkbox.set_margin_left(20)
        checkbox.show()
        self.pack_start(checkbox, False, False, 0)

    def checkbox_toggle(self, widget, option_name):
        """ Action for the checkbox's toggled signal."""
        self.real_config[self.config_type][option_name] = widget.get_active()

    #Entry
    def generate_entry(self, option_name, label, value=None):
        """ Generates an entry box. """
        hbox = Gtk.HBox()
        entry_label = Label(label)
        entry = Gtk.Entry()
        if value:
            entry.set_text(value)
        entry.connect("changed", self.entry_changed, option_name)
        hbox.pack_start(entry_label, False, False, 20)
        hbox.pack_start(entry, True, True, 20)
        hbox.show_all()
        self.pack_start(hbox, False, True, PADDING)

    def entry_changed(self, entry, option_name):
        """ Action triggered for entry 'changed' signal. """
        entry_text = entry.get_text()
        self.real_config[self.config_type][option_name] = entry_text

    #ComboBox
    def generate_combobox(self, option_name, choices, label, value=None):
        """ Generates a combobox (drop-down menu). """
        hbox = Gtk.HBox()
        liststore = Gtk.ListStore(str, str)
        for choice in choices:
            if type(choice) is str:
                choice = [choice, choice]
            liststore.append(choice)
        combobox = Gtk.ComboBox.new_with_model(liststore)
        cell = Gtk.CellRendererText()
        combobox.pack_start(cell, True)
        combobox.add_attribute(cell, 'text', 0)
        index = selected_index = -1
        if value:
            for choice in choices:
                if choice[1] == value:
                    selected_index = index + 1
                index += 1
        combobox.set_active(selected_index)
        combobox.connect('changed', self.on_combobox_change, option_name)
        label = Label(label)
        hbox.pack_start(label, False, False, 20)
        hbox.pack_start(combobox, True, True, 20)
        hbox.show_all()
        self.pack_start(hbox, False, False, PADDING)

    def on_combobox_change(self, combobox, option):
        """ Action triggered on combobox 'changed' signal. """
        model = combobox.get_model()
        active = combobox.get_active()
        if active < 0:
            return None
        option_value = model[active][1]
        self.real_config[self.config_type][option] = option_value

    def generate_range(self, option_name, min_val, max_val, label, value=None):
        """ Generates a ranged spin button. """
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
        hbox.pack_start(label, False, False, 20)
        hbox.pack_start(spin_button, True, True, 20)
        hbox.show_all()
        self.pack_start(hbox, False, True, 5)

    def on_spin_button_changed(self, spin_button, option):
        """ Action triggered on spin button 'changed' signal """
        value = spin_button.get_value_as_int()
        self.real_config[self.config_type][option] = value

    def generate_file_chooser(self, option, value=None):
        """Generates a file chooser button to select a file"""
        option_name = option['option']
        label = option['label']
        hbox = Gtk.HBox()
        Gtklabel = Label(label)
        file_chooser = Gtk.FileChooserButton("Choose a file for %s" % label)
        file_chooser.set_size_request(200, 30)
        if 'default_path' in option:
            config_key = option['default_path']
            if config_key in self.lutris_config.config['system']:
                default_path = self.lutris_config.config['system'][config_key]
                file_chooser.set_current_folder(default_path)

        file_chooser.set_action(Gtk.FileChooserAction.OPEN)
        file_chooser.connect("file-set", self.on_chooser_file_set, option_name)
        if value:
            file_chooser.unselect_all()
            file_chooser.select_filename(value)
        hbox.pack_start(Gtklabel, False, False, 20)
        hbox.pack_start(file_chooser, True, True, 20)
        self.pack_start(hbox, False, True, PADDING)

    def generate_directory_chooser(self, option_name, label, value=None):
        """Generates a file chooser button to select a directory"""
        hbox = Gtk.HBox()
        Gtklabel = Label(label)
        directory_chooser = Gtk.FileChooserButton("Choose a directory for %s"
                                                  % label)
        directory_chooser.set_action(Gtk.FileChooserAction.SELECT_FOLDER)
        if value:
            directory_chooser.set_current_folder(value)
        directory_chooser.connect("file-set", self.on_chooser_file_set,
                                  option_name)
        hbox.pack_start(Gtklabel, False, False, 20)
        hbox.pack_start(directory_chooser, True, True, 20)
        self.pack_start(hbox, False, True, PADDING)

    def on_chooser_file_set(self, filechooser_widget, option):
        """ Action triggered on file select dialog 'file-set' signal. """
        filename = filechooser_widget.get_filename()
        self.real_config[self.config_type][option] = filename

    def generate_multiple_file_chooser(self, option_name, label, value=None):
        """ Generates a multiple file selector. """
        hbox = Gtk.HBox()
        label = Label(label)
        hbox.pack_start(label, False, False, PADDING)
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
        game_path = self.lutris_config.get_path(self.runner_class)
        if game_path:
            files_chooser_button.set_current_folder(game_path)
        if value:
            files_chooser_button.set_filename(value[0])

        hbox.pack_start(files_chooser_button, True, True, 0)
        self.pack_start(hbox, False, True, PADDING)
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
        self.add(treeview_scroll)

    def on_files_treeview_event(self, treeview, event, option):
        """ Action triggered when a row is deleted from the filechooser. """
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
            if not filename in files:
                files.append(filename)
        self.real_config[self.config_type][option] = files
        self.files_chooser_dialog = None


class GameBox(ConfigBox):
    def __init__(self, lutris_config, caller):
        ConfigBox.__init__(self, "game", caller)
        self.lutris_config = lutris_config
        self.lutris_config.config_type = "game"
        self.runner_class = self.lutris_config.runner
        runner = import_runner(self.runner_class)()

        self.options = runner.game_options
        self.generate_widgets()


class RunnerBox(ConfigBox):
    def __init__(self, lutris_config, caller):
        runner_classname = lutris_config.runner
        ConfigBox.__init__(self, runner_classname, caller)
        runner = import_runner(runner_classname)()

        self.options = runner.runner_options
        self.lutris_config = lutris_config
        self.generate_widgets()


class SystemBox(ConfigBox):
    def __init__(self, lutris_config, caller):
        """Box init"""
        ConfigBox.__init__(self, "system", caller)
        self.lutris_config = lutris_config
        oss_list = [
            ("None (don't use OSS)", "none"),
            ("padsp (PulseAudio OSS Wrapper)", "padsp"),
            ("padsp32 (PulseAudio OSS Wrapper for 32bit apps)", "padsp32"),
            ("aoss (OSS Wrapper for Alsa)", "aoss"),
            ("esddsp (OSS Wrapper for esound)", "esddsp"),
        ]
        resolution_list = display.get_resolutions()
        display_list = display.get_output_names()
        self.options = [
            {
                'option': 'game_path',
                'type': 'directory_chooser',
                'label': 'Default game path'
            },
            {
                'option': 'resolution',
                'type': 'one_choice',
                'label': 'Resolution',
                'choices': resolution_list
            },
            {
                'option': 'display',
                'type': 'one_choice',
                'label': 'Restrict to display',
                'choices': display_list
            },
            {
                'option': 'oss_wrapper',
                'type': 'one_choice',
                'label': 'OSS Wrapper',
                'choices': oss_list
            },
            {
                'option': 'reset_pulse',
                'type': 'bool',
                'label': 'Reset PulseAudio'
            },
            {
                'option': 'hide_panels',
                'type': 'bool',
                'label': 'Hide Gnome Panels'
            },
            {
                'option': 'reset_desktop',
                'type': 'bool',
                'label': 'Reset resolution when game quits'
            },
            {
                'option': 'killswitch',
                'type': 'string',
                'label': 'Killswitch file'
            },
            {
                'option': 'xboxdrv',
                'type': 'string',
                'label': 'xboxdrv config'
            }
        ]
        self.generate_widgets()
