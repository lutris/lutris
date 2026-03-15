import unittest
from copy import deepcopy
from typing import Any
from unittest.mock import MagicMock, patch

from lutris.exceptions import MissingGameExecutableError
from lutris.runners.model import (
    DEFAULT_ENTRY_POINT_OPTION,
    RANGE_TYPE_REQUIRED_KEYS,
    REQUIRED_OPTION_KEYS,
    ModelRunner,
    RunnerDefinitionCategory,
)

TEST_RUNNER_DICT = {
    "human_name": "ModelRunner",
    "description": "Model Description",
    "platforms": ["Windows", "Linux"],
    "download_url": "https://lutris.net",
    "flatpak_id": "net.lutris.model.test",
    "runnable_alone": False,
    "entry_point_option": "rom",
    "runner_executable": "model-runner",
    "game_options": [{"option": "rom", "type": "file", "label": "Path to Game", "help": "help text"}],
    "runner_options": [
        {
            "option": "fullscreen",
            "type": "bool",
            "label": "Fullscreen",
            "default": True,
            "argument": "--fullscreen",
            "help": "Start Game in fullscreen mode.",
        }
    ],
    "system_options_override": [{"option": "disable_runtime", "default": True}],
    "env": {"SDL_VIDEODRIVER": "x11"},
    "working_dir": "runner",
}

TEST_REQUIRED_STRING_KEYS = {
    "human_name",
    "runner_executable",
}

TEST_OPTIONAL_STRING_KEYS = {"description", "flatpak_id", "download_url", "entry_point_option"}


