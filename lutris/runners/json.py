"""Base class and utilities for JSON based runners"""
import json
import os

from lutris import settings
from lutris.runners.runner import Runner
from lutris.util import datapath, system

JSON_RUNNER_DIRS = [
    os.path.join(datapath.get(), "json"),
    os.path.join(settings.RUNNER_DIR, "json"),
]


class JsonRunner(Runner):
    json_path = None

    def __init__(self, config=None):
        super().__init__(config)
        if not self.json_path:
            raise RuntimeError("Create subclasses of JsonRunner with the json_path attribute set")
        with open(self.json_path) as json_file:
            self._json_data = json.load(json_file)

        self.game_options = self._json_data["game_options"]
        self.runner_options = self._json_data.get("runner_options", [])
        self.human_name = self._json_data["human_name"]
        self.description = self._json_data["description"]
        self.platforms = self._json_data["platforms"]
        self.runner_executable = self._json_data["runner_executable"]
        self.system_options_override = self._json_data.get("system_options_override", [])
        self.entry_point_option = self._json_data.get("entry_point_option", "main_file")
        self.download_url = self._json_data.get("download_url")

    def play(self):
        """Return a launchable command constructed from the options"""
        arguments = [self.get_executable()]
        for option in self.runner_options:
            if option["option"] not in self.runner_config:
                continue
            if option["type"] == "bool":
                arguments.append(option["argument"])
            elif option["type"] == "choice":
                if self.runner_config.get(option["option"]) != "off":
                    arguments.append(option["argument"])
                    arguments.append(self.runner_config.get(option["option"]))
            else:
                raise RuntimeError("Unhandled type %s" % option["type"])
        main_file = self.game_config.get(self.entry_point_option)
        if not system.path_exists(main_file):
            return {"error": "FILE_NOT_FOUND", "file": main_file}
        arguments.append(main_file)
        return {"command": arguments}


def load_json_runners():
    json_runners = {}
    for json_dir in JSON_RUNNER_DIRS:
        if not os.path.exists(json_dir):
            continue
        for json_path in os.listdir(json_dir):
            if not json_path.endswith(".json"):
                continue
            runner_name = json_path[:-5]
            runner_class = type(
                runner_name,
                (JsonRunner, ),
                {'json_path': os.path.join(json_dir, json_path)}
            )
            json_runners[runner_name] = runner_class
    return json_runners
