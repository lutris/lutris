import unittest
from copy import deepcopy
from typing import Any, NamedTuple
from unittest.mock import MagicMock, patch

from lutris.exceptions import MissingGameExecutableError
from lutris.runners.model import (
    DEFAULT_ENTRY_POINT_OPTION,
    ModelRunner,
)

TEST_RUNNER_DICT = {
    "name": "model-runner",
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


TEST_OPTION_TYPES_DICT_TEMPLATE = {
    "name": "model-runner",
    "human_name": "ModelRunner",
    "description": "Model Description",
    "platforms": ["Windows", "Linux"],
    "download_url": "https://lutris.net",
    "flatpak_id": "net.lutris.model.test",
    "runnable_alone": False,
    "entry_point_option": "rom",
    "runner_executable": "model-runner",
    "game_options": [{"option": "rom", "type": "file", "label": "Path to Game", "help": "help text"}],
    "runner_options": [],
    "system_options_override": [{"option": "disable_runtime", "default": True}],
    "env": {"SDL_VIDEODRIVER": "x11"},
    "working_dir": "runner",
}


TEST_REQUIRED_STRING_KEYS = {
    "human_name",
    "runner_executable",
}


class OptionConfigParams(NamedTuple):
    runner_config: dict[str, Any]
    expected_command_args: list[str | bool | int | float]
    expected_result: bool


class OptionTestParams(NamedTuple):
    option_dict: dict[str, Any]
    option_configs: list[OptionConfigParams]


TEST_OPTIONAL_STRING_KEYS = {"description", "flatpak_id", "download_url", "entry_point_option"}


TEST_OPTION_TYPES_PARAMS: list[OptionTestParams] = [
    OptionTestParams(
        {
            "option": "bool_argument",
            "type": "bool",
            "label": "Bool",
            "default": True,
            "argument": "--bool",
        },
        [
            OptionConfigParams({"bool_argument": True}, ["--bool"], True),
            OptionConfigParams({"bool_argument": False}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {
            "option": "bool_no_argument",
            "type": "bool",
            "label": "Bool",
            "default": False,
        },
        [
            OptionConfigParams({"bool_no_argument": True}, [], True),
            OptionConfigParams({"bool_no_argument": False}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {
            "option": "bool_empty_argument",
            "type": "bool",
            "label": "Bool",
            "default": True,
            "argument": "",
        },
        [
            OptionConfigParams({"bool_empty_argument": True}, [], True),
            OptionConfigParams({"bool_empty_argument": False}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {
            "option": "label",
            "type": "label",
            "label": "This is a Note",
        },
        [
            OptionConfigParams({"label": "Could be any type"}, [], True),
            OptionConfigParams({"label": False}, [], True),
            OptionConfigParams({"label": 42}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {"option": "string_argument", "type": "string", "argument": "--string"},
        [
            OptionConfigParams({"string_argument": "True"}, ["--string", "True"], True),
            OptionConfigParams({"string_argument": ""}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {
            "option": "string_no_argument",
            "type": "string",
        },
        [
            OptionConfigParams({"string_no_argument": "True"}, ["True"], True),
            OptionConfigParams({"string_no_argument": ""}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {"option": "string_with_empty_argument", "type": "string", "argument": ""},
        [
            OptionConfigParams({"string_with_empty_argument": "True"}, ["True"], True),
            OptionConfigParams({"string_with_empty_argument": ""}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {"option": "range_argument", "type": "range", "argument": "--range"},
        [
            OptionConfigParams({"range_argument": "True"}, ["--range", "True"], True),
            OptionConfigParams({"range_argument": ""}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {
            "option": "range_no_argument",
            "type": "range",
        },
        [
            OptionConfigParams({"range_no_argument": "True"}, ["True"], True),
            OptionConfigParams({"range_no_argument": ""}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {"option": "range_with_empty_argument", "type": "range", "argument": ""},
        [
            OptionConfigParams({"range_with_empty_argument": "True"}, ["True"], True),
            OptionConfigParams({"range_with_empty_argument": ""}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {"option": "file_argument", "type": "file", "argument": "--file"},
        [
            OptionConfigParams({"file_argument": "True"}, ["--file", "True"], True),
            OptionConfigParams({"file_argument": ""}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {
            "option": "file_no_argument",
            "type": "file",
        },
        [
            OptionConfigParams({"file_no_argument": "True"}, ["True"], True),
            OptionConfigParams({"file_no_argument": ""}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {"option": "file_with_empty_argument", "type": "file", "argument": ""},
        [
            OptionConfigParams({"file_with_empty_argument": "True"}, ["True"], True),
            OptionConfigParams({"file_with_empty_argument": ""}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {"option": "directory_argument", "type": "directory", "argument": "--directory"},
        [
            OptionConfigParams({"directory_argument": "True"}, ["--directory", "True"], True),
            OptionConfigParams({"directory_argument": ""}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {
            "option": "directory_no_argument",
            "type": "directory",
        },
        [
            OptionConfigParams({"directory_no_argument": "True"}, ["True"], True),
            OptionConfigParams({"directory_no_argument": ""}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {"option": "directory_with_empty_argument", "type": "directory", "argument": ""},
        [
            OptionConfigParams({"directory_with_empty_argument": "True"}, ["True"], True),
            OptionConfigParams({"directory_with_empty_argument": ""}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {"option": "multiple_file_argument", "type": "multiple_file", "argument": "--multiple-file"},
        [
            OptionConfigParams({"multiple_file_argument": "True"}, ["--multiple-file", "True"], True),
            OptionConfigParams({"multiple_file_argument": "True False"}, ["--multiple-file", "True", "False"], True),
            OptionConfigParams({"multiple_file_argument": '"True False"'}, ["--multiple-file", "True False"], True),
            OptionConfigParams({"multiple_file_argument": ""}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {
            "option": "multiple_file_no_argument",
            "type": "multiple_file",
        },
        [
            OptionConfigParams({"multiple_file_no_argument": "True"}, ["True"], True),
            OptionConfigParams({"multiple_file_no_argument": "True False"}, ["True", "False"], True),
            OptionConfigParams({"multiple_file_no_argument": '"True False"'}, ["True False"], True),
            OptionConfigParams({"multiple_file_no_argument": ""}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {"option": "multiple_file_with_empty_argument", "type": "multiple_file", "argument": ""},
        [
            OptionConfigParams({"multiple_file_with_empty_argument": "True"}, ["True"], True),
            OptionConfigParams({"multiple_file_with_empty_argument": "True False"}, ["True", "False"], True),
            OptionConfigParams({"multiple_file_with_empty_argument": '"True False"'}, ["True False"], True),
            OptionConfigParams({"multiple_file_with_empty_argument": ""}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {"option": "command_line_argument", "type": "command_line", "argument": "--command-line"},
        [
            OptionConfigParams({"command_line_argument": "True"}, ["--command-line", "True"], True),
            OptionConfigParams({"command_line_argument": "True False"}, ["--command-line", "True", "False"], True),
            OptionConfigParams({"command_line_argument": '"True False"'}, ["--command-line", "True False"], True),
            OptionConfigParams({"command_line_argument": ""}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {
            "option": "command_line_no_argument",
            "type": "command_line",
        },
        [
            OptionConfigParams({"command_line_no_argument": "True"}, ["True"], True),
            OptionConfigParams({"command_line_no_argument": "True False"}, ["True", "False"], True),
            OptionConfigParams({"command_line_no_argument": '"True False"'}, ["True False"], True),
            OptionConfigParams({"command_line_no_argument": ""}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {"option": "command_line_with_empty_argument", "type": "command_line", "argument": ""},
        [
            OptionConfigParams({"command_line_with_empty_argument": "True"}, ["True"], True),
            OptionConfigParams({"command_line_with_empty_argument": "True False"}, ["True", "False"], True),
            OptionConfigParams({"command_line_with_empty_argument": '"True False"'}, ["True False"], True),
            OptionConfigParams({"command_line_with_empty_argument": ""}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {"option": "mapping_argument", "type": "mapping", "argument": "--mapping"},
        [
            OptionConfigParams(
                {"mapping_argument": {"foo": "True", "bar": 1}}, ["--mapping", "foo=True", "--mapping", "bar=1"], True
            ),
            OptionConfigParams({"mapping_argument": "NotADictShouldNotAddArguments"}, [], True),
            OptionConfigParams({"mapping_argument": ""}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {
            "option": "mapping_no_argument",
            "type": "mapping",
        },
        [
            OptionConfigParams({"mapping_no_argument": {"foo": "True", "bar": 1}}, ["foo=True", "bar=1"], True),
            OptionConfigParams({"mapping_no_argument": "NotADictShouldNotAddArguments"}, [], True),
            OptionConfigParams({"mapping_no_argument": False}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {"option": "mapping_empty_argument", "type": "mapping", "argument": ""},
        [
            OptionConfigParams({"mapping_empty_argument": {"foo": "True", "bar": 1}}, ["foo=True", "bar=1"], True),
            OptionConfigParams({"mapping_empty_argument": "NotADictShouldNotAddArguments"}, [], True),
            OptionConfigParams({"mapping_empty_argument": False}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {"option": "choice_argument", "type": "choice", "argument": "--choice"},
        [
            OptionConfigParams({"choice_argument": "True"}, ["--choice", "True"], True),
            OptionConfigParams({"choice_argument": 7}, ["--choice", 7], True),
            OptionConfigParams({"choice_argument": False}, ["--choice", False], True),
            OptionConfigParams({"choice_argument": 14.0}, ["--choice", 14.0], True),
            # Having an empty string choice make sense for selecting from a drop-down
            OptionConfigParams({"choice_argument": ""}, ["--choice", ""], True),
            # Check 'off' special case here
            OptionConfigParams({"choice_argument": "off"}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {"option": "choice_no_argument", "type": "choice"},
        [
            OptionConfigParams({"choice_no_argument": "True"}, ["True"], True),
            OptionConfigParams({"choice_no_argument": 7}, [7], True),
            OptionConfigParams({"choice_no_argument": False}, [False], True),
            OptionConfigParams({"choice_no_argument": 14.0}, [14.0], True),
            # Having an empty string choice make sense for selecting from a drop-down
            OptionConfigParams({"choice_no_argument": ""}, [""], True),
            # Check 'off' special case here
            OptionConfigParams({"choice_no_argument": "off"}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {"option": "choice_empty_argument", "type": "choice", "argument": ""},
        [
            OptionConfigParams({"choice_empty_argument": "True"}, ["True"], True),
            OptionConfigParams({"choice_empty_argument": 7}, [7], True),
            OptionConfigParams({"choice_empty_argument": False}, [False], True),
            OptionConfigParams({"choice_empty_argument": 14.0}, [14.0], True),
            # Having an empty string choice make sense for selecting from a drop-down
            OptionConfigParams({"choice_empty_argument": ""}, [""], True),
            # Check 'off' special case here
            OptionConfigParams({"choice_empty_argument": "off"}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {"option": "choice_with_entry_argument", "type": "choice_with_entry", "argument": "choice-with-entry"},
        [
            OptionConfigParams({"choice_with_entry_argument": "True"}, ["choice-with-entry", "True"], True),
            OptionConfigParams({"choice_with_entry_argument": 7}, ["choice-with-entry", 7], True),
            OptionConfigParams({"choice_with_entry_argument": False}, ["choice-with-entry", False], True),
            OptionConfigParams({"choice_with_entry_argument": 14.0}, ["choice-with-entry", 14.0], True),
            # Having an empty string choice_with_entry make sense for selecting from a drop-down
            OptionConfigParams({"choice_with_entry_argument": ""}, ["choice-with-entry", ""], True),
            # Check 'off' special case here
            OptionConfigParams({"choice_with_entry_argument": "off"}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {"option": "choice_with_entry_no_argument", "type": "choice_with_entry"},
        [
            OptionConfigParams({"choice_with_entry_no_argument": "True"}, ["True"], True),
            OptionConfigParams({"choice_with_entry_no_argument": 7}, [7], True),
            OptionConfigParams({"choice_with_entry_no_argument": False}, [False], True),
            OptionConfigParams({"choice_with_entry_no_argument": 14.0}, [14.0], True),
            # Having an empty string choice_with_entry make sense for selecting from a drop-down
            OptionConfigParams({"choice_with_entry_no_argument": ""}, [""], True),
            # Check 'off' special case here
            OptionConfigParams({"choice_with_entry_no_argument": "off"}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {"option": "choice_with_entry_empty_argument", "type": "choice_with_entry", "argument": ""},
        [
            OptionConfigParams({"choice_with_entry_empty_argument": "True"}, ["True"], True),
            OptionConfigParams({"choice_with_entry_empty_argument": 7}, [7], True),
            OptionConfigParams({"choice_with_entry_empty_argument": False}, [False], True),
            OptionConfigParams({"choice_with_entry_empty_argument": 14.0}, [14.0], True),
            # Having an empty string choice_with_entry make sense for selecting from a drop-down
            OptionConfigParams({"choice_with_entry_empty_argument": ""}, [""], True),
            # Check 'off' special case here
            OptionConfigParams({"choice_with_entry_empty_argument": "off"}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {"option": "choice_with_search_argument", "type": "choice_with_search", "argument": "choice-with-search"},
        [
            OptionConfigParams({"choice_with_search_argument": "True"}, ["choice-with-search", "True"], True),
            OptionConfigParams({"choice_with_search_argument": 7}, ["choice-with-search", 7], True),
            OptionConfigParams({"choice_with_search_argument": False}, ["choice-with-search", False], True),
            OptionConfigParams({"choice_with_search_argument": 14.0}, ["choice-with-search", 14.0], True),
            # Having an empty string choice_with_search make sense for selecting from a drop-down
            OptionConfigParams({"choice_with_search_argument": ""}, ["choice-with-search", ""], True),
            # Check 'off' special case here
            OptionConfigParams({"choice_with_search_argument": "off"}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {"option": "choice_with_search_no_argument", "type": "choice_with_search"},
        [
            OptionConfigParams({"choice_with_search_no_argument": "True"}, ["True"], True),
            OptionConfigParams({"choice_with_search_no_argument": 7}, [7], True),
            OptionConfigParams({"choice_with_search_no_argument": False}, [False], True),
            OptionConfigParams({"choice_with_search_no_argument": 14.0}, [14.0], True),
            # Having an empty string choice_with_search make sense for selecting from a drop-down
            OptionConfigParams({"choice_with_search_no_argument": ""}, [""], True),
            # Check 'off' special case here
            OptionConfigParams({"choice_with_search_no_argument": "off"}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
    OptionTestParams(
        {"option": "choice_with_search_empty_argument", "type": "choice_with_search", "argument": ""},
        [
            OptionConfigParams({"choice_with_search_empty_argument": "True"}, ["True"], True),
            OptionConfigParams({"choice_with_search_empty_argument": 7}, [7], True),
            OptionConfigParams({"choice_with_search_empty_argument": False}, [False], True),
            OptionConfigParams({"choice_with_search_empty_argument": 14.0}, [14.0], True),
            # Having an empty string choice_with_search make sense for selecting from a drop-down
            OptionConfigParams({"choice_with_search_empty_argument": ""}, [""], True),
            # Check 'off' special case here
            OptionConfigParams({"choice_with_search_empty_argument": "off"}, [], True),
            OptionConfigParams({}, [], True),
        ],
    ),
]


def generate_runner_dict_for_option_test(test_param: OptionTestParams) -> dict[str, Any]:
    test_dict = TEST_OPTION_TYPES_DICT_TEMPLATE.copy()
    test_dict["runner_options"] = [test_param.option_dict]
    return test_dict


class TestModelRunner(unittest.TestCase):
    def setUp(self):
        self.runner = ModelRunner()

    def test_create_model_runner(self):
        self.assertEqual(self.runner.entry_point_option, DEFAULT_ENTRY_POINT_OPTION)

    def test_init_from_dict(self):
        test_dict_with_array_platforms = TEST_RUNNER_DICT
        test_dict_with_dict_platforms = TEST_RUNNER_DICT.copy()
        test_dict_with_dict_platforms["platforms"] = {
            platform: platform for platform in TEST_RUNNER_DICT.get("platforms", [])
        }
        # The runner dict should be saved out with the "platforms" key pointing to a dict
        expected_dict = test_dict_with_dict_platforms

        # Test with the "platforms" key set to an array
        self.runner.from_dict(test_dict_with_array_platforms)
        output_dict = self.runner.to_dict()
        self.assertDictEqual(output_dict, expected_dict)

        # Test with the "platforms" key set to a dict
        self.runner.from_dict(test_dict_with_dict_platforms)
        output_dict = self.runner.to_dict()
        self.assertDictEqual(output_dict, expected_dict)

    # model.play test
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
            "command": self.runner.get_command() + ["--fullscreen", rom_name],
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

    @patch("lutris.runners.runner.Runner.get_executable")
    @patch("os.path.isfile")
    @patch("lutris.util.system.path_exists")
    def test_play_for_all_option_types(self, mock_path_exists, mock_isfile, mock_get_executable):
        for test_param in TEST_OPTION_TYPES_PARAMS:
            test_dict = generate_runner_dict_for_option_test(test_param)
            option_name = test_param.option_dict["option"]
            for runner_config, expected_commang_args, _ in test_param.option_configs:
                with self.subTest(
                    f"Testing play for option {option_name}", option=option_name, runner_config=runner_config
                ):
                    rom_name = "good_game"
                    mock_path_exists.return_value = True
                    mock_isfile.return_value = True
                    mock_config = MagicMock()
                    mock_config.game_config = {"rom": rom_name}
                    mock_config.runner_config = runner_config

                    mock_get_executable.return_value = "/path/to/model-runner"

                    self.runner.from_dict(test_dict)
                    self.runner.config = mock_config
                    expected = {
                        "command": self.runner.get_command() + expected_commang_args + ["good_game"],
                        "env": {"SDL_VIDEODRIVER": "x11"},
                        "working_dir": "/path/to",
                    }
                    play_dict = self.runner.play()
                    self.assertDictEqual(play_dict, expected)

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

    def test_get_platform_succeeds_if_platforms_key_is_dict(self):
        mock_config = MagicMock()
        mock_config.game_config = {"platform": "Pocket Challenge V2"}

        valid_runner_dict = deepcopy(TEST_RUNNER_DICT)
        valid_runner_dict["platforms"] = {
            "Bandai WonderSwan Color": "WonderSwan Color",
            "Benesse Pocket Challenge V2": "Pocket Challenge V2",
        }
        self.runner.from_dict(valid_runner_dict)
        self.runner.config = mock_config
        self.assertEqual(self.runner.get_platform(), "Benesse Pocket Challenge V2")
