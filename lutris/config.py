"""Handle the game, runner and global system configurations."""

import os
import time
from shutil import copyfile
from typing import Any, Dict, Optional, Set

from lutris import settings, sysoptions
from lutris.runners import InvalidRunnerError, import_runner
from lutris.util.log import logger
from lutris.util.system import path_exists
from lutris.util.yaml import read_yaml_from_file, write_yaml_to_file


def make_game_config_id(game_slug: str) -> str:
    """Return an unique config id to avoid clashes between multiple games"""
    return "{}-{}".format(game_slug, int(time.time()))


def write_game_config(game_slug: str, config: Dict[str, Any]) -> str:
    """Writes a game config to disk"""
    configpath = make_game_config_id(game_slug)
    logger.debug("Writing game config to %s", configpath)
    config_filename = os.path.join(settings.CONFIG_DIR, "games/%s.yml" % configpath)
    write_yaml_to_file(config, config_filename)
    return configpath


def duplicate_game_config(game_slug: str, source_config_id: str) -> str:
    """Copies an existing configuration file, giving it a new id that this
    function returns."""
    new_config_id = make_game_config_id(game_slug)
    src_path = os.path.join(settings.CONFIG_DIR, "games/%s.yml" % source_config_id)
    dest_path = os.path.join(settings.CONFIG_DIR, "games/%s.yml" % new_config_id)
    copyfile(src_path, dest_path)
    return new_config_id


def rename_config(old_config_id: str, new_slug: str) -> Optional[str]:
    old_slug, timestamp = old_config_id.rsplit("-", 1)
    if old_slug == new_slug:
        return None
    new_config_id = f"{new_slug}-{timestamp}"
    src_path = f"{settings.GAME_CONFIG_DIR}/{old_config_id}.yml"
    dest_path = f"{settings.GAME_CONFIG_DIR}/{new_config_id}.yml"
    os.rename(src_path, dest_path)
    return new_config_id