class TestModelRunner(unittest.TestCase):
    def setUp(self):
        self.runner = ModelRunner()

    def test_create_model_runner(self):
        self.assertEqual(self.runner.entry_point_option, DEFAULT_ENTRY_POINT_OPTION)

    def test_init_from_dict(self):
        self.runner.from_dict(TEST_RUNNER_DICT)
        output_dict = self.runner.to_dict()
        self.assertDictEqual(output_dict, TEST_RUNNER_DICT)

    @patch("lutris.runners.runner.Runner.get_executable")
    @patch("os.path.isfile")
    @patch("lutris.util.system.path_exists")
    def test_play_valid_game_succeeds(self, mock_path_exists, mock_isfile, mock_get_executable):
        rom_name = "good_game"
        mock_path_exists.return_value = True
        mock_isfile.return_value = True
        mock_config = MagicMock()
        mock_config.game_config = {"rom": rom_name}
        mock_config.runner_config = {"fullscreen": True}

        mock_get_executable.return_value = "/path/to/model-runner"

        self.runner.from_dict(TEST_RUNNER_DICT)
        self.runner.config = mock_config
        expected = {
            "command": [self.runner.get_executable(), "--fullscreen", rom_name],
            "env": {"SDL_VIDEODRIVER": "x11"},
            "working_dir": "/path/to",
        }
        self.assertDictEqual(self.runner.play(), expected)

    @patch("os.path.isfile")
    @patch("lutris.util.system.path_exists")
    def test_play_missing_game_fails(self, mock_path_exists, mock_isfile):
        rom_name = "good_game"
        mock_path_exists.return_value = False
        mock_isfile.return_value = True
        mock_config = MagicMock()
        mock_config.game_config = {"rom": rom_name}
        mock_config.runner_config = {"fullscreen": True}

        self.runner.from_dict(TEST_RUNNER_DICT)
        self.runner.config = mock_config
        with self.assertRaises(MissingGameExecutableError):
            self.runner.play()

    ## Config option validation
    def test_validate_good_config_succeeds(self):
        valid_runner_dict = TEST_RUNNER_DICT
        runner_messages = ModelRunner.validate(valid_runner_dict)
        self.assertEqual(len(runner_messages.get_all()), 0)

    ### Game Options validation
    def test_validate_bad_config_no_game_option_for_entry_point_fails(self):
        invalid_runner_dict = deepcopy(TEST_RUNNER_DICT)
        invalid_runner_dict["entry_point_option"] = "iso"
        runner_messages = ModelRunner.validate(invalid_runner_dict)
        self.assertGreater(len(runner_messages.get_all()), 0)
        self.assertEqual(runner_messages.get_all()[0].key_path, "game_options")
        self.assertIn("require exactly one 'option' for the entry point", runner_messages.get_all()[0].message)
        self.assertEqual(runner_messages.get_all()[0].category, RunnerDefinitionCategory.ERROR)

    def test_validate_bad_config_game_options_missing(self):
        invalid_runner_dict = deepcopy(TEST_RUNNER_DICT)
        del invalid_runner_dict["game_options"]
        runner_messages = ModelRunner.validate(invalid_runner_dict)
        self.assertGreater(len(runner_messages.get_all()), 0)
        self.assertEqual(runner_messages.get_all()[0].key_path, "game_options")
        self.assertIn("must exist", runner_messages.get_all()[0].message)
        self.assertEqual(runner_messages.get_all()[0].category, RunnerDefinitionCategory.ERROR)

    def test_validate_bad_config_game_options_not_list(self):
        invalid_runner_dict = deepcopy(TEST_RUNNER_DICT)
        invalid_runner_dict["game_options"] = {}
        runner_messages = ModelRunner.validate(invalid_runner_dict)
        self.assertGreater(len(runner_messages.get_all()), 0)
        self.assertEqual(runner_messages.get_all()[0].key_path, "game_options")
        self.assertIn("must be a list", runner_messages.get_all()[0].message)
        self.assertEqual(runner_messages.get_all()[0].category, RunnerDefinitionCategory.ERROR)

    def test_validate_bad_config_game_options_empty_list(self):
        invalid_runner_dict = deepcopy(TEST_RUNNER_DICT)
        invalid_runner_dict["game_options"] = []
        runner_messages = ModelRunner.validate(invalid_runner_dict)
        self.assertGreater(len(runner_messages.get_all()), 0)
        self.assertEqual(runner_messages.get_all()[0].key_path, "game_options")
        self.assertIn("list must contain at least one element", runner_messages.get_all()[0].message)
        self.assertEqual(runner_messages.get_all()[0].category, RunnerDefinitionCategory.ERROR)

    ### Runner Options validation
    def test_validate_bad_config_runner_options_not_list(self):
        invalid_runner_dict = deepcopy(TEST_RUNNER_DICT)
        invalid_runner_dict["runner_options"] = {}
        runner_messages = ModelRunner.validate(invalid_runner_dict)
        self.assertGreater(len(runner_messages.get_all()), 0)
        self.assertEqual(runner_messages.get_all()[0].key_path, "runner_options")
        self.assertIn("must be a list", runner_messages.get_all()[0].message)
        self.assertEqual(runner_messages.get_all()[0].category, RunnerDefinitionCategory.ERROR)

    ### System Options Override validation
    def test_validate_bad_config_system_options_override_not_list(self):
        invalid_runner_dict = deepcopy(TEST_RUNNER_DICT)
        invalid_runner_dict["system_options_override"] = {}
        runner_messages = ModelRunner.validate(invalid_runner_dict)
        self.assertGreater(len(runner_messages.get_all()), 0)
        self.assertEqual(runner_messages.get_all()[0].key_path, "system_options_override")
        self.assertIn("must be a list", runner_messages.get_all()[0].message)
        self.assertEqual(runner_messages.get_all()[0].category, RunnerDefinitionCategory.WARNING)

    def test_validate_bad_config_system_options_override_missing_option_field(self):
        invalid_runner_dict = deepcopy(TEST_RUNNER_DICT)
        invalid_runner_dict["system_options_override"] = [{"default": True}]
        runner_messages = ModelRunner.validate(invalid_runner_dict)
        self.assertGreater(len(runner_messages.get_all()), 0)
        self.assertEqual(runner_messages.get_all()[0].key_path, "system_options_override")
        self.assertIn("must contain an 'option'", runner_messages.get_all()[0].message)
        self.assertEqual(runner_messages.get_all()[0].category, RunnerDefinitionCategory.WARNING)

    ### Individual option validation
    def test_validate_bad_config_option_required_keys_missing(self) -> None:
        for required_key in REQUIRED_OPTION_KEYS:
            with self.subTest(required_key):
                invalid_runner_dict: dict[str, Any] = deepcopy(TEST_RUNNER_DICT)
                del invalid_runner_dict["runner_options"][0][required_key]
                runner_messages = ModelRunner.validate(invalid_runner_dict)
                self.assertGreater(len(runner_messages.get_all()), 0)
                self.assertEqual(runner_messages.get_all()[0].key_path, f"runner_options.0.{required_key}")
                self.assertIn("Option is missing required key", runner_messages.get_all()[0].message)
                self.assertEqual(runner_messages.get_all()[0].category, RunnerDefinitionCategory.ERROR)

    def test_validate_bad_config_option_type_choice_missing_choices_field(self) -> None:
        invalid_runner_dict: dict[str, Any] = deepcopy(TEST_RUNNER_DICT)
        invalid_runner_dict["runner_options"][0]["type"] = "choice"
        runner_messages = ModelRunner.validate(invalid_runner_dict)
        self.assertGreater(len(runner_messages.get_all()), 0)
        self.assertEqual(runner_messages.get_all()[0].key_path, "runner_options.0.choices")
        self.assertIn("'choices' key is required for widget type", runner_messages.get_all()[0].message)
        self.assertEqual(runner_messages.get_all()[0].category, RunnerDefinitionCategory.ERROR)

    def test_validate_bad_config_option_type_range_missing_required_keys(self) -> None:
        for range_req_key in RANGE_TYPE_REQUIRED_KEYS:
            with self.subTest(range_req_key):
                invalid_runner_dict: dict[str, Any] = deepcopy(TEST_RUNNER_DICT)
                invalid_runner_dict["runner_options"][0]["type"] = "range"
                # Add all the required range keys and then delete the key that is passed in to this method
                for add_keys in RANGE_TYPE_REQUIRED_KEYS:
                    invalid_runner_dict["runner_options"][0][add_keys] = 0
                del invalid_runner_dict["runner_options"][0][range_req_key]
                runner_messages = ModelRunner.validate(invalid_runner_dict)
                self.assertGreater(len(runner_messages.get_all()), 0)
                self.assertEqual(runner_messages.get_all()[0].key_path, f"runner_options.0.{range_req_key}")
                self.assertIn("key is required for widget type 'range'", runner_messages.get_all()[0].message)
                self.assertEqual(runner_messages.get_all()[0].category, RunnerDefinitionCategory.ERROR)

    ### Strings validation - human_name, description, runner_executable, flatpak_id, download_url, entry_point_option
    def test_validate_bad_config_required_string_keys_missing(self):
        for string_key in TEST_REQUIRED_STRING_KEYS:
            with self.subTest(string_key):
                invalid_runner_dict = deepcopy(TEST_RUNNER_DICT)
                del invalid_runner_dict[string_key]
                runner_messages = ModelRunner.validate(invalid_runner_dict)
                self.assertGreater(len(runner_messages.get_all()), 0)
                self.assertEqual(runner_messages.get_all()[0].key_path, string_key)
                self.assertIn("must exist", runner_messages.get_all()[0].message)
                self.assertEqual(runner_messages.get_all()[0].category, RunnerDefinitionCategory.ERROR)

    def test_validate_bad_config_required_string_keys_empty(self):
        for string_key in TEST_REQUIRED_STRING_KEYS:
            with self.subTest(string_key):
                invalid_runner_dict = deepcopy(TEST_RUNNER_DICT)
                invalid_runner_dict[string_key] = ""
                runner_messages = ModelRunner.validate(invalid_runner_dict)
                self.assertGreater(len(runner_messages.get_all()), 0)
                self.assertEqual(runner_messages.get_all()[0].key_path, string_key)
                self.assertIn("must be non-empty", runner_messages.get_all()[0].message)
                self.assertEqual(runner_messages.get_all()[0].category, RunnerDefinitionCategory.ERROR)

    def test_validate_bad_config_optional_string_keys_empty(self):
        for string_key in TEST_OPTIONAL_STRING_KEYS:
            with self.subTest(string_key):
                invalid_runner_dict = deepcopy(TEST_RUNNER_DICT)
                invalid_runner_dict[string_key] = ""
                runner_messages = ModelRunner.validate(invalid_runner_dict)
                self.assertGreater(len(runner_messages.get_all()), 0)
                self.assertEqual(runner_messages.get_all()[0].key_path, string_key)
                self.assertIn("must be non-empty", runner_messages.get_all()[0].message)
                self.assertEqual(runner_messages.get_all()[0].category, RunnerDefinitionCategory.WARNING)

    ### Platforms validation
    def test_validate_bad_config_platforms_key_is_missing(self):
        invalid_runner_dict = deepcopy(TEST_RUNNER_DICT)
        del invalid_runner_dict["platforms"]
        runner_messages = ModelRunner.validate(invalid_runner_dict)
        self.assertGreater(len(runner_messages.get_all()), 0)
        self.assertEqual(runner_messages.get_all()[0].key_path, "platforms")
        self.assertIn("must exist", runner_messages.get_all()[0].message)
        self.assertEqual(runner_messages.get_all()[0].category, RunnerDefinitionCategory.ERROR)

    def test_validate_bad_config_platforms_key_is_empty_list(self):
        invalid_runner_dict = deepcopy(TEST_RUNNER_DICT)
        invalid_runner_dict["platforms"] = []
        runner_messages = ModelRunner.validate(invalid_runner_dict)
        self.assertGreater(len(runner_messages.get_all()), 0)
        self.assertEqual(runner_messages.get_all()[0].key_path, "platforms")
        self.assertIn("list must contain at least one string element", runner_messages.get_all()[0].message)
        self.assertEqual(runner_messages.get_all()[0].category, RunnerDefinitionCategory.ERROR)

    def test_validate_bad_config_platforms_key_is_empty_dict(self):
        invalid_runner_dict = deepcopy(TEST_RUNNER_DICT)
        invalid_runner_dict["platforms"] = {}
        runner_messages = ModelRunner.validate(invalid_runner_dict)
        self.assertGreater(len(runner_messages.get_all()), 0)
        self.assertEqual(runner_messages.get_all()[0].key_path, "platforms")
        self.assertIn("dict must contain at least one string element", runner_messages.get_all()[0].message)
        self.assertEqual(runner_messages.get_all()[0].category, RunnerDefinitionCategory.ERROR)

    def test_validate_bad_config_platforms_key_is_empty_string(self):
        invalid_runner_dict = deepcopy(TEST_RUNNER_DICT)
        invalid_runner_dict["platforms"] = ""
        runner_messages = ModelRunner.validate(invalid_runner_dict)
        self.assertGreater(len(runner_messages.get_all()), 0)
        self.assertEqual(runner_messages.get_all()[0].key_path, "platforms")
        self.assertIn("string field cannot be empty", runner_messages.get_all()[0].message)
        self.assertEqual(runner_messages.get_all()[0].category, RunnerDefinitionCategory.ERROR)

    def test_validate_bad_config_platforms_key_is_list_contains_empty_string(self):
        invalid_runner_dict = deepcopy(TEST_RUNNER_DICT)
        invalid_runner_dict["platforms"] = [""]
        runner_messages = ModelRunner.validate(invalid_runner_dict)
        self.assertGreater(len(runner_messages.get_all()), 0)
        self.assertEqual(runner_messages.get_all()[0].key_path, "platforms")
        self.assertIn("list string entry cannot be empty", runner_messages.get_all()[0].message)
        self.assertEqual(runner_messages.get_all()[0].category, RunnerDefinitionCategory.ERROR)

    def test_validate_bad_config_platforms_key_is_dict_contains_empty_string(self):
        invalid_runner_dict = deepcopy(TEST_RUNNER_DICT)
        invalid_runner_dict["platforms"] = {"Windows": ""}
        runner_messages = ModelRunner.validate(invalid_runner_dict)
        self.assertGreater(len(runner_messages.get_all()), 0)
        self.assertEqual(runner_messages.get_all()[0].key_path, "platforms")
        self.assertIn("dict string entry cannot be empty", runner_messages.get_all()[0].message)
        self.assertEqual(runner_messages.get_all()[0].category, RunnerDefinitionCategory.ERROR)

    ### Runnable Alone Validation (i.e The runner can be invoked without a game argument)
    def test_validate_good_config_runnable_alone_is_convertible_to_bool(self):
        invalid_runner_dict = deepcopy(TEST_RUNNER_DICT)
        invalid_runner_dict["runnable_alone"] = 1
        runner_messages = ModelRunner.validate(invalid_runner_dict)
        self.assertEqual(len(runner_messages.get_all()), 0)

    ## get_platform tests
    def test_get_platform_with_with_platform_key_succeeds(self):
        mock_config = MagicMock()
        mock_config.game_config = {"platform": "Linux"}

        self.runner.from_dict(TEST_RUNNER_DICT)
        self.runner.config = mock_config
        self.assertEqual(self.runner.get_platform(), "Linux")

    def test_get_platform_with_without_platform_key_returns_first_key(self):
        mock_config = MagicMock()
        mock_config.game_config = {}

        self.runner.from_dict(TEST_RUNNER_DICT)
        self.runner.config = mock_config
        self.assertEqual(self.runner.get_platform(), TEST_RUNNER_DICT["platforms"][0])

    def test_get_platform_succeeds_if_platforms_key_is_string(self):
        mock_config = MagicMock()
        mock_config.game_config = {}

        valid_runner_dict = deepcopy(TEST_RUNNER_DICT)
        valid_runner_dict["platforms"] = "Steam"
        self.runner.from_dict(valid_runner_dict)
        self.runner.config = mock_config
        self.assertEqual(self.runner.get_platform(), "Steam")

    def test_get_platform_succeeds_if_platforms_key_is_dict(self):
        mock_config = MagicMock()
        mock_config.game_config = {"platform": "Pocket Challenge V2"}

        valid_runner_dict = deepcopy(TEST_RUNNER_DICT)
        valid_runner_dict["platforms"] = {
            "WonderSwan Color": "Bandai WonderSwan Color",
            "Pocket Challenge V2": "Benesse Pocket Challenge V2",
        }
        self.runner.from_dict(valid_runner_dict)
        self.runner.config = mock_config
        self.assertEqual(self.runner.get_platform(), "Benesse Pocket Challenge V2")
