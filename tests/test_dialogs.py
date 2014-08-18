import os
from gi.repository import Gio
from lutris.game import Game
from lutris import pga
from lutris.gui import config_dialogs
from unittest import TestCase
from lutris import runners

TEST_PGA_PATH = os.path.join(os.path.dirname(__file__), 'pga.db')


class TestGameDialogCommon(TestCase):
    def test_get_runner_liststore(self):
        dlg = config_dialogs.GameDialogCommon()
        list_store = dlg.get_runner_liststore()
        self.assertEqual(list_store[0][0], dlg.no_runner_label)
        self.assertTrue(list_store[1][0].startswith(runners.__all__[0]))
        self.assertEqual(list_store[1][1], runners.__all__[0])


class TestGameDialog(TestCase):
    def setUp(self):
        pga.syncdb()

    def test_dialog(self):
        dlg = config_dialogs.AddGameDialog(None)
        self.assertEqual(dlg.notebook.get_current_page(), 0)

    def test_changing_runner_sets_new_config(self):
        dlg = config_dialogs.AddGameDialog(None)
        runner_dropdown = dlg.vbox.get_children()[1]
        notebook = dlg.vbox.get_children()[2]
        label = notebook.get_children()[0]
        self.assertIn('Select a runner', label.get_text())

        buttons = dlg.vbox.get_children()[3].get_children()
        self.assertEqual(buttons[0].get_label(), 'Cancel')
        self.assertEqual(buttons[1].get_label(), 'Add')

        runner_dropdown.set_active(1)
        self.assertEqual(dlg.lutris_config.runner, runners.__all__[0])
        scrolled_window = notebook.get_children()[0]
        viewport = scrolled_window.get_children()[0]
        game_box = viewport.get_children()[0]
        self.assertEqual(game_box.runner_name, runners.__all__[0])
        exe_field = game_box.get_children()[0].get_children()[1]
        self.assertEqual(exe_field.__class__.__name__, 'FileChooserButton')

        runner_dropdown.set_active(2)
        self.assertEqual(dlg.lutris_config.runner, runners.__all__[1])

    def test_can_add_game(self):
        dlg = config_dialogs.AddGameDialog(None)
        name_entry = dlg.vbox.get_children()[0].get_children()[1]
        runner_dropdown = dlg.vbox.get_children()[1]
        name_entry.set_text("Test game")
        runner_dropdown.set_active(1)

        notebook = dlg.vbox.get_children()[2]
        scrolled_window = notebook.get_children()[0]
        viewport = scrolled_window.get_children()[0]
        game_box = viewport.get_children()[0]
        exe_label = game_box.get_children()[0].get_children()[0]
        self.assertEqual(exe_label.get_text(), "Executable")
        test_exe = os.path.abspath(__file__)
        exe_field = game_box.get_children()[0].get_children()[1]
        exe_field.set_file(Gio.File.new_for_path(test_exe))
        exe_field.emit('file-set')
        self.assertEqual(exe_field.get_filename(), test_exe)

        add_button = dlg.vbox.get_children()[3].get_children()[1]
        add_button.clicked()

        game = Game('test-game')
        self.assertEqual(game.name, 'Test game')
        game.remove(from_library=True)
