"""The backend's events re-announce the core's game notifications with plain data."""

import pytest

from lutris import game as core
from lutris.backend import events
from lutris.backend.models import GameInfo
from lutris.database import games as games_db
from lutris.util.test_config import setup_test_environment

setup_test_environment()


@pytest.fixture
def game():
    game_id = games_db.add_game(name="Events Game", slug="events-game", runner="linux", installed=1, playtime=2.0)
    yield core.Game(str(game_id))
    games_db.delete_game(game_id)


def collect(event):
    received = []
    registration = event.register(lambda *args: received.append(args))
    return received, registration


@pytest.mark.parametrize(
    ("core_event", "event"),
    [
        (core.GAME_UPDATED, events.GAME_CHANGED),
        (core.GAME_INSTALLED, events.GAME_INSTALLED),
        (core.GAME_START, events.GAME_LAUNCHING),
        (core.GAME_STARTED, events.GAME_STARTED),
        (core.GAME_STOPPED, events.GAME_STOPPED),
    ],
)
def test_game_events_carry_game_info(fake_main_loop, game, core_event, event):
    received, registration = collect(event)
    try:
        core_event.fire(game)
        fake_main_loop.run_pending()  # The core's notification
        fake_main_loop.run_pending()  # The backend's
    finally:
        registration.unregister()

    assert len(received) == 1
    (info,) = received[0]
    assert isinstance(info, GameInfo)
    assert (info.id, info.name, info.playtime) == (game.id, "Events Game", 2.0)


def test_a_game_not_in_the_library_is_described_by_the_object(fake_main_loop):
    unsaved = core.Game()
    unsaved.name = "Not Saved"
    unsaved.slug = "not-saved"
    received, registration = collect(events.GAME_CHANGED)
    try:
        core.GAME_UPDATED.fire(unsaved)
        fake_main_loop.run_pending()
        fake_main_loop.run_pending()
    finally:
        registration.unregister()

    (info,) = received[0]
    assert (info.id, info.name, info.slug) == ("", "Not Saved", "not-saved")


def test_launch_status_and_failures_carry_the_game_id(fake_main_loop, game):
    statuses, status_registration = collect(events.GAME_LAUNCH_STATUS)
    failures, failure_registration = collect(events.GAME_FAILED)
    error = RuntimeError("Broken")
    try:
        game.launch_status = "Downloading the runtime"
        core.GAME_UNHANDLED_ERROR.fire(game, error)
        fake_main_loop.run_pending()
        fake_main_loop.run_pending()
    finally:
        status_registration.unregister()
        failure_registration.unregister()

    assert statuses == [(game.id, "Downloading the runtime")]
    assert failures == [(game.id, error)]
