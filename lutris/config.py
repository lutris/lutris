"""Handle the game, runner and global system configurations."""

import os
from os.path import join
import time

from lutris import pga, settings, sysoptions
from lutris.runners import import_runner, InvalidRunner
from lutris.util.system import path_exists, create_folder
from lutris.util.yaml import read_yaml_from_file, write_yaml_to_file
from lutris.util.log import logger


# Temporary config name for games that haven't been created yet
TEMP_CONFIG = "TEMP_CONFIG"


def check_config():
    """Check if initial configuration is correct."""
    directories = [
        settings.CONFIG_DIR,
        join(settings.CONFIG_DIR, "runners"),
        join(settings.CONFIG_DIR, "games"),
        settings.DATA_DIR,
        join(settings.DATA_DIR, "covers"),
        settings.ICON_PATH,
        join(settings.DATA_DIR, "banners"),
        join(settings.DATA_DIR, "coverart"),
        join(settings.DATA_DIR, "runners"),
        join(settings.DATA_DIR, "lib"),
        settings.RUNTIME_DIR,
        settings.CACHE_DIR,
        join(settings.CACHE_DIR, "installer"),
        join(settings.CACHE_DIR, "tmp"),
    ]
    for directory in directories:
        create_folder(directory)

    pga.syncdb()


def make_game_config_id(game_slug):
    """Return an unique config id to avoid clashes between multiple games"""
    return "{}-{}".format(game_slug, int(time.time()))


class LutrisConfig:
    """Class where all the configuration handling happens.

    Description
    ===========
    Lutris' configuration uses a cascading mecanism where
    each higher, more specific level overrides the lower ones

    The levels are (highest to lowest): `game`, `runner` and `system`.
    Each level has its own set of options (config section), available to and
    overriden by upper levels:
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

    def __init__(self, runner_slug=None, game_config_id=None, level=None):
        self.game_config_id = game_config_id
        if runner_slug:
            self.runner_slug = str(runner_slug)
        else:
            self.runner_slug = runner_slug

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

        # Init and load config files
        self.game_level = {"system": {}, self.runner_slug: {}, "game": {}}
        self.runner_level = {"system": {}, self.runner_slug: {}}
        self.system_level = {"system": {}}
        self.game_level.update(read_yaml_from_file(self.game_config_path))
        self.runner_level.update(read_yaml_from_file(self.runner_config_path))
        self.system_level.update(read_yaml_from_file(self.system_config_path))

        self.update_cascaded_config()
        self.update_raw_config()

    def __repr__(self):
        return "LutrisConfig(level=%s, game_config_id=%s, runner=%s)" % (
            self.level,
            self.game_config_id,
            self.runner_slug,
        )

    @property
    def system_config_path(self):
        return os.path.join(settings.CONFIG_DIR, "system.yml")

    @property
    def runner_config_path(self):
        if not self.runner_slug:
            return None
        return os.path.join(settings.CONFIG_DIR, "runners/%s.yml" % self.runner_slug)

    @property
    def game_config_path(self):
        if not self.game_config_id or self.game_config_id == TEMP_CONFIG:
            return None
        return os.path.join(settings.CONFIG_DIR, "games/%s.yml" % self.game_config_id)

    def update_cascaded_config(self):
        if self.system_level.get("system") is None:
            self.system_level["system"] = {}
        self.system_config.clear()
        self.system_config.update(self.get_defaults("system"))
        self.system_config.update(self.system_level.get("system"))

        if self.level in ["runner", "game"] and self.runner_slug:
            if self.runner_level.get(self.runner_slug) is None:
                self.runner_level[self.runner_slug] = {}
            if self.runner_level.get("system") is None:
                self.runner_level["system"] = {}
            self.runner_config.clear()
            self.runner_config.update(self.get_defaults("runner"))
            self.runner_config.update(self.runner_level.get(self.runner_slug))
            self.system_config.update(self.runner_level.get("system"))

        if self.level == "game" and self.runner_slug:
            if self.game_level.get("game") is None:
                self.game_level["game"] = {}
            if self.game_level.get(self.runner_slug) is None:
                self.game_level[self.runner_slug] = {}
            if self.game_level.get("system") is None:
                self.game_level["system"] = {}
            self.game_config.clear()
            self.game_config.update(self.get_defaults("game"))
            self.game_config.update(self.game_level.get("game"))
            self.runner_config.update(self.game_level.get(self.runner_slug))
            self.system_config.update(self.game_level.get("system"))

    def update_raw_config(self):
        # Select the right level of config
        if self.level == "game":
            raw_config = self.game_level
        elif self.level == "runner":
            raw_config = self.runner_level
        else:
            raw_config = self.system_level

        # Load config sections
        self.raw_system_config = raw_config["system"]
        if self.level in ["runner", "game"]:
            self.raw_runner_config = raw_config[self.runner_slug]
        if self.level == "game":
            self.raw_game_config = raw_config["game"]

        self.raw_config = raw_config

    def remove(self):
        """Delete the configuration file from disk."""
        if path_exists(self.game_config_path):
            os.remove(self.game_config_path)
            logger.debug("Removed config %s", self.game_config_path)
        else:
            logger.debug("No config file at %s", self.game_config_path)

    def save(self):
        """Save configuration file according to its type"""
        # logger.debug("Saving config %s", self.__repr__())
        if self.level == "system":
            config = self.system_level
            config_path = self.system_config_path
        elif self.level == "runner":
            config = self.runner_level
            config_path = self.runner_config_path
        elif self.level == "game":
            config = self.game_level
            config_path = self.game_config_path
        else:
            raise ValueError("Invalid config level '%s'" % self.level)
        write_yaml_to_file(config_path, config)
        self.update_cascaded_config()

    def get_defaults(self, options_type):
        """Return a dict of options' default value."""
        options_dict = self.options_as_dict(options_type)
        defaults = {}
        for option, params in options_dict.items():
            if "default" in params:
                defaults[option] = params["default"]
        return defaults

    def options_as_dict(self, options_type):
        """Convert the option list to a dict with option name as keys"""
        if options_type == "system":
            options = (
                sysoptions.with_runner_overrides(self.runner_slug)
                if self.runner_slug
                else sysoptions.system_options
            )
        else:
            if not self.runner_slug:
                return None
            attribute_name = options_type + "_options"

            try:
                runner = import_runner(self.runner_slug)
            except InvalidRunner:
                options = {}
            else:
                if not getattr(runner, attribute_name):
                    runner = runner()

                options = getattr(runner, attribute_name)
        return dict((opt["option"], opt) for opt in options)
