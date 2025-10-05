"""Base class and utilities for JSON based runners"""

import json
import os
import shlex
from dataclasses import dataclass
from typing import Optional

from lutris import settings
from lutris.exceptions import MissingGameExecutableError
from lutris.runners.runner import Runner
from lutris.util import datapath, system

JSON_RUNNER_DIRS = [
    os.path.join(datapath.get(), "json"),
    os.path.join(settings.RUNNER_DIR, "json"),
]


@dataclass(frozen=True)
class JsonRunnerSpec:
    game_options: list
    runner_options: list
    human_name: str
    description: str
    platforms: list
    runner_executable: str
    system_options_override: list
    entry_point_option: str
    download_url: Optional[str]
    runnable_alone: Optional[bool]
    flatpak_id: Optional[str]


_REQUIRED_KEYS = {
    "game_options",
    "human_name",
    "description",
    "platforms",
    "runner_executable",
}


def _load_and_validate_json(path: str) -> JsonRunnerSpec:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    missing = _REQUIRED_KEYS - data.keys()
    if missing:
        raise ValueError(f"Invalid runner JSON {path}: missing {missing}")

    return JsonRunnerSpec(
        game_options=data["game_options"],
        runner_options=data.get("runner_options", []),
        human_name=data["human_name"],
        description=data["description"],
        platforms=data["platforms"],
        runner_executable=data["runner_executable"],
        system_options_override=data.get("system_options_override", []),
        entry_point_option=data.get("entry_point_option", "main_file"),
        download_url=data.get("download_url"),
        runnable_alone=data.get("runnable_alone"),
        flatpak_id=data.get("flatpak_id"),
    )


class JsonRunner(Runner):
    json_path = None
    _json_cache = {}

    def __init__(self, config=None):
        super().__init__(config)
        path = self.json_path
        if not path:
            raise RuntimeError("Create subclasses of JsonRunner with the json_path attribute set")

        data = self._json_cache.get(path)
        if data is None:
            with open(path, encoding="utf-8") as file:
                data = json.load(file)
            self._json_cache[path] = data

        self._json_data = data

        self.game_options = self._json_data["game_options"]
        self.runner_options = self._json_data.get("runner_options", [])
        self.runner_name = self._json_data.get("name", "")
        self.human_name = self._json_data["human_name"]
        self.description = self._json_data["description"]
        platforms = self._json_data.get("platforms", {})
        self.platform_dict = (
            self._json_data["platforms"]
            if isinstance(platforms, dict)
            else {platform: platform for platform in platforms}
        )
        self.runner_executable = self._json_data["runner_executable"]
        self.system_options_override = self._json_data.get("system_options_override", [])
        self.entry_point_option = self._json_data.get("entry_point_option", "main_file")
        self.download_url = self._json_data.get("download_url")
        self.runnable_alone = self._json_data.get("runnable_alone")
        self.flatpak_id = self._json_data.get("flatpak_id")

    def play(self):
        """Return a launchable command constructed from the options"""
        arguments = self.get_command()
        for option in self.runner_options:
            if option["option"] not in self.runner_config:
                continue
            if option["type"] == "bool":
                if self.runner_config.get(option["option"]):
                    arguments.append(option["argument"])
            elif option["type"] == "choice":
                if self.runner_config.get(option["option"]) != "off":
                    arguments.append(option["argument"])
                    arguments.append(self.runner_config.get(option["option"]))
            elif option["type"] == "string":
                arguments.append(option["argument"])
                arguments.append(self.runner_config.get(option["option"]))
            elif option["type"] == "command_line":
                arg = option.get("argument")
                if arg:
                    arguments.append(arg)
                arguments += shlex.split(self.runner_config.get(option["option"]))
            else:
                raise RuntimeError("Unhandled type %s" % option["type"])

        # Prepend the option flag before for entry_point_option value
        for option in self.game_options:
            if self.entry_point_option != option["option"]:
                continue
            if "argument" in option:
                arguments.append(option["argument"])

        main_file = self.game_config.get(self.entry_point_option)
        if not main_file or not system.path_exists(main_file):
            raise MissingGameExecutableError(filename=main_file)

        for opt in self.runner_options:
            key = opt["option"]
            if key not in self.runner_config:
                continue
            try:
                self._OPTION_HANDLERS[opt["type"]](self, opt, arguments)
            except KeyError:
                raise RuntimeError(f"Unhandled type {opt['type']}")

        arguments.append(main_file)
        result = {"command": arguments}
        if self._json_data.get("env"):
            result["env"] = self._json_data["env"]
        if self._json_data.get("working_dir") == "runner":
            result["working_dir"] = os.path.dirname(os.path.join(settings.RUNNER_DIR, self.runner_executable_path))
        return result


def load_json_runners():
    runners = {}
    for base in JSON_RUNNER_DIRS:
        if not os.path.isdir(base):
            continue
        for entry in os.scandir(base):
            if not entry.name.endswith(".json"):
                continue
            json_full_path = os.path.join(json_dir, json_path)
            json_data = {}
            with open(json_full_path, encoding="utf-8") as json_file:
                json_data = json.load(json_file)
            runner_name = json_data.get("name") or json_path[:-5]
            runner_class = type(runner_name, (JsonRunner,), {"json_path": json_full_path})
            json_runners[runner_name] = runner_class
    return json_runners
