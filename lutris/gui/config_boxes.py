"""Widget generators and their signal handlers"""
# pylint: disable=no-member
import os
from gi.repository import Gtk, Gdk

from lutris import settings, sysoptions
from lutris.gui.widgets.common import VBox, Label, FileChooserEntry, EditableGrid
from lutris.runners import import_runner, InvalidRunner
from lutris.util.log import logger
from lutris.util.system import reverse_expanduser


class ConfigBox(VBox):
    """Dynamically generate a vbox built upon on a python dict."""
    def __init__(self, game=None):
        super(ConfigBox, self).__init__()
        self.options = []
        self.game = game
        self.config = None
        self.raw_config = None
        self.option_widget = None
        self.wrapper = None

    def generate_top_info_box(self, text):
        help_box = Gtk.HBox()
        help_box.set_margin_left(15)
        help_box.set_margin_right(15)
        help_box.set_margin_bottom(5)
        icon = Gtk.Image(icon_name='dialog-information')
        label = Gtk.Label("<i>%s</i>" % text)
        label.set_line_wrap(True)
        label.set_alignment(0, 0.5)
        label.set_use_markup(True)
        help_box.pack_start(icon, False, False, 5)
        help_box.pack_start(label, False, False, 5)
        self.pack_start(help_box, False, False, 0)
        self.pack_start(Gtk.HSeparator(), False, False, 10)
        help_box.show_all()

    def generate_widgets(self, config_section):
        """Parse the config dict and generates widget accordingly."""
        if not self.options:
            label = Label("No options available")
            label.set_halign(Gtk.Align.CENTER)
            label.set_valign(Gtk.Align.CENTER)
            self.pack_start(label, True, True, 0)
            return

        # Select config section.
        if config_section == 'game':
            self.config = self.lutris_config.game_config
            self.raw_config = self.lutris_config.raw_game_config
        elif config_section == 'runner':
            self.config = self.lutris_config.runner_config
            self.raw_config = self.lutris_config.raw_runner_config
        elif config_section == 'system':
            self.config = self.lutris_config.system_config
            self.raw_config = self.lutris_config.raw_system_config

        # Go thru all options.
        for option in self.options:
            if 'scope' in option:
                if config_section not in option['scope']:
                    continue
            option_key = option['option']
            value = self.config.get(option_key)
            default = option.get('default')

            if callable(option.get('choices')):
                option['choices'] = option['choices']()
            if callable(option.get('condition')):
                option['condition'] = option['condition']()

            hbox = Gtk.HBox()
            hbox.set_margin_left(20)
            self.wrapper = Gtk.HBox()
            self.wrapper.set_spacing(20)

            placeholder = Gtk.HBox()
            placeholder.set_size_request(32, 32)
            hbox.pack_end(placeholder, False, False, 5)

            # Set tooltip's "Default" part
            default = option.get('default')
            self.tooltip_default = default if type(default) is str else None

            # Generate option widget
            self.option_widget = None
            self.call_widget_generator(option, option_key, value, default)

            # Reset button
            reset_btn = Gtk.Button.new_from_icon_name('edit-clear',
                                                      Gtk.IconSize.MENU)
            reset_btn.set_relief(Gtk.ReliefStyle.NONE)
            reset_btn.set_tooltip_text("Reset option to global or "
                                       "default config")
            reset_btn.connect('clicked', self.on_reset_button_clicked,
                              option, self.option_widget, self.wrapper)

            if option_key not in self.raw_config:
                reset_btn.set_visible(False)
                reset_btn.set_no_show_all(True)
            placeholder.pack_start(reset_btn, False, False, 0)

            # Tooltip
            helptext = option.get("help")
            if type(self.tooltip_default) is str:
                helptext = helptext + '\n\n' if helptext else ''
                helptext += "<b>Default</b>: " + self.tooltip_default
            if value != default and option_key not in self.raw_config:
                helptext = helptext + '\n\n' if helptext else ''
                helptext += ("<i>(Italic indicates that this option is "
                             "modified in a lower configuration level.)</i>")
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

            hbox.pack_start(self.wrapper, True, True, 0)
            self.pack_start(hbox, False, False, 5)

    def call_widget_generator(self, option, option_key, value, default):
        """Call the right generation method depending on option type."""
        option_type = option['type']

        if option_key in self.raw_config:
            self.set_style_property('font-weight', 'bold', self.wrapper)
        elif value != default:
            self.set_style_property('font-style', 'italic', self.wrapper)

        if option_type == 'choice':
            self.generate_combobox(option_key,
                                   option["choices"],
                                   option["label"],
                                   value,
                                   default)

        elif option_type == 'choice_with_entry':
            self.generate_combobox(option_key,
                                   option["choices"],
                                   option["label"],
                                   value,
                                   default,
                                   has_entry=True)

        elif option_type == 'bool':
            self.generate_checkbox(option, value)
            self.tooltip_default = 'Enabled' if default else 'Disabled'
        elif option_type == 'extended_bool':
            self.generate_checkbox_with_callback(option, value)
            self.tooltip_default = 'Enabled' if default else 'Disabled'
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
        elif option_type == 'mapping':
            self.generate_editable_grid(option_key, label=option['label'], value=value)
        else:
            raise ValueError("Unknown widget type %s" % option_type)

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
        """Generate a checkbox."""
        checkbox = Gtk.CheckButton(label=option["label"])
        if value is True:
            checkbox.set_active(value)
        checkbox.connect("toggled", self.checkbox_toggle, option['option'])
        self.wrapper.pack_start(checkbox, True, True, 5)
        self.option_widget = checkbox

    #Checkbox with callback
    def generate_checkbox_with_callback(self, option, value=None):
        """Generate a checkbox. With callback"""
        checkbox = Gtk.CheckButton(label=option["label"])
        if option['active'] is True:
            checkbox.set_sensitive(True)
        else:
            checkbox.set_sensitive(False)
        if value is True:
            checkbox.set_active(value)
        checkbox.connect("toggled", self.checkbox_toggle_with_callback, option['option'], option['callback'], option['callback_on'])
        self.wrapper.pack_start(checkbox, True, True, 5)
        self.option_widget = checkbox

    def checkbox_toggle(self, widget, option_name):
        """Action for the checkbox's toggled signal."""
        self.option_changed(widget, option_name, widget.get_active())

    def checkbox_toggle_with_callback(self, widget, option_name, callback, callback_on=None):
        """Action for the checkbox's toggled signal. With callback method"""
        if widget.get_active() == callback_on or callback_on is None:
            if callback(self.config):
                self.option_changed(widget, option_name, widget.get_active())
            else:
                widget.set_active(False)
        else:
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
        self.option_widget = entry

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
            if choice[1] == default and not has_entry:
                # Do not add default label to editable dropdowns since this gets
                # added to the actual value.
                liststore.append([choice[0] + "  (default)", default])
                self.tooltip_default = choice[0]
            else:
                liststore.append(choice)
        # With entry ("choice_with_entry" type)
        if has_entry:
            combobox = Gtk.ComboBox.new_with_model_and_entry(liststore)
            combobox.set_entry_text_column(0)
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
        combobox.connect('scroll-event', self.on_combobox_scroll)
        label = Label(label)
        label.set_alignment(0.5, 0.5)
        combobox.set_valign(Gtk.Align.CENTER)
        self.wrapper.pack_start(label, False, False, 0)
        self.wrapper.pack_start(combobox, True, True, 0)
        self.option_widget = combobox

    def on_combobox_scroll(self, combobox, event):
        """Do not change options when scrolling
        with cursor inside a ComboBox."""
        combobox.stop_emission_by_name('scroll-event')
        return False

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
        self.option_widget = spin_button

    def on_spin_button_changed(self, spin_button, option):
        """Action triggered on spin button 'changed' signal."""
        value = spin_button.get_value_as_int()
        self.option_changed(spin_button, option, value)

    # File chooser
    def generate_file_chooser(self, option, path=None):
        """Generate a file chooser button to select a file."""
        option_name = option['option']
        label = Label(option['label'])
        file_chooser = FileChooserEntry(
            title='Select file',
            action=Gtk.FileChooserAction.OPEN,
            default_path=path  # reverse_expanduser(path)
        )
        file_chooser.set_size_request(200, 30)

        if 'default_path' in option:
            config_key = option['default_path']
            default_path = self.lutris_config.system_config.get(config_key)
            if default_path and os.path.exists(default_path):
                file_chooser.entry.set_text(default_path)

        if path:
            # If path is relative, complete with game dir
            if not os.path.isabs(path):
                path = os.path.expanduser(path)
                if not os.path.isabs(path):
                    path = os.path.join(self.game.directory, path)
            file_chooser.entry.set_text(path)

        file_chooser.set_valign(Gtk.Align.CENTER)
        label.set_alignment(0.5, 0.5)
        self.wrapper.pack_start(label, False, False, 0)
        self.wrapper.pack_start(file_chooser, True, True, 0)
        self.option_widget = file_chooser
        file_chooser.entry.connect('changed', self._on_chooser_file_set,
                                            option_name)

    def _on_chooser_file_set(self, entry, option):
        """Action triggered on file select dialog 'file-set' signal."""
        if not os.path.isabs(entry.get_text()):
            entry.set_text(os.path.expanduser(entry.get_text()))
        self.option_changed(entry.get_parent(), option, entry.get_text())

    # Directory chooser
    def generate_directory_chooser(self, option_name, label_text, value=None):
        """Generate a file chooser button to select a directory."""
        label = Label(label_text)
        directory_chooser = FileChooserEntry(
            title='Select folder',
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            default_path=reverse_expanduser(value)
        )
        directory_chooser.entry.connect('changed', self._on_chooser_dir_set,
                                        option_name)
        directory_chooser.set_valign(Gtk.Align.CENTER)
        label.set_alignment(0.5, 0.5)
        self.wrapper.pack_start(label, False, False, 0)
        self.wrapper.pack_start(directory_chooser, True, True, 0)
        self.option_widget = directory_chooser

    def _on_chooser_dir_set(self, entry, option):
        """Action triggered on file select dialog 'file-set' signal."""
        self.option_changed(entry.get_parent(), option, entry.get_text())

    # Editable grid
    def generate_editable_grid(self, option_name, label, value=None):
        value = value or {}
        value = list(value.items())
        label = Label(label)
        label.set_alignment(0.5, 0)

        grid = EditableGrid(value, columns=["Key", "Value"])
        grid.connect('changed', self.on_grid_changed, option_name)
        self.wrapper.pack_start(label, False, False, 0)
        self.wrapper.pack_start(grid, True, True, 0)
        self.option_widget = grid

    def on_grid_changed(self, grid, option):
        values = dict(grid.get_data())
        self.option_changed(grid, option, values)

    # Multiple file selector
    def generate_multiple_file_chooser(self, option_name, label, value=None):
        """Generate a multiple file selector."""
        vbox = Gtk.VBox()
        label = Label(label + ':')
        label.set_halign(Gtk.Align.START)
        button = Gtk.Button('Add files')
        button.connect('clicked', self.on_add_files_clicked,
                       option_name, value)
        button.set_margin_left(10)
        vbox.pack_start(label, False, False, 5)
        vbox.pack_end(button, False, False, 0)

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
        files_treeview.connect('key-press-event',
                               self.on_files_treeview_keypress, option_name)
        treeview_scroll = Gtk.ScrolledWindow()
        treeview_scroll.set_min_content_height(130)
        treeview_scroll.set_margin_left(10)
        treeview_scroll.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        treeview_scroll.set_policy(Gtk.PolicyType.AUTOMATIC,
                                   Gtk.PolicyType.AUTOMATIC)
        treeview_scroll.add(files_treeview)

        vbox.pack_start(treeview_scroll, True, True, 0)
        self.wrapper.pack_start(vbox, True, True, 0)
        self.option_widget = self.files_list_store

    def on_add_files_clicked(self, widget, option_name, value):
        """Create and run multi-file chooser dialog."""
        dialog = Gtk.FileChooserDialog(
            title="Select files",
            parent=None,
            action=Gtk.FileChooserAction.OPEN,
            buttons=('_Cancel', Gtk.ResponseType.CANCEL,
                     '_Add', Gtk.ResponseType.ACCEPT)
        )
        dialog.set_select_multiple(True)

        first_file_dir = os.path.dirname(value[0]) if value else None
        dialog.set_current_folder(first_file_dir or
                                  self.game.directory or
                                  self.config.get('game_path') or
                                  os.path.expanduser('~'))
        response = dialog.run()
        if response == Gtk.ResponseType.ACCEPT:
            self.add_files_to_treeview(dialog, option_name, self.wrapper)
        dialog.destroy()

    def add_files_to_treeview(self, dialog, option, wrapper):
        """Add several files to the configuration"""
        filenames = dialog.get_filenames()
        files = self.config.get(option, [])
        for filename in filenames:
            self.files_list_store.append([filename])
            if filename not in files:
                files.append(filename)
        self.option_changed(wrapper, option, files)

    def on_files_treeview_keypress(self, treeview, event, option):
        """Action triggered when a row is deleted from the filechooser."""
        key = event.keyval
        if key == Gdk.KEY_Delete:
            selection = treeview.get_selection()
            (model, treepaths) = selection.get_selected_rows()
            for treepath in treepaths:
                row_index = int(str(treepath))
                treeiter = model.get_iter(treepath)
                model.remove(treeiter)
                self.raw_config[option].pop(row_index)

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

    def option_changed(self, widget, option_name, value):
        """Common actions when value changed on a widget"""
        self.raw_config[option_name] = value
        self.config[option_name] = value

        wrapper = widget.get_parent()
        hbox = wrapper.get_parent()

        # Dirty way to get the reset btn. I tried passing it through the
        # methods but got some strange unreliable behavior.
        reset_btn = hbox.get_children()[1].get_children()[0]
        reset_btn.set_visible(True)
        self.set_style_property('font-weight', 'bold', wrapper)

    def on_reset_button_clicked(self, btn, option, widget, wrapper):
        """Clear option (remove from config, reset option widget)."""
        option_key = option['option']
        current_value = self.config[option_key]

        btn.set_visible(False)
        self.set_style_property('font-weight', 'normal', wrapper)
        self.raw_config.pop(option_key)
        self.lutris_config.update_cascaded_config()

        reset_value = self.config.get(option_key)
        if current_value == reset_value:
            return

        # Destroy and recreate option widget
        self.wrapper = wrapper
        children = wrapper.get_children()
        for child in children:
            child.destroy()
        self.call_widget_generator(option, option_key, reset_value,
                                   option.get('default'))
        self.wrapper.show_all()

    def set_style_property(self, property_, value, wrapper):
        """Add custom style."""
        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(
            "GtkHBox {{{}: {};}}".format(property_, value).encode()
        )
        style_context = wrapper.get_style_context()
        style_context.add_provider(style_provider,
                                   Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


class GameBox(ConfigBox):
    def __init__(self, lutris_config, game):
        ConfigBox.__init__(self, game)
        self.lutris_config = lutris_config
        if game.runner_name:
            if not game.runner:
                try:
                    runner = import_runner(game.runner_name)()
                except InvalidRunner:
                    runner = None
            else:
                runner = game.runner
            if runner:
                self.options = runner.game_options
        else:
            logger.warning("No runner in game supplied to GameBox")
        self.generate_widgets('game')


class RunnerBox(ConfigBox):
    def __init__(self, lutris_config):
        ConfigBox.__init__(self)
        self.lutris_config = lutris_config
        try:
            runner = import_runner(self.lutris_config.runner_slug)()
        except InvalidRunner:
            runner = None
        if runner:
            self.options = runner.get_runner_options()

        if lutris_config.level == 'game':
            self.generate_top_info_box(
                "If modified, these options supersede the same options from "
                "the base runner configuration."
            )
        self.generate_widgets('runner')


class SystemBox(ConfigBox):
    def __init__(self, lutris_config):
        ConfigBox.__init__(self)
        self.lutris_config = lutris_config
        runner_slug = self.lutris_config.runner_slug

        if runner_slug:
            self.options = sysoptions.with_runner_overrides(runner_slug)
        else:
            self.options = sysoptions.system_options

        if lutris_config.game_config_id and runner_slug:
            self.generate_top_info_box(
                "If modified, these options supersede the same options from "
                "the base runner configuration, which themselves supersede "
                "the global preferences."
            )
        elif runner_slug:
            self.generate_top_info_box(
                "If modified, these options supersede the same options from "
                "the global preferences."
            )

        self.generate_widgets('system')
