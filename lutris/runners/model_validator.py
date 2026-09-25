"""Base class and utilities for JSON based runners"""

from enum import Enum
from gettext import gettext as _
from typing import Any

from lutris.runners.model import DEFAULT_ENTRY_POINT_OPTION

REQUIRED_OPTION_KEYS = {"option", "type", "label"}
CHOICE_TYPES = {"choice", "choice_with_entry", "choice_with_search"}
RANGE_TYPE_REQUIRED_KEYS = {"min", "max"}


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
        self.runner_messages: list[RunnerDefinitionMessage] = []

    def get_all(self) -> list[RunnerDefinitionMessage]:
        return self.runner_messages

    def get_errors(self) -> list[RunnerDefinitionMessage]:
        return list(filter(lambda msg: msg.category == RunnerDefinitionCategory.ERROR, self.runner_messages))

    def get_warnings(self) -> list[RunnerDefinitionMessage]:
        return list(filter(lambda msg: msg.category == RunnerDefinitionCategory.WARNING, self.runner_messages))

    def has_errors(self) -> bool:
        for runner_message in self.runner_messages:
            if runner_message.category == RunnerDefinitionCategory.ERROR:
                return True
        return False


def validate_runner_name(runner_name: str) -> RunnerDefinitionMessages:
    """Validate the runner name only contains alphanumeric characters and underscore
    [0-9A-Za-z\\-]
    """
    error_list = RunnerDefinitionMessages()
    if runner_name == "":
        error_list.runner_messages.append(
            RunnerDefinitionMessage(key_path="name", message=_("Runner name cannot be empty"))
        )
    else:
        for c in runner_name:
            if not (c.isalnum() and c.islower()) and c != "-":
                error_list.runner_messages.append(
                    RunnerDefinitionMessage(
                        key_path="name",
                        message=_(
                            "Runner name '%s' contains invalid character '%s'.\nIt must be alphanumeric lower case"
                        )
                        % (runner_name, c),
                    )
                )
                break
    return error_list


def validate(data_dict: dict[str, Any]) -> RunnerDefinitionMessages:
    """Verifies the dictionary contains the required fields to use as a valid Runner"""

    error_list = RunnerDefinitionMessages()

    error_list.runner_messages.extend(validate_runner_name_from_dict(data_dict).runner_messages)
    error_list.runner_messages.extend(validate_human_name(data_dict).runner_messages)
    error_list.runner_messages.extend(validate_description(data_dict).runner_messages)
    error_list.runner_messages.extend(validate_platforms(data_dict).runner_messages)
    error_list.runner_messages.extend(validate_runner_executable(data_dict).runner_messages)
    error_list.runner_messages.extend(validate_runnable_alone(data_dict).runner_messages)
    error_list.runner_messages.extend(validate_flatpak_id(data_dict).runner_messages)
    error_list.runner_messages.extend(validate_download_url(data_dict).runner_messages)
    error_list.runner_messages.extend(validate_entry_point_option(data_dict).runner_messages)
    error_list.runner_messages.extend(validate_game_options(data_dict).runner_messages)
    error_list.runner_messages.extend(validate_runner_options(data_dict).runner_messages)
    error_list.runner_messages.extend(validate_system_options_override(data_dict).runner_messages)
    error_list.runner_messages.extend(validate_envs(data_dict).runner_messages)
    error_list.runner_messages.extend(validate_working_dir(data_dict).runner_messages)

    return error_list


def _validate_string_non_empty(data_dict: dict[str, Any], key: str) -> RunnerDefinitionMessages:
    """Verify key exist and is non empty.
    i.e The key is required
    """
    error_list = RunnerDefinitionMessages()
    if key not in data_dict:
        error_list.runner_messages.append(
            RunnerDefinitionMessage(key_path=key, message=_("Field `%s` must exist") % key)
        )
    else:
        try:
            str_value = str(data_dict[key])
            if str_value == "":
                error_list.runner_messages.append(
                    RunnerDefinitionMessage(key_path=key, message=_("Field `%s` must be non-empty") % key)
                )
        except Exception as ex:
            error_list.runner_messages.append(
                RunnerDefinitionMessage(
                    key_path=key, message=_("Error `%s` not convertible to string: %s") % (key, str(ex))
                )
            )

    return error_list


def _validate_string_non_empty_if_exist(data_dict: dict[str, Any], key: str) -> RunnerDefinitionMessages:
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
                    message=_("Field `%s` must be non-empty") % key,
                    category=RunnerDefinitionCategory.WARNING,
                )
            )
    except Exception as ex:
        error_list.runner_messages.append(
            RunnerDefinitionMessage(
                key_path=key,
                message=_("Error `%s` not convertible to string: %s") % (key, str(ex)),
                category=RunnerDefinitionCategory.WARNING,
            )
        )
    return error_list


