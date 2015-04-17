"""Widget generators and their signal handlers"""
import os
from gi.repository import Gtk, Gdk

from lutris import settings, sysoptions
from lutris.gui.widgets import VBox, Label
from lutris.runners import import_runner
from lutris.util.log import logger


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
            real_config = self.lutris_config.system_config
        elif self.caller == "runner":
            real_config = self.lutris_config.runner_config
        elif self.caller == "game":
            real_config = self.lutris_config.game_config

        # Select part of config to load or create it.
        if self.config_type in real_config:
            self.config = real_config[self.config_type]
        else:
            self.config = real_config[self.config_type] = {}

        # Go thru all options.
        for option in self.options:
            if 'scope' in option:
                if self.caller not in option['scope']:
                    continue
            option_key = option["option"]
            option_type = option['type']

            hbox = Gtk.HBox()
            hbox.set_margin_left(20)
            self.wrapper = Gtk.HBox()
            self.wrapper.set_spacing(20)

            # Load value if there is one.
            default = option.get('default')
            value = self.config.get(option_key, default)

            # Set tooltip's "Default" part
            self.tooltip_default = default if type(default) is str else None

            # Reset button
            icon = Gtk.Image(stock=Gtk.STOCK_CLEAR)
            self.reset_btn = Gtk.Button(image=icon)
            self.reset_btn.set_relief(Gtk.ReliefStyle.NONE)
            self.reset_btn.set_tooltip_text("Reset option to global or "
                                            "default config")

            if option_key not in self.config:
                self.reset_btn.set_visible(False)
                self.reset_btn.set_no_show_all(True)

            placeholder = Gtk.HBox()
            placeholder.set_size_request(32, 32)
            placeholder.pack_start(self.reset_btn, False, False, 0)
            hbox.pack_end(placeholder, False, False, 5)

            # Different types of widgets.
            self.the_widget = None
            if option_type == 'choice':
                self.generate_combobox(option_key,
                                       option["choices"],
                                       option["label"],
                                       value, default)
            elif option_type == 'choice_with_entry':
                self.generate_combobox(option_key,
                                       option["choices"],
                                       option["label"],
                                       value, default, has_entry=True)
            elif option_type == 'bool':
                self.generate_checkbox(option, value)
            elif option_type == 'range':
                self.generate_range(option_key,
                                    option["min"],
                                    option["max"],
                                    option["label"], value)
            elif option_type == 'string':
                if 'label' not in option:
                    raise ValueError("Option %s has no label" % option)
                self.generate_entry(option_key,
                                    option["label"], value)
            elif option_type == 'directory_chooser':
                self.generate_directory_chooser(option_key,
                                                option["label"],
                                                value)
            elif option_type == 'file':
                self.generate_file_chooser(option, value)
            elif option_type == 'multiple':
                self.generate_multiple_file_chooser(option_key,
                                                    option["label"], value)
            elif option_type == 'label':
                self.generate_label(option["label"])
            else:
                raise ValueError("Unknown widget type %s" % option_type)

            # Tooltip
            helptext = option.get("help")
            if type(self.tooltip_default) is str:
                helptext = helptext + '\n\n' if helptext else ''
                helptext += "<b>Default</b>: " + self.tooltip_default
            if helptext:
                self.wrapper.props.has_tooltip = True
                self.wrapper.connect('query-tooltip', self.on_query_tooltip,
                                     helptext)

            # Grey out option if condition unmet
            if 'condition' in option and not option['condition']:
                hbox.set_sensitive(False)

            # Hide if advanced
            if option.get('advanced'):
                hbox.get_style_context().add_class('advanced')
                show_advanced = settings.read_setting('show_advanced_options')
                if not show_advanced == 'True':
                    hbox.set_no_show_all(True)

            self.reset_btn.connect('clicked', self.on_reset_button_clicked,
                                   option, self.the_widget, self.wrapper)
            hbox.pack_start(self.wrapper, True, True, 0)
            self.pack_start(hbox, False, False, 5)

    def on_reset_button_clicked(self, btn, option, widget, wrapper):
        """Clear option (remove from config, reset option widget)."""
        option_key = option['option']
        option_type = option['type']
        current_value = self.config.get(option_key)
        default = option.get('default')

        btn.set_visible(False)
        self.config.pop(option_key)

        if current_value == default:
            return

        def reset(widget_function, value, signal_function):
            """Set widget's value to default without emitting signal."""
            widget.handler_block_by_func(signal_function)
            widget_function(value)
            widget.handler_unblock_by_func(signal_function)

        if option_type == 'choice':
            reset(widget.set_active_id, default, self.on_combobox_change)
        elif option_type == 'choice_with_entry':
            reset(widget.get_child().set_text, default or '',
                  self.on_combobox_change)
        elif option_type == 'bool':
            reset(widget.set_active, default or False, self.checkbox_toggle)
        elif option_type == 'range':
            reset(widget.set_value, default or 0, self.on_spin_button_changed)
        elif option_type == 'string':
            reset(widget.set_text, default or '', self.entry_changed)
        elif option_type == 'directory_chooser':
            # Here, destroy/recreate the widget because
            # the methods to reset FileChoosers are buggy.
            self.wrapper = wrapper
            label, widget = wrapper.get_children()
            label.destroy()
            widget.destroy()
            self.generate_directory_chooser(option_key, option['label'],
                                            default)
            self.wrapper.show_all()
        elif option_type == 'file':
            widget.handler_block_by_func(self.on_chooser_file_set)
            if default:
                widget.set_current_folder(default)
            else:
                widget.unselect_all()
            widget.handler_unblock_by_func(self.on_chooser_file_set)
        elif option_type == 'multiple':
            widget.clear()

    def option_changed(self, widget, option_name, value):
        """Common actions when value changed on a widget"""
        self.config[option_name] = value

        wrapper = widget.get_parent().get_parent()
        reset_btn = wrapper.get_children()[1].get_children()[0]
        reset_btn.set_visible(True)

    # Label
    def generate_label(self, text):
        """Generate a simple label."""
        label = Label(text)
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        label.set_valign(Gtk.Align.CENTER)
        self.wrapper.pack_start(label, True, True, 0)

    # Checkbox
    def generate_checkbox(self, option, value=None):
        """Generates a checkbox."""
        checkbox = Gtk.CheckButton(label=option["label"])
        if value:
            checkbox.set_active(value)
            self.tooltip_default = 'Enabled'
        else:
            self.tooltip_default = 'Disabled'
        checkbox.connect("toggled", self.checkbox_toggle, option['option'])
        self.wrapper.pack_start(checkbox, True, True, 5)
        self.the_widget = checkbox

    def checkbox_toggle(self, widget, option_name):
        """Action for the checkbox's toggled signal."""
        self.option_changed(widget, option_name, widget.get_active())

    # Entry
    def generate_entry(self, option_name, label, value=None):
        """Generate an entry box."""
        label = Label(label)
        entry = Gtk.Entry()
        if value:
            entry.set_text(value)
        entry.connect("changed", self.entry_changed, option_name)
        label.set_alignment(0.5, 0.5)
        self.wrapper.pack_start(label, False, False, 0)
        self.wrapper.pack_start(entry, True, True, 0)
        self.the_widget = entry

    def entry_changed(self, entry, option_name):
        """Action triggered for entry 'changed' signal."""
        self.option_changed(entry, option_name, entry.get_text())

    # ComboBox
    def generate_combobox(self, option_name, choices, label,
                          value=None, default=None, has_entry=False):
        """Generate a combobox (drop-down menu)."""
        liststore = Gtk.ListStore(str, str)
        for choice in choices:
            if type(choice) is str:
                choice = [choice, choice]
            if choice[1] == default:
                liststore.append([choice[0] + "  (default)", default])
                self.tooltip_default = choice[0]
            else:
                liststore.append(choice)
        # With entry ("choice_with_entry" type)
        if has_entry:
            combobox = Gtk.ComboBox.new_with_model_and_entry(liststore)
            combobox.set_entry_text_column(1)
            if value:
                combobox.get_child().set_text(value)
        # No entry ("choice" type)
        else:
            combobox = Gtk.ComboBox.new_with_model(liststore)
            cell = Gtk.CellRendererText()
            combobox.pack_start(cell, True)
            combobox.add_attribute(cell, 'text', 0)
            combobox.set_id_column(1)

            choices = list(v for k, v in choices)
            if value in choices:
                combobox.set_active_id(value)
            else:
                combobox.set_active_id(default)

        combobox.connect('changed', self.on_combobox_change, option_name)
        label = Label(label)
        label.set_alignment(0.5, 0.5)
        self.wrapper.pack_start(label, False, False, 0)
        self.wrapper.pack_start(combobox, True, True, 0)
        self.the_widget = combobox

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
        self.option_changed(combobox, option, option_value)

    # Range
    def generate_range(self, option_name, min_val, max_val, label, value=None):
        """Generate a ranged spin button."""
        adjustment = Gtk.Adjustment(float(min_val), float(min_val),
                                    float(max_val), 1, 0, 0)
        spin_button = Gtk.SpinButton()
        spin_button.set_adjustment(adjustment)
        if value:
            spin_button.set_value(value)
        spin_button.connect('changed', self.on_spin_button_changed,
                            option_name)
        label = Label(label)
        label.set_alignment(0.5, 0.5)
        self.wrapper.pack_start(label, False, False, 0)
        self.wrapper.pack_start(spin_button, True, True, 0)
        self.the_widget = spin_button

    def on_spin_button_changed(self, spin_button, option):
        """Action triggered on spin button 'changed' signal."""
        value = spin_button.get_value_as_int()
        self.option_changed(spin_button, option, value)

    # File chooser
    def generate_file_chooser(self, option, path=None):
        """Generate a file chooser button to select a file."""
        option_name = option['option']
        label = Label(option['label'])
        file_chooser = Gtk.FileChooserButton("Choose a file for %s" % label)
        file_chooser.set_size_request(200, 30)

        if 'default_path' in option:
            config_key = option['default_path']
            default_path = self.lutris_config.config['system'].get(config_key)
            if default_path and os.path.exists(default_path):
                file_chooser.set_current_folder(default_path)

        file_chooser.set_action(Gtk.FileChooserAction.OPEN)
        file_chooser.connect("file-set", self.on_chooser_file_set,
                             option_name)
        if path:
            # If path is relative, complete with game dir
            if not os.path.isabs(path):
                path = os.path.join(self.game.directory, path)
            file_chooser.unselect_all()
            file_chooser.select_filename(path)
        label.set_alignment(0.5, 0.5)
        self.wrapper.pack_start(label, False, False, 0)
        self.wrapper.pack_start(file_chooser, True, True, 0)
        self.the_widget = file_chooser

    # Directory chooser
    def generate_directory_chooser(self, option_name, label_text, value=None):
        """Generate a file chooser button to select a directory."""
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
        self.wrapper.pack_start(label, False, False, 0)
        self.wrapper.pack_start(directory_chooser, True, True, 0)
        self.the_widget = directory_chooser

    def on_chooser_file_set(self, filechooser_widget, option):
        """Action triggered on file select dialog 'file-set' signal."""
        filename = filechooser_widget.get_filename()
        self.option_changed(filechooser_widget, option, filename)

    # Multiple file selector
    def generate_multiple_file_chooser(self, option_name, label, value=None):
        """Generate a multiple file selector."""
        vbox = Gtk.VBox()
        label = Label(label + ':')
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
            files_chooser_button.set_current_folder(os.path.dirname(value[0]))

        label.set_halign(Gtk.Align.START)
        files_chooser_button.set_margin_left(10)
        files_chooser_button.set_margin_right(10)
        vbox.pack_start(label, False, False, 5)
        vbox.pack_start(files_chooser_button, False, False, 0)

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
        treeview_scroll.set_min_content_height(130)
        treeview_scroll.set_policy(Gtk.PolicyType.AUTOMATIC,
                                   Gtk.PolicyType.AUTOMATIC)
        treeview_scroll.add(files_treeview)

        treeview_scroll.set_margin_left(10)
        treeview_scroll.set_margin_right(10)
        vbox.pack_start(treeview_scroll, True, True, 0)
        self.wrapper.pack_start(vbox, True, True, 0)
        self.the_widget = self.files_list_store

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
                self.config[option].pop(row_index)

    def add_files_callback(self, button, option=None):
        """Add several files to the configuration"""
        filenames = button.get_filenames()
        files = self.config.get(option, [])
        for filename in filenames:
            self.files_list_store.append([filename])
            if filename not in files:
                files.append(filename)
        self.option_changed(button.get_parent(), option, files)
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
