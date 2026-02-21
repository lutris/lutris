"""Base class and utilities for YAML based runners"""

from pathlib import Path
from typing import Any, Dict, Optional

from lutris import settings
from lutris.runners.model import ModelRunner
from lutris.util import datapath
from lutris.util.yaml import read_yaml_from_file

SETTING_YAML_RUNNER_DIR = Path(settings.RUNNER_DIR) / "yaml"

YAML_RUNNER_DIRS = [
    Path(datapath.get()) / "yaml",
    SETTING_YAML_RUNNER_DIR,
]


class YamlRunner(ModelRunner):
    yaml_path: Optional[Path] = None

    def __init__(
        self,
        config=None,
        *,
        dict_data: Optional[Dict[str, Any]] = None,
    ):
        if not self.yaml_path and not isinstance(dict_data, dict):
            raise RuntimeError(
                f"Create subclasses of {self.__class__.__name__} with the yaml_path attribute set,"
                " or supply the `dict_data` argument with a dictionary"
            )

        yaml_data: Dict[str, Any] = {}
        if self.yaml_path:
            yaml_data = read_yaml_from_file(str(self.yaml_path))
        else:
            yaml_data = dict_data  # type: ignore
        super().__init__(dict_data=yaml_data, config=config)

    @property
    def file_path(self):
        return self.yaml_path


def load_yaml_runners():
    yaml_runners = {}
    for yaml_dir in YAML_RUNNER_DIRS:
        if not yaml_dir.exists():
            continue
        for yaml_path in yaml_dir.iterdir():
            if yaml_path.suffix not in [".yml", "yaml"]:
                continue
            runner_name = yaml_path.stem
            runner_class = type(runner_name, (YamlRunner,), {"yaml_path": yaml_dir / yaml_path})
            yaml_runners[runner_name] = runner_class
    return yaml_runners
