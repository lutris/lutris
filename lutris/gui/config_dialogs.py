"""Configuration dialogs"""
from gi.repository import Gtk, Pango

from lutris.util.log import logger
from lutris.config import LutrisConfig
from lutris.game import Game
from lutris import pga
import lutris.runners
from lutris.gui.widgets import VBox, Dialog
from lutris.gui.config_boxes import GameBox,  RunnerBox, SystemBox
from lutris.util.strings import slugify


class GameDialogCommon(object):
    no_runner_label = "Select a runner from the list"

    @staticmethod
    def get_runner_liststore():
        """Build a ListStore with available runners."""
        runner_liststore = Gtk.ListStore(str, str)
        runner_liststore.append(("Select a runner from the list", ""))
        for runner_name in lutris.runners.__all__:
            runner_class = lutris.runners.import_runner(runner_name)
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
        scrolled_window.show_all()
        return scrolled_window

    def build_notebook(self):
        self.notebook = Gtk.Notebook()
        self.vbox.pack_start(self.notebook, True, True, 10)

    def add_notebook_tab(self, widget, label):
        self.notebook.append_page(widget, Gtk.Label(label=label))

    def build_info_tab(self):
        info_box = VBox()
        self.name_entry = Gtk.Entry()
        if self.game:
            self.name_entry.set_text(self.game.name)
        name_box = self.build_entry_box(self.name_entry, "Name")
        info_box.pack_start(name_box, False, False, 5)

        self.slug_entry = Gtk.Entry()
        if self.game:
            self.slug_entry.set_text(self.game.slug)
        slug_box = self.build_entry_box(self.slug_entry, "Identifier")
        info_box.pack_start(slug_box, False, False, 5)

        runner_dropdown = self.get_runner_dropdown()
        runner_box = Gtk.HBox()
        runner_box.pack_start(runner_dropdown, False, False, 20)
        info_box.pack_start(runner_box, False, False, 5)

        info_sw = self.build_scrolled_window(info_box)
        self.add_notebook_tab(info_sw, "Game info")

    def build_game_tab(self):
        if self.game and self.runner_name:
            self.game.runner_name = self.runner_name
            self.game_box = GameBox(self.lutris_config, "game", self.game)
            game_sw = self.build_scrolled_window(self.game_box)
        elif self.runner_name:
            game = Game(None)
            game.runner_name = self.runner_name
            self.game_box = GameBox(self.lutris_config, "game", game)
            game_sw = self.build_scrolled_window(self.game_box)
        else:
            game_sw = Gtk.Label(label=self.no_runner_label)
            game_sw.show()
        self.add_notebook_tab(game_sw, "Game configuration")

    def build_runner_tab(self):
        if self.runner_name:
            self.runner_box = RunnerBox(self.lutris_config, "game",
                                        self.runner_name)
            runner_sw = self.build_scrolled_window(self.runner_box)
        else:
            runner_sw = Gtk.Label(label=self.no_runner_label)
            runner_sw.show()
        self.add_notebook_tab(runner_sw, "Runner configuration")

    def build_system_tab(self):
        self.system_box = SystemBox(self.lutris_config, "game")
        self.system_sw = self.build_scrolled_window(self.system_box)
        self.add_notebook_tab(self.system_sw, "System configuration")

    def build_tabs(self):
        self.build_info_tab()
        self.build_game_tab()
        self.build_runner_tab()
        self.build_system_tab()

    def rebuild_tabs(self):
        for i in range(self.notebook.get_n_pages(), 1, -1):
            self.notebook.remove_page(i - 1)
        self.build_game_tab()
        self.build_runner_tab()
        self.build_system_tab()

    def build_action_area(self, label, button_callback):
        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", self.on_cancel_clicked)
        self.action_area.pack_start(cancel_button, True, True, 0)

        button = Gtk.Button(label=label)
        button.connect("clicked", button_callback)
        self.action_area.pack_start(button, True, True, 0)

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
            self.lutris_config = LutrisConfig(runner=self.runner_name)

        self.rebuild_tabs()
        self.notebook.set_current_page(current_page)

    def on_cancel_clicked(self, widget=None):
        """Dialog destroy callback."""
        self.destroy()

    def is_valid(self):
        name = self.name_entry.get_text()
        if not self.runner_name:
            logger.error("Missing runner")
            return False
        if not name:
            logger.error("Missing game name")
            return False

    def on_save(self, _button):
        """Save game info and destroy widget. Return True if success."""
        if not self.is_valid():
            return False
        name = self.name_entry.get_text()
        if not self.lutris_config.game:
            self.lutris_config.game = slugify(name)
        self.lutris_config.save()
        self.slug = self.lutris_config.game
        runner_class = lutris.runners.import_runner(self.runner_name)
        runner = runner_class(self.lutris_config)
        pga.add_or_update(name, self.runner_name, slug=self.slug,
                          directory=runner.game_path,
                          installed=1)
        self.destroy()
        logger.debug("Saved %s", name)
        return True


