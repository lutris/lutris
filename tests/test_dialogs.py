from lutris.gui import config_dialogs
from unittest import TestCase
from lutris import runners


class TestGameDialogCommon(TestCase):
    def test_get_runner_liststore(self):
        dlg = config_dialogs.GameDialogCommon()
        list_store = dlg.get_runner_liststore()
        self.assertEqual(list_store[0][0], dlg.no_runner_label)
        self.assertTrue(list_store[1][0].startswith(runners.__all__[0]))
        self.assertEqual(list_store[1][1], runners.__all__[0])


class TestGameDialog(TestCase):
    def test_dialog(self):
        dlg = config_dialogs.AddGameDialog(None)
        self.assertEqual(dlg.notebook.get_current_page(), 0)