def _validate_bool_if_exist(data_dict: dict[str, Any], key: str) -> RunnerDefinitionMessages:
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
                message=_("Error `%s` not convertible to bool: %s") % (str(key), str(ex)),
                category=RunnerDefinitionCategory.WARNING,
            )
        )
    return error_list


def validate_runner_name_from_dict(data_dict: dict[str, Any]) -> RunnerDefinitionMessages:
    """Verifies runner  name is valid"""
    error_list = _validate_string_non_empty(data_dict, "name")
    if not error_list.get_errors():
        error_list.runner_messages.extend(validate_runner_name(data_dict["name"]).runner_messages)
    return error_list


def validate_human_name(data_dict: dict[str, Any]) -> RunnerDefinitionMessages:
    """Verifies runner human name is valid"""
    return _validate_string_non_empty(data_dict, "human_name")


def validate_description(data_dict: dict[str, Any]) -> RunnerDefinitionMessages:
    """Verifies runner description is valid"""
    return _validate_string_non_empty_if_exist(data_dict, "description")


def validate_platforms(data_dict: dict[str, Any]) -> RunnerDefinitionMessages:
    """Verifies runner platform list is valid"""
    error_list = RunnerDefinitionMessages()

    key = "platforms"
    if key not in data_dict:
        error_list.runner_messages.append(
            RunnerDefinitionMessage(key_path=key, message=_("Field `%s` must exist") % key)
        )
    else:
        platforms = data_dict[key]
        if isinstance(platforms, dict):
            if len(platforms) == 0:
                error_list.runner_messages.append(
                    RunnerDefinitionMessage(
                        key_path=key, message=_("`%s` dict must contain at least one string element") % key
                    )
                )
            else:
                for index, platform_name in enumerate(platforms.values()):
                    if platform_name == "":
                        key_prefix = f"{key}.{index}"
                        error_list.runner_messages.append(
                            RunnerDefinitionMessage(
                                key_path=key, message=_("`%s` dict string entry cannot be empty") % key_prefix
                            )
                        )
        elif isinstance(platforms, list):
            if len(platforms) == 0:
                error_list.runner_messages.append(
                    RunnerDefinitionMessage(
                        key_path=key, message=_("`%s` list must contain at least one string element") % key
                    )
                )
            else:
                for index, platform_name in enumerate(platforms):
                    if platform_name == "":
                        key_prefix = f"{key}.{index}"
                        error_list.runner_messages.append(
                            RunnerDefinitionMessage(
                                key_path=key, message=_("`%s` list string entry cannot be empty") % key_prefix
                            )
                        )
        elif isinstance(platforms, str):
            platform_name = platforms
            if platform_name == "":
                error_list.runner_messages.append(
                    RunnerDefinitionMessage(key_path=key, message=_("`%s` string field cannot be empty") % key)
                )
    return error_list


def validate_runner_executable(data_dict: dict[str, Any]) -> RunnerDefinitionMessages:
    """Verifies runner executable is valid"""
    return _validate_string_non_empty(data_dict, "runner_executable")


def validate_runnable_alone(data_dict: dict[str, Any]) -> RunnerDefinitionMessages:
    """Verifies runnable alone option is is valid"""
    return _validate_bool_if_exist(data_dict, "runnable_alone")


def validate_download_url(data_dict: dict[str, Any]) -> RunnerDefinitionMessages:
    """Verifies the download url is valid"""
    return _validate_string_non_empty_if_exist(data_dict, "download_url")


def validate_flatpak_id(data_dict: dict[str, Any]) -> RunnerDefinitionMessages:
    """Verifies the download url is valid"""
    return _validate_string_non_empty_if_exist(data_dict, "flatpak_id")


def validate_entry_point_option(data_dict: dict[str, Any]) -> RunnerDefinitionMessages:
    """Verifies the entry_point_option is valid"""
    return _validate_string_non_empty_if_exist(data_dict, "entry_point_option")


