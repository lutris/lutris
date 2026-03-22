"""Base class and utilities for JSON based runners"""

import shlex
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from lutris.exceptions import MissingGameExecutableError
from lutris.runners.runner import Runner
from lutris.util import system

FILE_BASED_ENTRY_POINTS = set(["exe", "main_file", "iso", "rom", "disk-a", "path", "files"])
DEFAULT_ENTRY_POINT_OPTION = "main_file"

AppendFunction = Callable[[List[str], Any, Dict[str, Any]], None]


def _append_args_string(arguments: List[str], option_dict: Any, config: Dict[str, Any]):
    option_key = option_dict.get("option")
    if option_value := config.get(option_key):
        option_arg = option_dict.get("argument")
        if isinstance(option_arg, str) and len(option_arg) > 0:
            arguments.append(option_arg)
        arguments.append(option_value)


def _append_args_bool(arguments: List[str], option_dict: Any, config: Dict[str, Any]):
    option_key = option_dict.get("option")
    value = config.get(option_key)
    option_arg = option_dict.get("argument")
    if value and isinstance(option_arg, str) and len(option_arg) > 0:
        arguments.append(option_arg)


def _append_args_choice(arguments: List[str], option_dict: Any, config: Dict[str, Any]):
    option_key = option_dict.get("option")
    value = config.get(option_key)
    if isinstance(value, str) and value == "off":
        return
    if value is not None:
        option_arg = option_dict.get("argument")
        if isinstance(option_arg, str) and len(option_arg) > 0:
            arguments.append(option_arg)
        arguments.append(value)


def _append_args_multi_string(arguments: List[str], option_dict: Any, config: Dict[str, Any]):
    option_key = option_dict.get("option")
    if option_values := shlex.split(str(config.get(option_key))):
        option_arg = option_dict.get("argument")
        if isinstance(option_arg, str) and len(option_arg) > 0:
            arguments.append(option_arg)
        arguments.extend(option_values)


def _append_args_mapping(arguments: List[str], option_dict: Any, config: Dict[str, Any]):
    option_key = option_dict.get("option")
    option_arg = option_dict.get("argument")
    option_value = config.get(option_key)
    if not isinstance(option_value, dict):
        return
    for name, value in option_value.items():
        if isinstance(option_arg, str) and len(option_arg) > 0:
            arguments.append(option_arg)
        arguments.append(f"{name}={value}")


_argument_append_funcs: Dict[str, AppendFunction] = {
    # adds arguments from the supplied option dictionary to the arguments list
    "label": lambda _1, _2, _3: None,
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
        dict_platforms = dict_data.get("platforms", {})
        # Support existing platforms that were are list
        if isinstance(dict_platforms, dict):
            self.platform_dict = dict_platforms
        else:
            self.platforms = dict_platforms
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

    @property
    def file_path(self) -> Optional[Path]:
        """Override to specify file path to the runner definition if applicable"""
        return None
