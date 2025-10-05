"""Base class and utilities for JSON based runners"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from lutris import settings
from lutris.runners.model import ModelRunner
from lutris.util import datapath

SETTING_JSON_RUNNER_DIR = Path(settings.RUNNER_DIR) / "json"

JSON_RUNNER_DIRS = [
    Path(datapath.get()) / "json",
    SETTING_JSON_RUNNER_DIR,
]


class JsonRunner(ModelRunner):
    json_path: Optional[Path] = None

    def __init__(
        self,
        config=None,
        *,
        dict_data: Optional[Dict[str, Any]] = None,
    ):
        if not self.json_path and not isinstance(dict_data, dict):
            raise RuntimeError(
                "Create subclasses of JsonRunner with the json_path attribute set,"
                " or supply the `dict_data` argument with a dictionary"
            )

        json_data: Dict[str, Any] = {}
        if self.json_path:
            with open(self.json_path, encoding="utf-8") as json_file:
                json_data = json.load(json_file)
        else:
            json_data = dict_data  # type: ignore
        super().__init__(dict_data=json_data, config=config)

    @property
    def file_path(self):
        return self.json_path


def load_json_runners():
    json_runners = {}
    for json_dir in JSON_RUNNER_DIRS:
        if not json_dir.exists():
            continue
        for json_path in json_dir.iterdir():
            if json_path.suffix not in [".json"]:
                continue
            runner_name = json_path.stem
            runner_class = type(runner_name, (JsonRunner,), {"json_path": json_dir / json_path})
            json_runners[runner_name] = runner_class
    return json_runners
