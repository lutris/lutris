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
            raise RuntimeError(
                "Create subclasses of JsonRunner with the json_path attribute set"
            )

        data = self._json_cache.get(path)
        if data is None:
            with open(path, encoding="utf-8") as file:
                data = json.load(file)
            self._json_cache[path] = data

        self._json_data = data

        self.game_options = data.game_options
        self.runner_options = data.runner_options
        self.human_name = data.human_name
        self.description = data.description
        self.platforms = data.platforms
        self.runner_executable = data.runner_executable
        self.system_options_override = data.system_options_override
        self.entry_point_option = data.entry_point_option
        self.download_url = data.download_url
        self.runnable_alone = data.runnable_alone
        self.flatpak_id = data.flatpak_id

    def _opt_bool(self, opt, args):
        if self.runner_config.get(opt["option"]):
            args.append(opt["argument"])

    def _opt_choice(self, opt, args):
        val = self.runner_config.get(opt["option"])
        if val != "off":
            args.extend((opt["argument"], val))

    def _opt_string(self, opt, args):
        args.extend((opt["argument"], self.runner_config.get(opt["option"])))

    def _opt_cmd(self, opt, args):
        arg = opt.get("argument")
        if arg:
            args.append(arg)
        args.extend(shlex.split(self.runner_config.get(opt["option"])))

    _OPTION_HANDLERS = {
        "bool": _opt_bool,
        "choice": _opt_choice,
        "string": _opt_string,
        "command_line": _opt_cmd,
    }

    def play(self):
        """Return a launchable command constructed from the options"""
        arguments = self.get_command()

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
        return {"command": arguments}


def load_json_runners():
    runners = {}
    for base in JSON_RUNNER_DIRS:
        if not os.path.isdir(base):
            continue
        for entry in os.scandir(base):
            if not entry.name.endswith(".json"):
                continue
            name = entry.name[:-5]
            runners[name] = type(name, (JsonRunner,), {"json_path": entry.path})
    return runners
