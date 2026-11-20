"""A game's errors stop it and are announced as notifications, without any UI."""

import pytest

from lutris.game import GAME_UNHANDLED_ERROR, Game
from lutris.game_errors import watch_game_errors


class FakeGame:
    STATE_STOPPED = "stopped"

    def __init__(self):
        self.state = "running"
        self.errors = []

    def stop_game(self):
        self.state = self.STATE_STOPPED

    def signal_error(self, error):
        self.errors.append(error)

    @watch_game_errors(game_stop_result=False)
    def fail(self):
        raise RuntimeError("it broke")

    @watch_game_errors(game_stop_result=False)
    def give_up(self):
        return False

    @watch_game_errors(game_stop_result=False)
    def keep_going(self):
        return True


def test_error_stops_the_game_and_is_signalled():
    game = FakeGame()

    assert game.fail() is False
    assert game.state == FakeGame.STATE_STOPPED
    assert [str(error) for error in game.errors] == ["it broke"]


def test_returning_the_stop_result_stops_the_game():
    game = FakeGame()
    assert game.give_up() is False
    assert game.state == FakeGame.STATE_STOPPED


def test_other_results_leave_the_game_running():
    game = FakeGame()
    assert game.keep_going() is True
    assert game.state == "running"
    assert game.errors == []


@pytest.fixture
def unhandled_errors(fake_main_loop):
    errors = []
    registration = GAME_UNHANDLED_ERROR.register(lambda game, error: errors.append((game, error)))
    yield errors
    registration.unregister()


def test_errors_nobody_handles_become_a_global_notification(fake_main_loop, unhandled_errors):
    game = Game()
    error = RuntimeError("no handler")

    game.signal_error(error)
    fake_main_loop.run_pending()

    assert unhandled_errors == [(game, error)]
