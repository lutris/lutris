from unittest import TestCase

from lutris import runners
from lutris.gui.application import LutrisApplication
from lutris.gui.config.add_game_dialog import AddGameDialog
from lutris.gui.config.game_info_box import GameInfoBox
from lutris.gui.views.store import sort_func
from lutris.util.test_config import setup_test_environment

setup_test_environment()


class TestGameDialogCommon(TestCase):
    def test_get_runner_liststore(self):
        list_store = GameInfoBox._get_runner_liststore()
        self.assertTrue(list_store[1][0].startswith(runners.get_installed()[0].human_name))
        self.assertEqual(list_store[1][1], runners.get_installed()[0].name)


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


class TestSort(TestCase):
    class FakeModel(object):
        def __init__(self, rows):
            self.rows = rows

        def get_value(self, row_index, col_name):
            return self.rows[row_index].cols.get(col_name)

    class FakeRow(object):
        def __init__(self, coldict):
            self.cols = coldict

    def test_sort_strings_with_caps(self):
        row1 = self.FakeRow({"name": "Abc"})
        row2 = self.FakeRow({"name": "Def"})
        model = self.FakeModel([row1, row2])
        assert sort_func(model, 0, 1, "name") == -1

    def test_sort_strings_with_one_caps(self):
        row1 = self.FakeRow({"name": "abc"})
        row2 = self.FakeRow({"name": "Def"})
        model = self.FakeModel([row1, row2])
        assert sort_func(model, 0, 1, "name") == -1

    def test_sort_strings_with_no_caps(self):
        row1 = self.FakeRow({"name": "abc"})
        row2 = self.FakeRow({"name": "def"})
        model = self.FakeModel([row1, row2])
        assert sort_func(model, 0, 1, "name") == -1

    def test_sort_int(self):
        row1 = self.FakeRow({"name": 1})
        row2 = self.FakeRow({"name": 2})
        model = self.FakeModel([row1, row2])
        assert sort_func(model, 0, 1, "name") == -1

    def test_sort_mismatched_types(self):
        row1 = self.FakeRow({"name": "abc"})
        row2 = self.FakeRow({"name": 1})
        model = self.FakeModel([row1, row2])
        with self.assertRaises(TypeError):
            assert sort_func(model, 0, 1, "name") == -1

    def test_both_none(self):
        row1 = self.FakeRow({})
        row2 = self.FakeRow({})
        model = self.FakeModel([row1, row2])
        assert sort_func(model, 0, 1, "name") == 0

    def test_one_none(self):
        row1 = self.FakeRow({})
        row2 = self.FakeRow({"name": "abc"})
        model = self.FakeModel([row1, row2])
        assert sort_func(model, 0, 1, "name") == -1
