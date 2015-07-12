"""Configuration dialogs"""
from gi.repository import Gtk, Pango

from lutris import runners, settings
from lutris.config import LutrisConfig
from lutris.game import Game
from lutris.gui.dialogs import ErrorDialog
from lutris.gui.widgets import VBox, Dialog
from lutris.gui.config_boxes import GameBox,  RunnerBox, SystemBox
from lutris.util.log import logger
from lutris.util.strings import slugify

DIALOG_WIDTH = 550
DIALOG_HEIGHT = 550


class GameDialogCommon(object):
    no_runner_label = "Select a runner from the list"

    @staticmethod
    def get_runner_liststore():
        """Build a ListStore with available runners."""
        runner_liststore = Gtk.ListStore(str, str)
        runner_liststore.append(("Select a runner from the list", ""))
        for runner_name in runners.__all__:
            runner_class = runners.import_runner(runner_name)
            runner = runner_class()
            if runner.is_installed():
                description = runner.description
                runner_liststore.append(
                    ("%s (%s)" % (runner_name, description), runner_name)
                )
        return runner_liststore

    def build_entry_box(self, entry, label_text=None):
        box = Gtk.HBox()
        if label_text:
            label = Gtk.Label(label=label_text)
            box.pack_start(label, False, False, 20)
        box.pack_start(entry, True, True, 20)
        return box

    def get_runner_dropdown(self):
        runner_liststore = self.get_runner_liststore()
        self.runner_dropdown = Gtk.ComboBox.new_with_model(runner_liststore)
        runner_index = 0
        if self.game:
            for runner in runner_liststore:
                if self.runner_name == str(runner[1]):
                    break
                runner_index += 1
        self.runner_dropdown.set_active(runner_index)
        self.runner_dropdown.connect("changed", self.on_runner_changed)
        cell = Gtk.CellRendererText()
        cell.props.ellipsize = Pango.EllipsizeMode.END
        self.runner_dropdown.pack_start(cell, True)
        self.runner_dropdown.add_attribute(cell, 'text', 0)
        return self.runner_dropdown

    @staticmethod
    def build_scrolled_window(widget):
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                   Gtk.PolicyType.AUTOMATIC)
        scrolled_window.add_with_viewport(widget)
        return scrolled_window

    def build_notebook(self):
        self.notebook = Gtk.Notebook()
        self.vbox.pack_start(self.notebook, True, True, 0)

    def build_adv_checkbox(self):
        # Advanced settings checkbox
        checkbox = Gtk.CheckButton(label="Show advanced options")
        value = settings.read_setting('show_advanced_options')
        if value == 'True':
            checkbox.set_active(value)
        checkbox.connect("toggled", self.on_show_advanced_options_toggled)
        self.vbox.pack_end(checkbox, False, False, 5)

    def add_notebook_tab(self, widget, label):
        self.notebook.append_page(widget, Gtk.Label(label=label))

    def build_info_tab(self):
        info_box = VBox()
        self.name_entry = Gtk.Entry()
        if self.game:
            self.name_entry.set_text(self.game.name)
        name_box = self.build_entry_box(self.name_entry, "Name")
        info_box.pack_start(name_box, False, False, 5)

        if self.game:
            self.slug_entry = Gtk.Entry()
            self.slug_entry.set_text(self.game.slug)
            self.slug_entry.set_sensitive(False)
            slug_box = self.build_entry_box(self.slug_entry, "Identifier")
            info_box.pack_start(slug_box, False, False, 5)

        runner_box = Gtk.HBox()
        label = Gtk.Label("Runner")
        label.set_alignment(0.5, 0.5)
        runner_dropdown = self.get_runner_dropdown()
        runner_box.pack_start(label, False, False, 20)
        runner_box.pack_start(runner_dropdown, False, False, 20)
        info_box.pack_start(runner_box, False, False, 5)

        info_sw = self.build_scrolled_window(info_box)
        self.add_notebook_tab(info_sw, "Game info")

    def build_game_tab(self):
        if self.game and self.runner_name:
            self.game.runner_name = self.runner_name
            self.game_box = GameBox(self.lutris_config, self.game)
            game_sw = self.build_scrolled_window(self.game_box)
        elif self.runner_name:
            game = Game(None)
            game.runner_name = self.runner_name
            self.game_box = GameBox(self.lutris_config, game)
            game_sw = self.build_scrolled_window(self.game_box)
        else:
            game_sw = Gtk.Label(label=self.no_runner_label)
        self.add_notebook_tab(game_sw, "Game options")

    def build_runner_tab(self, config_level):
        if self.runner_name:
            self.runner_box = RunnerBox(self.lutris_config)
            runner_sw = self.build_scrolled_window(self.runner_box)
        else:
            runner_sw = Gtk.Label(label=self.no_runner_label)
        self.add_notebook_tab(runner_sw, "Runner options")

    def build_system_tab(self, config_level):
        self.system_box = SystemBox(self.lutris_config)
        self.system_sw = self.build_scrolled_window(self.system_box)
        self.add_notebook_tab(self.system_sw, "System options")

    def build_tabs(self, config_level):
        if config_level == 'game':
            self.build_info_tab()
            self.build_game_tab()
        self.build_runner_tab(config_level)
        self.build_system_tab(config_level)

    def rebuild_tabs(self):
        for i in range(self.notebook.get_n_pages(), 1, -1):
            self.notebook.remove_page(i - 1)
        self.build_game_tab()
        self.build_runner_tab('game')
        self.build_system_tab('game')
        self.show_all()

    def build_action_area(self, label, button_callback):
        # Buttons
        cancel_button = self.add_button("Cancel", Gtk.ResponseType.CANCEL)
        cancel_button.connect("clicked", self.on_cancel_clicked)

        button = self.add_button(label, Gtk.ResponseType.APPLY)
        self.set_default_response(Gtk.ResponseType.APPLY)
        button.connect("clicked", button_callback)

    def set_advanced_options_visible(self, value):
        """Change visibility of advanced options across all config tabs."""
        widgets = self.system_box.get_children()
        if self.runner_name:
            widgets += self.runner_box.get_children()
        if self.game:
            widgets += self.game_box.get_children()

        for widget in widgets:
            if widget.get_style_context().has_class('advanced'):
                widget.set_visible(value)
                if value:
                    widget.set_no_show_all(not value)
                    widget.show_all()

    def on_show_advanced_options_toggled(self, checkbox):
        value = True if checkbox.get_active() else False
        settings.write_setting('show_advanced_options', value)

        self.set_advanced_options_visible(value)

    def on_runner_changed(self, widget):
        """Action called when runner drop down is changed."""
        runner_index = widget.get_active()
        current_page = self.notebook.get_current_page()

        if runner_index == 0:
            self.runner_name = None
            self.lutris_config = LutrisConfig()
        else:
            self.runner_name = widget.get_model()[runner_index][1]
            # XXX DANGER ZONE
            self.lutris_config = LutrisConfig(runner_slug=self.runner_name,
                                              level='game')

        self.rebuild_tabs()
        self.notebook.set_current_page(current_page)

    def on_cancel_clicked(self, widget=None):
        """Dialog destroy callback."""
        self.destroy()

    def is_valid(self):
        name = self.name_entry.get_text()
        if not self.runner_name:
            ErrorDialog("Runner not provided")
            return False
        if not name:
            ErrorDialog("Please fill in the name")
            return False
        return True

    def on_save(self, _button):
        """Save game info and destroy widget. Return True if success."""
        if not self.is_valid():
            return False
        name = self.name_entry.get_text()

        # Do not modify slug
        if not self.slug:
            self.slug = slugify(name)

        if not self.game:
            self.game = Game(self.slug)
            self.game.config = self.lutris_config

        if not self.lutris_config.game_slug:
            self.lutris_config.game_slug = self.slug

        runner_class = runners.import_runner(self.runner_name)
        runner = runner_class(self.lutris_config)
        self.game.name = name
        self.game.slug = self.slug
        self.game.runner_name = self.runner_name
        self.game.config = self.lutris_config
        self.game.directory = runner.game_path
        self.game.is_installed = True
        self.game.save()
        self.destroy()
        logger.debug("Saved %s", name)
        self.saved = True


