from unittest import TestCase

from lutris import runners
from lutris.gui.application import LutrisApplication
from lutris.gui.config.add_game_dialog import AddGameDialog
from lutris.util.test_config import setup_test_environment

setup_test_environment()


class TestGameDialogCommon(TestCase):
    def test_get_runner_dropdown(self):
        from lutris.gui.widgets.common import KeyValueDropDown

        dropdown = KeyValueDropDown()
        dropdown.append("", "Select a runner from the list")
        for runner in runners.get_installed():
            dropdown.append(runner.name, "%s (%s)" % (runner.human_name, runner.description))
        installed = runners.get_installed()
        if installed:
            self.assertEqual(dropdown._ids[1], installed[0].name)
            self.assertIn(installed[0].human_name, dropdown._string_list.get_string(1))


class TestGameDialog(TestCase):
    def setUp(self):
        lutris_application = LutrisApplication()
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

    def test_dialog(self):
        self.assertEqual(self.dlg.notebook.get_current_page(), 0)