def _validate_option(option_dict: dict[str, Any], key_prefix="") -> RunnerDefinitionMessages:
    error_list = RunnerDefinitionMessages()

    error_list.runner_messages.extend(
        [
            RunnerDefinitionMessage(
                key_path=f"{key_prefix}{'.' if key_prefix else ''}{key}",
                message=_("Option is missing required key '%s'") % key,
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
                        "'choices' key is required for widget type %s with a least one element."
                        ' Ex. `"choices": [ {"option1": "value1"}, {"option2": "value2"} ]`'
                    )
                    % widget_type,
                )
            )

    if widget_type == "range":
        error_list.runner_messages.extend(
            [
                RunnerDefinitionMessage(
                    key_path=f"{key_prefix}{'.' if key_prefix else ''}{key}",
                    message=_("'%s' key is required for widget type '%s'") % (key, widget_type),
                )
                for key in RANGE_TYPE_REQUIRED_KEYS
                if key not in option_dict
            ]
        )

    return error_list


def _validate_options(option_list: list[dict[str, Any]], prefix="") -> RunnerDefinitionMessages:
    error_list = RunnerDefinitionMessages()
    for index, option in enumerate(option_list):
        error_list.runner_messages.extend(
            _validate_option(option, key_prefix=f"{prefix}{'.' if prefix else ''}{index}").runner_messages
        )
    return error_list


def validate_game_options(data_dict: dict[str, Any]) -> RunnerDefinitionMessages:
    """Verifies game option field is list and contains at least one entry
    The entry point option must exist as option in order to allow the user to specify the game
    """
    error_list = RunnerDefinitionMessages()

    key = "game_options"
    if key not in data_dict:
        error_list.runner_messages.append(
            RunnerDefinitionMessage(key_path=key, message=_("Field `%s` must exist") % key)
        )
    else:
        game_options = data_dict[key]
        # Need the entry point to verify the game_options field contains an option for it
        entry_point_option = data_dict.get("entry_point_option", DEFAULT_ENTRY_POINT_OPTION)
        if not isinstance(game_options, list):
            error_list.runner_messages.append(
                RunnerDefinitionMessage(key_path=key, message=_("`%s` must be a list") % key)
            )
        elif len(game_options) == 0:
            error_list.runner_messages.append(
                RunnerDefinitionMessage(key_path=key, message=_("`%s` list must contain at least one element") % key)
            )
        elif len([option for option in game_options if option.get("option", "") == entry_point_option]) != 1:
            error_list.runner_messages.append(
                RunnerDefinitionMessage(
                    key_path=key,
                    message=_("`%s` require exactly one 'option' for the entry point field: %s")
                    % (key, entry_point_option),
                )
            )
        else:
            error_list.runner_messages.extend(_validate_options(game_options, prefix=key).runner_messages)

    return error_list


def validate_runner_options(data_dict: dict[str, Any]) -> RunnerDefinitionMessages:
    error_list = RunnerDefinitionMessages()

    key = "runner_options"
    if key not in data_dict:
        return error_list

    runner_options = data_dict[key]
    if not isinstance(runner_options, list):
        error_list.runner_messages.append(RunnerDefinitionMessage(key_path=key, message=_("`%s` must be a list") % key))
    else:
        error_list.runner_messages.extend(_validate_options(runner_options, prefix=key).runner_messages)

    return error_list


def validate_system_options_override(data_dict: dict[str, Any]) -> RunnerDefinitionMessages:
    error_list = RunnerDefinitionMessages()

    key = "system_options_override"
    if key not in data_dict:
        return error_list

    system_options_override = data_dict[key]
    if not isinstance(system_options_override, list):
        error_list.runner_messages.append(
            RunnerDefinitionMessage(
                key_path=key, message=_("`%s` must be a list") % key, category=RunnerDefinitionCategory.WARNING
            )
        )
    else:
        for index, option_override in enumerate(system_options_override):
            if "option" not in option_override:
                error_list.runner_messages.append(
                    RunnerDefinitionMessage(
                        key_path=key,
                        message=_("`%s` element:%d must contain an 'option' in order to override system option")
                        % (key, index),
                        category=RunnerDefinitionCategory.WARNING,
                    )
                )
    return error_list


def validate_envs(data_dict: dict[str, Any]) -> RunnerDefinitionMessages:
    """Verifies environment variable dict is valid if it exist"""
    error_list = RunnerDefinitionMessages()

    key = "env"
    if key not in data_dict:
        return error_list

    env_dict = data_dict[key]
    if not isinstance(env_dict, dict):
        error_list.runner_messages.append(
            RunnerDefinitionMessage(
                key_path=key, message=_("`%s` must be a dictionary") % key, category=RunnerDefinitionCategory.WARNING
            )
        )
    return error_list


def validate_working_dir(data_dict: dict[str, Any]) -> RunnerDefinitionMessages:
    """Verifies working directory is valid if it exist"""
    return _validate_string_non_empty_if_exist(data_dict, "working_dir")