class LutrisConfig:
    """Class where all the configuration handling happens.

    Description
    ===========
    Lutris' configuration uses a cascading mechanism where
    each higher, more specific level overrides the lower ones

    The levels are (highest to lowest): `game`, `runner` and `system`.
    Each level has its own set of options (config section), available to and
    overridden by upper levels:
    ```
     level | Config sections
    -------|----------------------
      game | system, runner, game
    runner | system, runner
    system | system
    ```
    Example: if requesting runner options at game level, their returned value
    will be from the game level config if it's set at this level; if not it
    will be the value from runner level if available; and if not, the default
    value set in the runner's module, or None.

    The config levels are stored in separate YAML format text files.

    Usage
    =====
    The config level will be auto set depending on what you pass to __init__:
    - For game level, pass game_config_id and optionally runner_slug (better perfs)
    - For runner level, pass runner_slug
    - For system level, pass nothing
    If need be, you can pass the level manually.

    To read, use the config sections dicts: game_config, runner_config and
    system_config.

    To write, modify the relevant `raw_*_config` section dict, then run
    `save()`.

    """

    def __init__(
        self,
        runner_slug: Optional[str] = None,
        game_config_id: Optional[str] = None,
        level: Optional[str] = None,
        options_supported: Optional[Set[str]] = None,
    ):
        self.game_config_id = game_config_id
        if runner_slug:
            self.runner_slug: Optional[str] = str(runner_slug)
        else:
            self.runner_slug: Optional[str] = runner_slug

        self.options_supported = options_supported
        # Cascaded config sections (for reading)
        self.game_config = {}
        self.runner_config = {}
        self.system_config = {}

        # Raw (non-cascaded) sections (for writing)
        self.raw_game_config = {}
        self.raw_runner_config = {}
        self.raw_system_config = {}

        self.raw_config = {}

        # Set config level
        self.level = level
        if not level:
            if game_config_id:
                self.level = "game"
            elif runner_slug:
                self.level = "runner"
            else:
                self.level = "system"
        self.initialize_config()

    def __repr__(self):
        return "LutrisConfig(level=%s, game_config_id=%s, runner=%s)" % (
            self.level,
            self.game_config_id,
            self.runner_slug,
        )

    @property
    def system_config_path(self) -> str:
        return os.path.join(settings.CONFIG_DIR, "system.yml")

    @property
    def runner_config_path(self) -> Optional[str]:
        if not self.runner_slug:
            return None
        return os.path.join(settings.RUNNERS_CONFIG_DIR, "%s.yml" % self.runner_slug)

    @property
    def game_config_path(self) -> Optional[str]:
        if not self.game_config_id:
            return None
        return os.path.join(settings.CONFIG_DIR, "games/%s.yml" % self.game_config_id)

    def initialize_config(self) -> None:
        """Init and load config files"""
        self.game_level = {"system": {}, self.runner_slug: {}, "game": {}}
        self.runner_level = {"system": {}, self.runner_slug: {}}
        self.system_level = {"system": {}}
        if self.game_config_path:
            self.game_level.update(read_yaml_from_file(self.game_config_path))
        if self.runner_config_path:
            self.runner_level.update(read_yaml_from_file(self.runner_config_path))
        self.system_level.update(read_yaml_from_file(self.system_config_path))

        self.update_cascaded_config()
        self.update_raw_config()

    def update_cascaded_config(self) -> None:
        if self.system_level.get("system") is None:
            self.system_level["system"] = {}
        self.system_config.clear()
        self.system_config.update(self.get_defaults("system"))
        self.system_config.update(self.system_level.get("system", {}))

        if self.level in ["runner", "game"] and self.runner_slug:
            if self.runner_level.get(self.runner_slug) is None:
                self.runner_level[self.runner_slug] = {}
            if self.runner_level.get("system") is None:
                self.runner_level["system"] = {}
            self.runner_config.clear()
            self.runner_config.update(self.get_defaults("runner"))
            self.runner_config.update(self.runner_level.get(self.runner_slug, {}))
            self.merge_to_system_config(self.runner_level.get("system"))

        if self.level == "game" and self.runner_slug:
            if self.game_level.get("game") is None:
                self.game_level["game"] = {}
            if self.game_level.get(self.runner_slug) is None:
                self.game_level[self.runner_slug] = {}
            if self.game_level.get("system") is None:
                self.game_level["system"] = {}
            self.game_config.clear()
            self.game_config.update(self.get_defaults("game"))
            self.game_config.update(self.game_level.get("game", {}))
            self.runner_config.update(self.game_level.get(self.runner_slug, {}))
            self.merge_to_system_config(self.game_level.get("system"))

    def merge_to_system_config(self, config: Optional[Dict[str, Any]]) -> None:
        """Merge a configuration to the system configuration"""
        if config:
            existing_env = None
            if self.system_config.get("env") and "env" in config:
                existing_env = self.system_config["env"]
            self.system_config.update(config)
            if existing_env:
                self.system_config["env"] = existing_env
                self.system_config["env"].update(config["env"])

        # Don't save env items where the key is empty; this would crash when used.
        if "env" in self.system_config:
            self.system_config["env"] = {k: v for k, v in self.system_config["env"].items() if k}

    def update_raw_config(self) -> None:
        # Select the right level of config
        if self.level == "game":
            raw_config = self.game_level
        elif self.level == "runner":
            raw_config = self.runner_level
        else:
            raw_config = self.system_level

        # Load config sections
        self.raw_system_config = raw_config["system"]
        if self.level in ["runner", "game"] and self.runner_slug is not None:
            self.raw_runner_config = raw_config[self.runner_slug]
        if self.level == "game":
            self.raw_game_config = raw_config["game"]

        self.raw_config = raw_config

    def remove(self) -> None:
        """Delete the configuration file from disk."""
        if not self.game_config_path or not path_exists(self.game_config_path):
            logger.debug("No config file at %s", self.game_config_path)
            return
        os.remove(self.game_config_path)
        logger.debug("Removed config %s", self.game_config_path)

    def save(self) -> None:
        """Save configuration file according to its type"""

        if self.options_supported is not None:
            raise RuntimeError("LutrisConfig instances that are restricted to only some options can't be saved.")

        if self.level == "system":
            config = self.system_level
            config_path: str = self.system_config_path
        elif self.level == "runner" and self.runner_config_path:
            config = self.runner_level
            config_path = self.runner_config_path
        elif self.level == "game" and self.game_config_path:
            config = self.game_level
            config_path = self.game_config_path
        else:
            raise ValueError("Invalid config level '%s'" % self.level)
        # Remove keys with no values from config before saving
        config = {key: value for key, value in config.items() if value}
        logger.debug("Saving %s config to %s", self, config_path)
        write_yaml_to_file(config, config_path)
        self.initialize_config()

    def get_defaults(self, options_type: str) -> Dict[str, Any]:
        """Return a dict of options' default value."""
        options_dict = self.options_as_dict(options_type)
        defaults = {}
        for option, params in options_dict.items():
            if "default" in params:
                default = params["default"]
                if callable(default):
                    if self.options_supported is None or option in self.options_supported:
                        try:
                            default = default()
                        except Exception as ex:
                            logger.exception("Unable to generate a default for '%s': %s", option, ex)
                            continue
                    else:
                        # Do not evaluate options we aren't supposed to use, in case
                        # this is expensive or unsafe.
                        default = None
                defaults[option] = default
        return defaults

    def options_as_dict(self, options_type: str) -> Dict[str, Any]:
        """Convert the option list to a dict with option name as keys"""
        if options_type == "system":
            options = (
                sysoptions.with_runner_overrides(self.runner_slug) if self.runner_slug else sysoptions.system_options
            )
        else:
            if not self.runner_slug:
                return {}
            attribute_name = options_type + "_options"

            try:
                runner = import_runner(self.runner_slug)
            except InvalidRunnerError:
                options = {}
            else:
                if not getattr(runner, attribute_name):
                    runner = runner()

                options = getattr(runner, attribute_name)
        return dict((opt["option"], opt) for opt in options)
