"""Tile caption formatting (headless regression tests).

These calls mirror Gtk exactly: Gtk.CellLayout.set_cell_data_func invokes
the callback as func(layout, cell, model, iter) when no user data is given,
so format_tile_caption must take exactly four arguments. A five-argument
version raised TypeError for every tile at runtime.
"""

import inspect
import unittest

from lutris.gui.views import COL_NAME, COL_PLATFORM, COL_RUNNER_HUMAN_NAME
from lutris.gui.views.grid import GameGridView


class FakeProps:
    markup = None


class FakeCell:
    def __init__(self):
        self.props = FakeProps()


class FakeModel:
    def __init__(self, values):
        self.values = values

    def get_value(self, _tree_iter, column):
        return self.values.get(column)


def format_caption(values):
    """Call the callback exactly like Gtk does: four positional arguments."""
    cell = FakeCell()
    GameGridView.format_tile_caption(None, cell, FakeModel(values), None)
    return cell.props.markup


class TestTileCaption(unittest.TestCase):
    def test_callback_takes_four_arguments(self):
        params = list(inspect.signature(GameGridView.format_tile_caption).parameters)
        self.assertEqual(len(params), 4)

    def test_full_details(self):
        self.assertEqual(
            format_caption({COL_NAME: "Undertail", COL_RUNNER_HUMAN_NAME: "Linux", COL_PLATFORM: "Linux"}),
            'Undertail\n<span size="smaller" alpha="60%">Linux • Linux</span>',
        )

    def test_partial_details(self):
        self.assertEqual(
            format_caption({COL_NAME: "Doom", COL_RUNNER_HUMAN_NAME: "GZDoom", COL_PLATFORM: ""}),
            'Doom\n<span size="smaller" alpha="60%">GZDoom</span>',
        )

    def test_missing_details_falls_back_to_name(self):
        self.assertEqual(
            format_caption({COL_NAME: "NoMeta", COL_RUNNER_HUMAN_NAME: "", COL_PLATFORM: None}),
            "NoMeta",
        )

    def test_values_are_not_reescaped(self):
        self.assertEqual(
            format_caption({COL_NAME: "Esc &lt;b&gt;", COL_RUNNER_HUMAN_NAME: "Wine", COL_PLATFORM: "Windows"}),
            'Esc &lt;b&gt;\n<span size="smaller" alpha="60%">Wine • Windows</span>',
        )


if __name__ == "__main__":
    unittest.main()
