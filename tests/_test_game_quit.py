"""Tests for the cleanup Lutris does when a game quits."""

from unittest import TestCase
from unittest.mock import PropertyMock, patch

from lutris.database.games import add_game, delete_game
from lutris.game import Game
from lutris.util.test_config import setup_test_environment

setup_test_environment()


class TestKeyboardLayoutReset(TestCase):
    """The US layout option only switches the layout on X11, so only X11 needs it put back."""

    def setUp(self):
        game_id = add_game(name="Some Game", slug="some-game", runner="linux", installed=1, configpath="some-game")
        self.addCleanup(delete_game, game_id)
        self.game = Game(game_id)
        self.game.state = self.game.STATE_STOPPED
        runner_class = type(self.game.runner)
        for mock_patch in (
            patch.object(
                runner_class, "system_config", new_callable=PropertyMock, return_value={"use_us_layout": True}
            ),
            patch("lutris.game.os.chdir"),
        ):
            mock_patch.start()
            self.addCleanup(mock_patch.stop)

    def quit_game(self, is_x11):
        with patch("lutris.game.is_display_x11", return_value=is_x11), patch("lutris.game.subprocess.Popen") as popen:
            self.game.on_game_quit()
        return popen

    def test_layout_is_reset_on_x11(self):
        popen = self.quit_game(is_x11=True)
        self.assertEqual(popen.call_args.args[0], ["setxkbmap"])

    def test_layout_is_left_alone_elsewhere(self):
        popen = self.quit_game(is_x11=False)
        popen.assert_not_called()
