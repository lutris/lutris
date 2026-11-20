"""Library rows and artwork are available through Qt Quick model roles."""

from PySide6.QtGui import QGuiApplication

from lutris.backend.models import LibraryArtwork, LibraryGame
from lutris.qt.library_model import GameRole, LibraryModel


def make_game(
    game_id: str,
    name: str,
    installed: bool = True,
    *,
    year: int | None = None,
    playtime: float | None = None,
    artwork: LibraryArtwork | None = None,
) -> LibraryGame:
    return LibraryGame(
        id=game_id,
        game_id=game_id,
        name=name,
        sortname="",
        slug=name.lower(),
        year=year,
        runner="linux",
        runner_name="Linux",
        platform="Linux",
        installed=installed,
        installed_at=None,
        lastplayed=None,
        playtime=playtime,
        service=None,
        service_id=None,
        appid=None,
        icon=None,
        artwork=artwork,
    )


def test_rows_show_their_games(qt_application: QGuiApplication) -> None:
    model = LibraryModel()
    model.set_games([make_game("1", "Doom", year=1993, playtime=1.5), make_game("2", "Quake", installed=False)])

    assert model.rowCount() == 2
    assert model.data(model.index(0), GameRole.TITLE) == "Doom"
    assert model.data(model.index(0), GameRole.RUNNER) == "Linux"
    assert model.data(model.index(0), GameRole.YEAR) == "1993"
    assert model.data(model.index(0), GameRole.PLAY_TIME) == "1 hour 30 minutes"
    assert model.data(model.index(1), GameRole.PLAY_TIME) == ""
    assert model.data(model.index(1), GameRole.TITLE) == "Quake"
    assert model.find_row("2") == 1
    assert model.find_row("3") == -1


def test_running_and_installed_state_are_exposed_to_qml(qt_application: QGuiApplication) -> None:
    model = LibraryModel()
    model.set_games([make_game("1", "Doom"), make_game("2", "Quake", installed=False)])
    model.set_running_game_ids({"1"})

    assert model.data(model.index(0), GameRole.RUNNING) is True
    assert model.data(model.index(1), GameRole.RUNNING) is False
    assert model.data(model.index(0), GameRole.INSTALLED) is True
    assert model.data(model.index(1), GameRole.INSTALLED) is False