class AddGameDialog(Dialog, GameDialogCommon):
    """Add game dialog class."""

    def __init__(self, parent, game=None):
        super(AddGameDialog, self).__init__("Add a new game")
        self.lutris_config = LutrisConfig(level='game')
        self.game = game
        self.saved = False

        self.set_default_size(DIALOG_WIDTH, DIALOG_HEIGHT)
        if game:
            self.runner_name = game.runner_name
            self.slug = game.slug
        else:
            self.runner_name = None
            self.slug = None

        self.build_notebook()
        self.build_adv_checkbox()
        self.build_tabs('game')
        self.build_action_area("Add", self.on_save)
        self.name_entry.grab_focus()


class EditGameConfigDialog(Dialog, GameDialogCommon):
    """Game config edit dialog."""
    def __init__(self, parent, game):
        super(EditGameConfigDialog, self).__init__(
            "Configure %s" % game.name,
            parent=parent
        )
        self.game = game
        self.lutris_config = game.config
        self.slug = game.slug
        self.runner_name = game.runner_name
        self.saved = False

        self.set_default_size(DIALOG_WIDTH, DIALOG_HEIGHT)

        self.build_notebook()
        self.build_adv_checkbox()
        self.build_tabs('game')
        self.build_action_area("Edit", self.on_save)
        self.show_all()


class RunnerConfigDialog(Dialog, GameDialogCommon):
    """Runners management dialog."""
    def __init__(self, runner):
        self.runner_name = runner.__class__.__name__
        super(RunnerConfigDialog, self).__init__(
            "Configure %s" % self.runner_name
        )

        self.game = None
        self.saved = False
        self.lutris_config = LutrisConfig(runner_slug=self.runner_name)

        self.set_default_size(DIALOG_WIDTH, DIALOG_HEIGHT)

        self.build_notebook()
        self.build_adv_checkbox()
        self.build_tabs('runner')
        self.build_action_area("Edit", self.ok_clicked)
        self.show_all()

    def ok_clicked(self, _wigdet):
        self.lutris_config.save()
        self.destroy()


class SystemConfigDialog(Dialog, GameDialogCommon):
    def __init__(self, parent=None):
        super(SystemConfigDialog, self).__init__("System preferences", parent=parent)

        self.game = None
        self.runner_name = None
        self.lutris_config = LutrisConfig()

        self.set_default_size(DIALOG_WIDTH, DIALOG_HEIGHT)

        self.system_box = SystemBox(self.lutris_config)
        self.build_adv_checkbox()
        self.system_sw = self.build_scrolled_window(self.system_box)
        self.vbox.pack_start(self.system_sw, True, True, 0)
        self.build_action_area("Save", self.save_config)
        self.show_all()

    def save_config(self, widget):
        self.lutris_config.save()
        self.destroy()
