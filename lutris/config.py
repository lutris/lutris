#!/usr/bin/python
# -*- coding:Utf-8 -*-
#
#  Copyright (C) 2010 Mathieu Comandon <strider@strycore.com>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License version 3 as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""Handle the basic configuration of Lutris."""

import os
import sys
import yaml
import logging
from os.path import join

from gi.repository import Gio

from lutris import pga, settings, sysoptions
from lutris.runners import import_runner
from lutris.util.log import logger


def register_handler():
    """Register the lutris: protocol to open with the application."""
    logger.debug("registering protocol")
    executable = os.path.abspath(sys.argv[0])
    base_key = "desktop.gnome.url-handlers.lutris"
    schema_directory = "/usr/share/glib-2.0/schemas/"
    schema_source = Gio.SettingsSchemaSource.new_from_directory(
        schema_directory, None, True
    )
    schema = schema_source.lookup(base_key, True)
    if schema:
        settings = Gio.Settings.new(base_key)
        settings.set_string('command', executable)
    else:
        logger.warning("Schema not installed, cannot register url-handler")


def check_config(force_wipe=False):
    """Check if initial configuration is correct."""
    directories = [settings.CONFIG_DIR,
                   join(settings.CONFIG_DIR, "runners"),
                   join(settings.CONFIG_DIR, "games"),
                   settings.DATA_DIR,
                   join(settings.DATA_DIR, "covers"),
                   settings.ICON_PATH,
                   join(settings.DATA_DIR, "banners"),
                   join(settings.DATA_DIR, "runners"),
                   join(settings.DATA_DIR, "lib"),
                   settings.RUNTIME_DIR,
                   settings.CACHE_DIR,
                   join(settings.CACHE_DIR, "installer"),
                   join(settings.CACHE_DIR, "tmp")]
    for directory in directories:
        if not os.path.exists(directory):
            logger.debug("creating directory %s" % directory)
            os.makedirs(directory)

    if force_wipe:
        os.remove(settings.PGA_DB)
    pga.syncdb()


def read_yaml_from_file(filename):
    """Read filename and return parsed yaml"""
    if not filename or not os.path.exists(filename):
        return {}
    try:
        content = file(filename, 'r').read()
        yaml_content = yaml.load(content) or {}
    except (yaml.scanner.ScannerError, yaml.parser.ParserError):
        logger.error("error parsing file %s", filename)
        yaml_content = {}
    return yaml_content


def write_yaml_to_file(filepath, config):
    if not filepath:
        raise ValueError('Missing filepath')
    yaml_config = yaml.dump(config, default_flow_style=False)
    with open(filepath, "w") as filehandler:
        filehandler.write(yaml_config)


class LutrisConfig(object):
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
    - For game level, pass game slug and optionally runner_slug (better perfs)
    - For runner level, pass runner_slug
    - For system level, pass nothing
    If need be, you can pass the level manually.

    To read, use the config sections dicts: game_config, runner_config and
    system_config.

    To write, modify the relevant `raw_XXXX_config` section dict, then run
    `save()`.

    """
    def __init__(self, runner_slug=None, game_slug=None, level=None):
        self.game_slug = game_slug
        self.runner_slug = runner_slug
        if game_slug and not runner_slug:
            self.runner_slug = pga.get_game_by_slug(game_slug).get('runner')

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
            if game_slug:
                self.level = 'game'
            elif runner_slug:
                self.level = 'runner'
            else:
                self.level = 'system'

        # Init and load config files
        self.game_level = {'system': {}, self.runner_slug: {}, 'game': {}}
        self.runner_level = {'system': {}, self.runner_slug: {}}
        self.system_level = {'system': {}}
        self.game_level.update(read_yaml_from_file(self.game_config_path))
        self.runner_level.update(read_yaml_from_file(self.runner_config_path))
        self.system_level.update(read_yaml_from_file(self.system_config_path))

        self.update_cascaded_config()
        self.update_raw_config()

    @property
    def system_config_path(self):
        return os.path.join(settings.CONFIG_DIR, "system.yml")

    @property
    def runner_config_path(self):
        if not self.runner_slug:
            return
        return os.path.join(settings.CONFIG_DIR, "runners/%s.yml" %
                            self.runner_slug)

    @property
    def game_config_path(self):
        if not self.game_slug:
            return
        return os.path.join(settings.CONFIG_DIR, "games/%s.yml" %
                            self.game_slug)

    def __str__(self):
        return str(self.config)

    def update_cascaded_config(self):
        self.system_config.clear()
        self.system_config.update(self.get_defaults('system'))
        self.system_config.update(self.system_level['system'])

        if self.level in ['runner', 'game'] and self.runner_slug:
            self.runner_config.clear()
            self.runner_config.update(self.get_defaults('runner'))
            self.runner_config.update(self.runner_level[self.runner_slug])
            self.system_config.update(self.runner_level['system'])

        if self.level == 'game' and self.runner_slug:
            self.game_config.clear()
            self.game_config.update(self.get_defaults('game'))
            self.game_config.update(self.game_level['game'])
            self.runner_config.update(self.game_level[self.runner_slug])
            self.system_config.update(self.game_level['system'])

    def update_raw_config(self):
        # Select the right level of config
        if self.level == 'game':
            raw_config = self.game_level
        elif self.level == 'runner':
            raw_config = self.runner_level
        else:
            raw_config = self.system_level

        # Load config sections
        self.raw_system_config = raw_config['system']
        if self.level in ['runner', 'game']:
            self.raw_runner_config = raw_config[self.runner_slug]
        if self.level == 'game':
            self.raw_game_config = raw_config['game']

        self.raw_config = raw_config

    def remove(self, game=None):
        """Delete the configuration file from disk."""
        if game is None:
            game = self.game_slug
        logging.debug("removing config for %s", game)
        if os.path.exists(self.game_config_path):
            os.remove(self.game_config_path)
        else:
            logger.debug("No config file at %s" % self.game_config_path)

    def save(self):
        """Save configuration file according to its type"""
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

    def get_path(self, default=None):
        """Return the main install path if exists."""
        path = self.system_config.get('game_path') or ''
        if os.path.exists(path):
            return path
        if default and os.path.exists(default):
            return default

    def get_defaults(self, options_type):
        """Return a dict of options' default value."""
        options_dict = self.options_as_dict(options_type)
        defaults = {}
        for option, params in options_dict.iteritems():
            if 'default' in params:
                defaults[option] = params['default']
        return defaults

    def options_as_dict(self, options_type):
        """Convert the option list to a dict with option name as keys"""
        options = {}
        if options_type == 'system':
            options = sysoptions.system_options
        elif options_type == 'runner' and self.runner_slug:
            runner = import_runner(self.runner_slug)()
            options = runner.runner_options
        elif options_type == 'game' and self.runner_slug:
            runner = import_runner(self.runner_slug)()
            options = runner.game_options
        return dict((opt['option'], opt) for opt in options)
