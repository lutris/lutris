import os
import gi

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk
from lutris.game import Game
from lutris.config import check_config
# from lutris import settings
from lutris import pga
from lutris.gui.config.common import GameDialogCommon
from lutris.gui.config.add_game import AddGameDialog
from lutris.gui.application import Application
from unittest import TestCase
from lutris import runners

TEST_PGA_PATH = os.path.join(os.path.dirname(__file__), 'pga.db')


class TestGameDialogCommon(TestCase):
    def test_get_runner_liststore(self):
        dlg = GameDialogCommon()
        list_store = dlg._get_runner_liststore()
        self.assertTrue(
            list_store[1][0].startswith(runners.get_installed()[0].human_name)
        )
        self.assertEqual(list_store[1][1], runners.get_installed()[0].name)


class TestGameDialog(TestCase):
    def setUp(self):
        check_config()
        lutris_application = Application()
        lutris_window = lutris_application.window
        self.dlg = AddGameDialog(lutris_window)

    def get_notebook(self):
        return self.dlg.vbox.get_children()[0]

    def get_viewport(self, index):
        children = self.get_notebook().get_children()
        try:
            scrolled_window = children[index]
        except IndexError:
            print("No viewport for index %s" % index)
            print(children)
            raise
        viewport = scrolled_window.get_children()[0]
        return viewport.get_children()[0]

    def get_game_box(self):
        return self.get_viewport(1)

    def get_buttons(self):
        notebook = self.dlg.vbox.get_children()[1]
        # For some reason, there isn't a ButtonBox on Ubuntu 14.4, weird.
        button_box = notebook.get_children()[0]
        if button_box.__class__ == Gtk.CheckButton:
            button_hbox = notebook.get_children()[1]
        else:
            button_hbox = button_box.get_children()[1]
        self.assertEqual(button_hbox.__class__, Gtk.Box)
        return button_hbox

    def test_dialog(self):
        self.assertEqual(self.dlg.notebook.get_current_page(), 0)

    def test_changing_runner_sets_new_config(self):
        label = self.get_notebook().get_children()[1]
        self.assertIn('Select a runner', label.get_text())

        buttons = self.get_buttons().get_children()
        self.assertEqual(buttons[0].get_label(), 'Cancel')
        self.assertEqual(buttons[1].get_label(), 'Save')

        self.dlg.runner_dropdown.set_active_id('linux')
        self.assertEqual(self.dlg.lutris_config.runner_slug, 'linux')
        game_box = self.get_game_box()
        self.assertEqual(game_box.game.runner_name, 'linux')
        exe_box = game_box.get_children()[0].get_children()[0]
        exe_field = exe_box.get_children()[1]
        self.assertEqual(exe_field.__class__.__name__, 'FileChooserEntry')

    def test_can_add_game(self):
        name_entry = self.dlg.name_entry
        name_entry.set_text("Test game")
        self.dlg.runner_dropdown.set_active_id('linux')

        game_box = self.get_game_box()
        exe_box = game_box.get_children()[0].get_children()[0]
        exe_label = exe_box.get_children()[0]
        self.assertEqual(exe_label.get_text(), "Executable")
        test_exe = os.path.abspath(__file__)
        exe_field = exe_box.get_children()[1]
        exe_field.entry.set_text(test_exe)
        self.assertEqual(exe_field.get_filename(), test_exe)

        add_button = self.get_buttons().get_children()[1]
        add_button.clicked()

        pga_game = pga.get_game_by_field('test-game', 'slug')
        self.assertTrue(pga_game)
        game = Game(pga_game['id'])
        self.assertEqual(game.name, 'Test game')
        game.remove(from_library=True)
