"""Base class and utilities for JSON based runners"""

import json
import os
import shlex
from dataclasses import dataclass
from typing import Any

from lutris import settings
from lutris.exceptions import MissingGameExecutableError
from lutris.runners.runner import Runner, RunnerOptionDict
from lutris.util import datapath, system

JSON_RUNNER_DIRS = [
    os.path.join(datapath.get(), "json"),
    os.path.join(settings.RUNNER_DIR, "json"),
]


@dataclass(frozen=True)
class JsonRunnerSpec:
    game_options: list[RunnerOptionDict]
    runner_options: list[RunnerOptionDict]
    runner_name: str
    human_name: str
    description: str
    platform_dict: dict[str, str]
    runner_executable: str
    system_options_override: list[RunnerOptionDict]
    entry_point_option: str
    download_url: str | None
    runnable_alone: bool | None
    flatpak_id: str | None
    env: dict[str, str]
    working_dir: str | None


_REQUIRED_KEYS = {
    "game_options",
    "human_name",
    "description",
    "platforms",
    "runner_executable",
}


def _to_platform_dict(path: str, platforms: Any) -> dict[str, str]:
    """Reads the 'platforms' key, which can be a list of Lutris platform names, or a
    dict mapping each Lutris platform name onto the code the runner uses for it."""
    if isinstance(platforms, dict):
        return {str(name): str(code) for name, code in platforms.items()}
    if isinstance(platforms, list):
        return Runner.to_platform_dict([str(name) for name in platforms])
    raise ValueError(f"Invalid runner JSON {path}: 'platforms' must be a list or a dict")


def _load_and_validate_json(path: str) -> JsonRunnerSpec:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    missing = _REQUIRED_KEYS - data.keys()
    if missing:
        raise ValueError(f"Invalid runner JSON {path}: missing {missing}")

    return JsonRunnerSpec(
        game_options=data["game_options"],
        runner_options=data.get("runner_options", []),
        runner_name=data.get("name", ""),
        human_name=data["human_name"],
        description=data["description"],
        platform_dict=_to_platform_dict(path, data["platforms"]),
        runner_executable=data["runner_executable"],
        system_options_override=data.get("system_options_override", []),
        entry_point_option=data.get("entry_point_option", "main_file"),
        download_url=data.get("download_url"),
        runnable_alone=data.get("runnable_alone"),
        flatpak_id=data.get("flatpak_id"),
        env=data.get("env") or {},
        working_dir=data.get("working_dir"),
    )


class JsonRunner(Runner):
    json_path = None
    _json_cache = {}

    def __init__(self, config=None):
        super().__init__(config)
        path = self.json_path
        if not path:
            raise RuntimeError("Create subclasses of JsonRunner with the json_path attribute set")

        spec = self._json_cache.get(path)
        if spec is None:
            spec = _load_and_validate_json(path)
            self._json_cache[path] = spec

        self.spec = spec

        self.game_options = spec.game_options
        self.runner_options = spec.runner_options
        self.runner_name = spec.runner_name
        self.human_name = spec.human_name
        self.description = spec.description
        self.platform_dict = spec.platform_dict
        self.runner_executable = spec.runner_executable
        self.system_options_override = spec.system_options_override
        self.entry_point_option = spec.entry_point_option
        self.download_url = spec.download_url
        self.runnable_alone = spec.runnable_alone
        self.flatpak_id = spec.flatpak_id

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

        for opt in self.runner_options:
            key = opt["option"]
            if key not in self.runner_config:
                continue
            try:
                self._OPTION_HANDLERS[opt["type"]](self, opt, arguments)
            except KeyError:
                raise RuntimeError(f"Unhandled type {opt['type']}")

        # Prepend the option flag before for entry_point_option value
        for option in self.game_options:
            if self.entry_point_option != option["option"]:
                continue
            if "argument" in option:
                arguments.append(option["argument"])

        main_file = self.game_config.get(self.entry_point_option)
        if not main_file or not system.path_exists(main_file):
            raise MissingGameExecutableError(filename=main_file)

        arguments.append(main_file)
        result = {"command": arguments}
        if self.spec.env:
            result["env"] = dict(self.spec.env)
        if self.spec.working_dir == "runner":
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
            name = entry.name[:-5]
            runners[name] = type(name, (JsonRunner,), {"json_path": entry.path})
    return runners