class AddGameDialog(Dialog, GameDialogCommon):
    """Add game dialog class."""

    def __init__(self, parent, game=None):
        super(AddGameDialog, self).__init__("Add a new game", parent.window)
        self.parent_window = parent
        self.lutris_config = LutrisConfig()
        self.game = game
        self.installed = False

        self.set_size_request(-1, 500)
        if game:
            self.runner_name = game.runner_name
            self.slug = game.slug
        else:
            self.runner_name = None
            self.slug = None

        self.build_notebook()
        self.build_tabs()

        self.build_action_area("Add", self.on_save)
        self.show_all()

    def on_save(self, _button):
        name = self.name_entry.get_text()
        self.lutris_config.game = self.slug if self.slug else slugify(name)
        self.installed = super(AddGameDialog, self).on_save(_button)


class EditGameConfigDialog(Dialog, GameDialogCommon):
    """Game config edit dialog."""
    def __init__(self, parent, game):
        super(EditGameConfigDialog, self).__init__(
            "Edit game configuration for %s" % game.name, parent.window
        )
        self.parent_window = parent
        self.game = game
        self.lutris_config = game.config
        self.runner_name = game.runner_name

        self.set_size_request(500, 550)

        self.build_notebook()
        self.build_tabs()

        self.build_action_area("Edit", self.on_save)
        self.show_all()
        self.run()


class RunnerConfigDialog(Dialog):
    """Runners management dialog."""
    def __init__(self, runner):
        runner_name = runner.__class__.__name__
        super(RunnerConfigDialog, self).__init__("Configure %s" % runner_name)
        self.set_size_request(570, 500)
        self.runner_name = runner_name
        self.lutris_config = LutrisConfig(runner=runner_name)

        # Notebook for choosing between runner and system configuration
        self.notebook = Gtk.Notebook()
        self.vbox.pack_start(self.notebook, True, True, 0)

        # Runner configuration
        self.runner_config_vbox = RunnerBox(self.lutris_config, "runner",
                                            self.runner_name)
        runner_scrollwindow = Gtk.ScrolledWindow()
        runner_scrollwindow.set_policy(Gtk.PolicyType.AUTOMATIC,
                                       Gtk.PolicyType.AUTOMATIC)
        runner_scrollwindow.add_with_viewport(self.runner_config_vbox)
        self.notebook.append_page(runner_scrollwindow,
                                  Gtk.Label(label="Runner configuration"))

        # System configuration
        self.system_config_vbox = SystemBox(self.lutris_config, "runner")
        system_scrollwindow = Gtk.ScrolledWindow()
        system_scrollwindow.set_policy(Gtk.PolicyType.AUTOMATIC,
                                       Gtk.PolicyType.AUTOMATIC)
        system_scrollwindow.add_with_viewport(self.system_config_vbox)
        self.notebook.append_page(system_scrollwindow,
                                  Gtk.Label(label="System configuration"))

        # Action buttons
        cancel_button = Gtk.Button("Cancel")
        ok_button = Gtk.Button("Ok")
        self.action_area.pack_start(cancel_button, True, True, 0)
        self.action_area.pack_start(ok_button, True, True, 0)
        cancel_button.connect("clicked", self.close)
        ok_button.connect("clicked", self.ok_clicked)

        self.show_all()
        self.run()

    def close(self, _widget):
        self.destroy()

    def ok_clicked(self, _wigdet):
        self.lutris_config.config_type = "runner"
        self.lutris_config.save()
        self.destroy()


class SystemConfigDialog(Dialog, GameDialogCommon):
    def __init__(self):
        super(SystemConfigDialog, self).__init__("System preferences")
        self.set_title(self.title)
        self.set_size_request(500, 500)
        self.lutris_config = LutrisConfig()
        self.system_config_vbox = SystemBox(self.lutris_config, 'system')
        self.vbox.pack_start(self.system_config_vbox, True, True, 0)

        self.build_action_area("Save", self.save_config)
        self.show_all()

    def save_config(self, widget):
        self.lutris_config.save()
        self.destroy()
