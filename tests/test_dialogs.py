from lutris.gui import config_dialogs
from unittest import TestCase


class TestGameDialog(TestCase):
    def test_dialog(self):
        dlg = config_dialogs.AddGameDialog(None)
        self.assertEqual(dlg.notebook.get_current_page(), 0)
