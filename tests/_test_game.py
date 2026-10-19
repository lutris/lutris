from unittest import TestCase
from unittest.mock import MagicMock, patch

from lutris.exceptions import MissingGameExecutableError
from lutris.game import Game
from lutris.util.test_config import setup_test_environment

setup_test_environment()


class TestGameLaunchValidation(TestCase):
    def test_validation_runs_before_prelaunch(self):
        error = MissingGameExecutableError(filename="/unmounted/game.exe")
        runner = MagicMock()
        runner.name = "wine"
        runner.is_installed.return_value = True
        runner.validate_game.side_effect = error

        game = Game()
        game._id = "1"
        game._game_config_id = "test-game"
        game.is_installed = True
        game.runner = runner

        launch_ui_delegate = MagicMock()
        launch_ui_delegate.check_game_launchable.return_value = True
        launch_ui_delegate.wait_for_component_updates.side_effect = lambda _game, callback: callback()

        with patch.object(game, "reload_config"), patch.object(game, "signal_error") as signal_error:
            game.launch(launch_ui_delegate)

        runner.validate_game.assert_called_once_with()
        runner.prelaunch.assert_not_called()
        signal_error.assert_called_once_with(error)
