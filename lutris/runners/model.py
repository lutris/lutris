"""Base class and utilities for JSON based runners"""

import shlex
from enum import Enum
from gettext import gettext as _
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from lutris.exceptions import MissingGameExecutableError
from lutris.runners.runner import Runner
from lutris.util import system

FILE_BASED_ENTRY_POINTS = set(["exe", "main_file", "iso", "rom", "disk-a", "path", "files"])
DEFAULT_ENTRY_POINT_OPTION = "main_file"

OPTION_KEYS = {
    "option",
    "type",
    "section",
    "label",
    "argument",
    "help",
    "default",
    "advanced",
    "choices",
    "min",
    "max",
    "visible",
    "default_path",
    "conditional_on",
    "warn_if_non_writable_parent",
}

REQUIRED_OPTION_KEYS = {"option", "type", "label"}

CHOICE_TYPES = {"choice", "choice_with_entry", "choice_with_search"}
RANGE_TYPE_REQUIRED_KEYS = {"min", "max"}

AppendFunction = Callable[[List[str], Any, Dict[str, Any]], None]


def _append_args_string(arguments: List[str], option_dict: Any, config: Dict[str, Any]):
    option_key = option_dict.get("option")
    if option_value := config.get(option_key):
        if option_arg := option_dict.get("argument"):
            arguments.append(option_arg)
        arguments.append(option_value)


def _append_args_bool(arguments: List[str], option_dict: Any, config: Dict[str, Any]):
    option_key = option_dict.get("option")
    value = config.get(option_key)
    option_arg = option_dict.get("argument")
    if value and isinstance(option_arg, str):
        arguments.append(option_arg)


def _append_args_choice(arguments: List[str], option_dict: Any, config: Dict[str, Any]):
    option_key = option_dict.get("option")
    value = config.get(option_key)
    if value is not None:
        option_arg = option_dict.get("argument")
        if isinstance(option_arg, str):
            arguments.append(option_arg)
        arguments.append(value)


def _append_args_multi_string(arguments: List[str], option_dict: Any, config: Dict[str, Any]):
    option_key = option_dict.get("option")
    if option_arg := option_dict.get("argument"):
        arguments.append(option_arg)
    arguments.extend(shlex.split(str(config.get(option_key))))


def _append_args_mapping(arguments: List[str], option_dict: Any, config: Dict[str, Any]):
    option_key = option_dict.get("option")
    option_arg = option_dict.get("argument")
    option_value = config.get(option_key)
    if not isinstance(option_value, dict):
        return
    for name, value in option_value.items():
        if option_arg:
            arguments.append(option_arg)
        arguments.append(f"{name}={value}")


_argument_append_funcs: Dict[str, AppendFunction] = {
    # adds arguments from the supplied option dictionary to the arguments list
    "label": lambda _, _1, _2: None,
    "string": _append_args_string,
    "bool": _append_args_bool,
    "range": _append_args_string,
    "choice": _append_args_choice,
    "choice_with_entry": _append_args_choice,
    "choice_with_search": _append_args_choice,
    "file": _append_args_string,
    "multiple_file": _append_args_multi_string,
    "directory": _append_args_string,
    "mapping": _append_args_mapping,
    "command_line": _append_args_multi_string,
}


def append_args(
    arguments: List[str],
    options_dict_list: List[Dict[str, Any]],
    config: Dict[str, Any],
):
    for option_dict in options_dict_list:
        option_key = option_dict.get("option")
        if option_key not in config:
            continue

        option_type = option_dict.get("type")
        if append_func := _argument_append_funcs.get(str(option_type)):
            append_func(arguments, option_dict, config)
        else:
            raise RuntimeError(f"Unhandled option type {option_dict.get('type')}")


class RunnerDefinitionCategory(str, Enum):
    WARNING = "warning"
    ERROR = "error"


class RunnerDefinitionMessage:
    def __init__(self, key_path, message, category=RunnerDefinitionCategory.ERROR) -> None:
        self.key_path: str = key_path
        self.message: str = message
        self.category = category


