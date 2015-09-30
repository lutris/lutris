import os
from gi.repository import Gio
from lutris.game import Game
from lutris.config import check_config
# from lutris import settings
# from lutris import pga
from lutris.gui import config_dialogs
from lutris.gui.lutriswindow import LutrisWindow
from unittest import TestCase
from lutris import runners

TEST_PGA_PATH = os.path.join(os.path.dirname(__file__), 'pga.db')


class TestGameDialogCommon(TestCase):
    def test_get_runner_liststore(self):
        dlg = config_dialogs.GameDialogCommon()
        list_store = dlg.get_runner_liststore()
        self.assertEqual(list_store[0][0], dlg.no_runner_label)
        self.assertTrue(
            list_store[1][0].startswith(sorted(runners.__all__)[0])
        )
        self.assertEqual(list_store[1][1], sorted(runners.__all__)[0])


class TestGameDialog(TestCase):
    def setUp(self):
        check_config()
        lutris_window = LutrisWindow()
        self.dlg = config_dialogs.AddGameDialog(lutris_window)

    def get_notebook(self):
        return self.dlg.vbox.get_children()[0]

    def get_viewport(self, index):
        scrolled_window = self.get_notebook().get_children()[index]
        viewport = scrolled_window.get_children()[0]
        return viewport.get_children()[0]

    def get_game_box(self):
        return self.get_viewport(1)

    def get_buttons(self):
        return self.dlg.vbox.get_children()[1].get_children()[1]

    def test_dialog(self):
        self.assertEqual(self.dlg.notebook.get_current_page(), 0)

    def test_changing_runner_sets_new_config(self):
        label = self.get_notebook().get_children()[1]
        self.assertIn('Select a runner', label.get_text())

        buttons = self.get_buttons().get_children()
        self.assertEqual(buttons[0].get_label(), 'Cancel')
        self.assertEqual(buttons[1].get_label(), 'Add')

        self.dlg.runner_dropdown.set_active_id('linux')
        self.assertEqual(self.dlg.lutris_config.runner_slug, 'linux')
        game_box = self.get_game_box()
        self.assertEqual(game_box.game.runner_name, 'linux')
        exe_box = game_box.get_children()[0].get_children()[0]
        exe_field = exe_box.get_children()[1]
        self.assertEqual(exe_field.__class__.__name__, 'FileChooserButton')

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
        exe_field.set_file(Gio.File.new_for_path(test_exe))
        exe_field.emit('file-set')
        self.assertEqual(exe_field.get_filename(), test_exe)

        add_button = self.get_buttons().get_children()[1]
        add_button.clicked()

        game = Game('test-game')
        self.assertEqual(game.name, 'Test game')
        game.remove(from_library=True)
