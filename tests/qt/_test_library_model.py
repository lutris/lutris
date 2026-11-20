"""The Qt library window's table of games."""

from PySide6.QtCore import Qt

from lutris.backend.models import LibraryGame
from lutris.qt.library_model import COLUMNS, GameRole, LibraryModel


def make_game(game_id: str, name: str, installed: bool = True, **values) -> LibraryGame:
    fields = {
        "id": game_id,
        "game_id": game_id,
        "name": name,
        "sortname": "",
        "slug": name.lower(),
        "year": None,
        "runner": "linux",
        "runner_name": "Linux",
        "platform": "Linux",
        "installed": installed,
        "installed_at": None,
        "lastplayed": None,
        "playtime": None,
        "service": None,
        "service_id": None,
        "appid": None,
        "icon": None,
    }
    fields.update(values)
    return LibraryGame(**fields)


def column(name: str) -> int:
    return next(index for index, (column_name, _title, _key) in enumerate(COLUMNS) if column_name == name)


def test_rows_show_their_games(qt_application):
    model = LibraryModel()
    model.set_games([make_game("1", "Doom", year=1993, playtime=1.5), make_game("2", "Quake", installed=False)])

    assert model.rowCount() == 2
    assert model.data(model.index(0, column("name"))) == "Doom"
    assert model.data(model.index(0, column("runner"))) == "Linux"
    assert model.data(model.index(0, column("year"))) == "1993"
    assert model.data(model.index(0, column("playtime"))) == "1 hour 30 minutes"
    assert model.data(model.index(1, column("playtime"))) == ""
    assert model.data(model.index(1, 0), GameRole).name == "Quake"
    assert model.find_row("2") == 1
    assert model.find_row("3") is None


def test_running_games_are_bold_and_uninstalled_ones_dimmed(qt_application):
    model = LibraryModel()
    model.set_games([make_game("1", "Doom"), make_game("2", "Quake", installed=False)])
    model.set_running_game_ids({"1"})

    assert model.data(model.index(0, 0), Qt.ItemDataRole.FontRole).bold()
    assert model.data(model.index(1, 0), Qt.ItemDataRole.FontRole) is None
    assert model.data(model.index(0, 0), Qt.ItemDataRole.ForegroundRole) is None
    assert model.data(model.index(1, 0), Qt.ItemDataRole.ForegroundRole) is not None