class RunnerDefinitionMessages:
    def __init__(
        self,
    ) -> None:
        self.runner_messages: List[RunnerDefinitionMessage] = []

    def get_all(self) -> List[RunnerDefinitionMessage]:
        return self.runner_messages

    def get_errors(self):
        return filter(lambda msg: msg.category == RunnerDefinitionCategory.ERROR, self.runner_messages)

    def get_warnings(self):
        return filter(lambda msg: msg.category == RunnerDefinitionCategory.WARNING, self.runner_messages)

    def has_errors(self) -> bool:
        for runner_message in self.runner_messages:
            if runner_message.category == RunnerDefinitionCategory.ERROR:
                return True
        return False

    def __len__(self):
        return len(self.runner_messages)


class ModelRunner(Runner):
    def __init__(self, dict_data: Optional[Dict[str, Any]] = None, config=None):
        super().__init__(config)
        if dict_data:
            self.from_dict(dict_data)

    def from_dict(self, dict_data: Dict[str, Any]):
        self.game_options = dict_data.get("game_options", [])
        self.runner_options = dict_data.get("runner_options", [])
        self.human_name = dict_data.get("human_name", "")
        self.description = dict_data.get("description", "")
        self.platforms = dict_data.get("platforms", [])
        self.runner_executable = dict_data.get("runner_executable", "")
        self.system_options_override = dict_data.get("system_options_override", [])
        self.entry_point_option = dict_data.get("entry_point_option", DEFAULT_ENTRY_POINT_OPTION)
        self.download_url = dict_data.get("download_url", "")
        self.runnable_alone = dict_data.get("runnable_alone", True)
        self.flatpak_id = dict_data.get("flatpak_id", "")
        self.env = dict_data.get("env", {})
        self.launch_working_dir = dict_data.get("working_dir", "")

    def to_dict(self) -> Dict[str, Any]:
        output_dict_data: Dict[str, Any] = {}
        output_dict_data["human_name"] = self.human_name
        output_dict_data["description"] = self.description
        output_dict_data["platforms"] = self.platforms
        output_dict_data["runner_executable"] = self.runner_executable
        output_dict_data["runnable_alone"] = self.runnable_alone
        output_dict_data["flatpak_id"] = self.flatpak_id
        output_dict_data["download_url"] = self.download_url
        output_dict_data["entry_point_option"] = self.entry_point_option
        output_dict_data["game_options"] = self.game_options
        output_dict_data["runner_options"] = self.runner_options
        output_dict_data["system_options_override"] = self.system_options_override
        output_dict_data["env"] = self.env
        output_dict_data["working_dir"] = self.launch_working_dir

        return output_dict_data

    def get_platform(self):
        """Queries the platform from either a list, dict or str"""
        selected_platform = self.game_config.get("platform")
        if isinstance(self.platforms, dict):
            if selected_platform in self.platforms:
                return self.platforms[selected_platform]
        elif isinstance(self.platforms, list):
            if selected_platform in self.platforms:
                return selected_platform
            elif self.platforms:
                return self.platforms[0]
        elif isinstance(self.platforms, str):
            return self.platforms
        return ""

    def play(self) -> dict[str, Any]:
        """Runs the game"""
        entry_point_value = self.game_config.get(self.entry_point_option, "")
        if self.entry_point_option in FILE_BASED_ENTRY_POINTS and not system.path_exists(entry_point_value):
            raise MissingGameExecutableError(filename=entry_point_value)

        arguments = self.get_command()

        # Append the runner arguments first, and game arguments afterwards
        append_args(arguments, self.runner_options, self.runner_config)
        append_args(arguments, self.game_options, self.game_config)

        result: dict[str, Any] = {"command": arguments}
        if self.env:
            result["env"] = self.env
        if self.launch_working_dir == "runner":
            result["working_dir"] = str(Path(self.get_executable()).parent)
        return result

    @staticmethod
    def validate(data_dict: Dict[str, Any]) -> RunnerDefinitionMessages:
        """Verifies the dictionary contains the required fields to use as a valid Runner"""

        error_list = RunnerDefinitionMessages()

        error_list.runner_messages.extend(ModelRunner.validate_human_name(data_dict).runner_messages)
        error_list.runner_messages.extend(ModelRunner.validate_description(data_dict).runner_messages)
        error_list.runner_messages.extend(ModelRunner.validate_platforms(data_dict).runner_messages)
        error_list.runner_messages.extend(ModelRunner.validate_runner_executable(data_dict).runner_messages)
        error_list.runner_messages.extend(ModelRunner.validate_runnable_alone(data_dict).runner_messages)
        error_list.runner_messages.extend(ModelRunner.validate_flakpak_id(data_dict).runner_messages)
        error_list.runner_messages.extend(ModelRunner.validate_download_url(data_dict).runner_messages)
        error_list.runner_messages.extend(ModelRunner.validate_entry_point_option(data_dict).runner_messages)
        error_list.runner_messages.extend(ModelRunner.validate_game_options(data_dict).runner_messages)
        error_list.runner_messages.extend(ModelRunner.validate_runner_options(data_dict).runner_messages)
        error_list.runner_messages.extend(ModelRunner.validate_system_options_override(data_dict).runner_messages)
        error_list.runner_messages.extend(ModelRunner.validate_envs(data_dict).runner_messages)
        error_list.runner_messages.extend(ModelRunner.validate_working_dir(data_dict).runner_messages)

        return error_list

    @staticmethod
    def _validate_string_non_empty(data_dict: Dict[str, Any], key: str) -> RunnerDefinitionMessages:
        """Verify key exist and is non empty.
        i.e The key is required
        """
        error_list = RunnerDefinitionMessages()
        if key not in data_dict:
            error_list.runner_messages.append(
                RunnerDefinitionMessage(key_path=key, message=_(f"Field `{key}` must exist"))
            )
        else:
            try:
                str_value = str(data_dict[key])
                if str_value == "":
                    error_list.runner_messages.append(
                        RunnerDefinitionMessage(key_path=key, message=_(f"Field `{key}` must be non-empty"))
                    )
            except Exception as ex:
                error_list.runner_messages.append(
                    RunnerDefinitionMessage(key_path=key, message=_(f"Error `{key}` not convertible to string: {ex}"))
                )

        return error_list

    @staticmethod
    def _validate_string_non_empty_if_exist(data_dict: Dict[str, Any], key: str) -> RunnerDefinitionMessages:
        """Verify key is non empty if it exist.
        i.e The key is optional
        """
        error_list = RunnerDefinitionMessages()
        if key not in data_dict:
            return error_list

        try:
            str_value = str(data_dict[key])
            if str_value == "":
                error_list.runner_messages.append(
                    RunnerDefinitionMessage(
                        key_path=key,
                        message=_(f"Field `{key}` must be non-empty"),
                        category=RunnerDefinitionCategory.WARNING,
                    )
                )
        except Exception as ex:
            error_list.runner_messages.append(
                RunnerDefinitionMessage(
                    key_path=key,
                    message=_(f"Error `{key}` not convertible to string: {ex}"),
                    category=RunnerDefinitionCategory.WARNING,
                )
            )
        return error_list

    @staticmethod
    def _validate_bool_if_exist(data_dict: Dict[str, Any], key: str) -> RunnerDefinitionMessages:
        """Verify key is convertible to boolean if it exist."""
        error_list = RunnerDefinitionMessages()
        if key not in data_dict:
            return error_list
        try:
            bool(data_dict[key])
        except Exception as ex:
            error_list.runner_messages.append(
                RunnerDefinitionMessage(
                    key_path=key,
                    message=_(f"Error `{key}` not convertible to bool: {ex}"),
                    category=RunnerDefinitionCategory.WARNING,
                )
            )
        return error_list

    @staticmethod
    def validate_human_name(data_dict: Dict[str, Any]) -> RunnerDefinitionMessages:
        """Verifies runner human name is valid"""
        return ModelRunner._validate_string_non_empty(data_dict, "human_name")

    @staticmethod
    def validate_description(data_dict: Dict[str, Any]) -> RunnerDefinitionMessages:
        """Verifies runner description is valid"""
        return ModelRunner._validate_string_non_empty_if_exist(data_dict, "description")

    @staticmethod
    def validate_platforms(data_dict: Dict[str, Any]) -> RunnerDefinitionMessages:
        """Verifies runner platform list is valid"""
        error_list = RunnerDefinitionMessages()

        key = "platforms"
        if key not in data_dict:
            error_list.runner_messages.append(
                RunnerDefinitionMessage(key_path=key, message=_(f"Field `{key}` must exist"))
            )
        else:
            platforms = data_dict[key]
            if isinstance(platforms, dict):
                if len(platforms) == 0:
                    error_list.runner_messages.append(
                        RunnerDefinitionMessage(
                            key_path=key, message=_(f"`{key}` dict must contain at least one string element")
                        )
                    )
                else:
                    platform_name = next(iter(platforms.values()))  # get first value field in platforms dict
                    if platform_name == "":
                        error_list.runner_messages.append(
                            RunnerDefinitionMessage(
                                key_path=key, message=_(f"`{key}` dict string entry cannot be empty")
                            )
                        )
            elif isinstance(platforms, list):
                if len(platforms) == 0:
                    error_list.runner_messages.append(
                        RunnerDefinitionMessage(
                            key_path=key, message=_(f"`{key}` list must contain at least one string element")
                        )
                    )
                else:
                    platform_name = platforms[0]
                    if platform_name == "":
                        error_list.runner_messages.append(
                            RunnerDefinitionMessage(
                                key_path=key, message=_(f"`{key}` list string entry cannot be empty")
                            )
                        )
            elif isinstance(platforms, str):
                platform_name = platforms
                if platform_name == "":
                    error_list.runner_messages.append(
                        RunnerDefinitionMessage(key_path=key, message=_(f"`{key}` string field cannot be empty"))
                    )
        return error_list

    @staticmethod
    def validate_runner_executable(data_dict: Dict[str, Any]) -> RunnerDefinitionMessages:
        """Verifies runner executable is valid"""
        return ModelRunner._validate_string_non_empty(data_dict, "runner_executable")

    @staticmethod
    def validate_runnable_alone(data_dict: Dict[str, Any]) -> RunnerDefinitionMessages:
        """Verifies runnable alone option is is valid"""
        return ModelRunner._validate_bool_if_exist(data_dict, "runnable_alone")

    @staticmethod
    def validate_download_url(data_dict: Dict[str, Any]) -> RunnerDefinitionMessages:
        """Verifies the download url is valid"""
        return ModelRunner._validate_string_non_empty_if_exist(data_dict, "download_url")

    @staticmethod
    def validate_flakpak_id(data_dict: Dict[str, Any]) -> RunnerDefinitionMessages:
        """Verifies the download url is valid"""
        return ModelRunner._validate_string_non_empty_if_exist(data_dict, "flatpak_id")

    @staticmethod
    def validate_entry_point_option(data_dict: Dict[str, Any]) -> RunnerDefinitionMessages:
        """Verifies the entry_point_option is valid"""
        return ModelRunner._validate_string_non_empty_if_exist(data_dict, "entry_point_option")

    @staticmethod
    def _validate_option(option_dict: Dict[str, Any], key_prefix="") -> RunnerDefinitionMessages:
        error_list = RunnerDefinitionMessages()

        error_list.runner_messages.extend(
            [
                RunnerDefinitionMessage(
                    key_path=f"{key_prefix}{'.' if key_prefix else ''}{key}",
                    message=_(f"Option is missing required key '{key}'"),
                )
                for key in REQUIRED_OPTION_KEYS
                if key not in option_dict
            ]
        )
        widget_type = option_dict.get("type", "")
        if widget_type in CHOICE_TYPES:
            if not option_dict.get("choices", []):
                key = "choices"
                error_list.runner_messages.append(
                    RunnerDefinitionMessage(
                        key_path=f"{key_prefix}{'.' if key_prefix else ''}{key}",
                        message=_(
                            f"'choices' key is required for widget type {widget_type} with a least one element."
                            ' Ex. `"choices": [ {"option1": "value1"}, {"option2": "value2"} ]`'
                        ),
                    )
                )

        if widget_type == "range":
            error_list.runner_messages.extend(
                [
                    RunnerDefinitionMessage(
                        key_path=f"{key_prefix}{'.' if key_prefix else ''}{key}",
                        message=_(f"'{key}' key is required for widget type '{widget_type}'"),
                    )
                    for key in RANGE_TYPE_REQUIRED_KEYS
                    if key not in option_dict
                ]
            )

        return error_list

    @staticmethod
    def _validate_options(option_list: List[Dict[str, Any]], prefix="") -> RunnerDefinitionMessages:
        error_list = RunnerDefinitionMessages()
        for index, option in enumerate(option_list):
            error_list.runner_messages.extend(
                ModelRunner._validate_option(
                    option, key_prefix=f"{prefix}{'.' if prefix else ''}{index}"
                ).runner_messages
            )
        return error_list

    @staticmethod
    def validate_game_options(data_dict: Dict[str, Any]) -> RunnerDefinitionMessages:
        """Verifies game option field is list and contains at least one entry
        The entry point option must exist as option in order to allow the user to specify the game
        """
        error_list = RunnerDefinitionMessages()

        key = "game_options"
        if key not in data_dict:
            error_list.runner_messages.append(
                RunnerDefinitionMessage(key_path=key, message=_(f"Field `{key}` must exist"))
            )
        else:
            game_options = data_dict[key]
            # Need the entry point to verify the game_options field contains an option for it
            entry_point_option = data_dict.get("entry_point_option", DEFAULT_ENTRY_POINT_OPTION)
            if not isinstance(game_options, list):
                error_list.runner_messages.append(
                    RunnerDefinitionMessage(key_path=key, message=_(f"`{key}` must be a list"))
                )
            elif len(game_options) == 0:
                error_list.runner_messages.append(
                    RunnerDefinitionMessage(key_path=key, message=_(f"`{key}` list must contain at least one element"))
                )
            elif len([option for option in game_options if option.get("option", "") == entry_point_option]) != 1:
                error_list.runner_messages.append(
                    RunnerDefinitionMessage(
                        key_path=key,
                        message=_(
                            f"`{key}` require exactly one 'option' for the entry point field: {entry_point_option}"
                        ),
                    )
                )
            else:
                error_list.runner_messages.extend(
                    ModelRunner._validate_options(game_options, prefix=key).runner_messages
                )

        return error_list

    @staticmethod
    def validate_runner_options(data_dict: Dict[str, Any]) -> RunnerDefinitionMessages:
        error_list = RunnerDefinitionMessages()

        key = "runner_options"
        if key not in data_dict:
            return error_list

        runner_options = data_dict[key]
        if not isinstance(runner_options, list):
            error_list.runner_messages.append(
                RunnerDefinitionMessage(key_path=key, message=_(f"`{key}` must be a list"))
            )
        else:
            error_list.runner_messages.extend(ModelRunner._validate_options(runner_options, prefix=key).runner_messages)

        return error_list

    @staticmethod
    def validate_system_options_override(data_dict: Dict[str, Any]) -> RunnerDefinitionMessages:
        error_list = RunnerDefinitionMessages()

        key = "system_options_override"
        if key not in data_dict:
            return error_list

        system_options_override = data_dict[key]
        if not isinstance(system_options_override, list):
            error_list.runner_messages.append(
                RunnerDefinitionMessage(
                    key_path=key, message=_(f"`{key}` must be a list"), category=RunnerDefinitionCategory.WARNING
                )
            )
        else:
            for index, option_override in enumerate(system_options_override):
                if "option" not in option_override:
                    error_list.runner_messages.append(
                        RunnerDefinitionMessage(
                            key_path=key,
                            message=_(
                                f"`{key}` element:{index} must contain an 'option' in order to override system option"
                            ),
                            category=RunnerDefinitionCategory.WARNING,
                        )
                    )
        return error_list

    @staticmethod
    def validate_envs(data_dict: Dict[str, Any]) -> RunnerDefinitionMessages:
        """Verifies environment variable dict is valid if it exist"""
        error_list = RunnerDefinitionMessages()

        key = "env"
        if key not in data_dict:
            return error_list

        env_dict = data_dict[key]
        if not isinstance(env_dict, dict):
            error_list.runner_messages.append(
                RunnerDefinitionMessage(
                    key_path=key, message=_(f"`{key}` must be a dictionary"), category=RunnerDefinitionCategory.WARNING
                )
            )
        return error_list

    @staticmethod
    def validate_working_dir(data_dict: Dict[str, Any]) -> RunnerDefinitionMessages:
        """Verifies working directory i is valid if it exist"""
        error_list = RunnerDefinitionMessages()

        key = "working_dir"
        if key not in data_dict:
            return error_list

        try:
            _ = str(data_dict[key])
        except Exception as ex:
            error_list.runner_messages.append(
                RunnerDefinitionMessage(
                    key_path=key,
                    message=_(f"Error `{key}` not convertible to string: {ex}"),
                    category=RunnerDefinitionCategory.WARNING,
                )
            )
        return error_list

    @property
    def file_path(self) -> Optional[Path]:
        """Override to specify file path to the runner definition if applicable"""
        return None
