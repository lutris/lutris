# -*- coding: utf-8 -*-

import os

from lutris.runners.runner import Runner
from lutris.util import datapath
from lutris import pga, settings

DEFAULT_ICON = os.path.join(datapath.get(), 'media/default_icon.png')

class web(Runner):
    human_name = "Web"
    description = "Runs web based games"
    platform = "Web based games"
    description = "Runs web games"
    game_options = [
        {
            "option": "main_file",
            "type": "string",
            "label": "Full address (URL)",
            'help': ("The full address of the game's web page.")
        }
    ]
    runner_options = [
        {
            "option": "fullscreen",
            "label": "Open in fullscreen",
            "type": "bool",
            "default": False,
            'help': ("Launch the game in fullscreen.")
        },
        {
            "option": "maximize_window",
            "label": "Open window maximized",
            "type": "bool",
            "default": False,
            'help': ("Maximizes the window when game starts.")
        },
        {
            'option': 'window_size',
            'label': 'Window size',
            'type': 'choice_with_entry',
            'choices': ["640x480", "800x600", "1024x768", "1280x720", "1280x1024", "1920x1080"],
            'default': '800x600',
            'help': ("The initial size of the game window when not opened.")
        },
        {
            "option": "disable_resizing",
            "label": "Disable window resizing (disables fullscreen and maximize)",
            "type": "bool",
            "default": False,
            'help': ("You can't resize this window.")
        },
        {
            "option": "frameless",
            "label": "Borderless window",
            "type": "bool",
            "default": False,
            'help': ("The window has no borders/frame.")
        },
        {
            "option": "disable_menu_bar",
            "label": "Disable menu bar and default shortcuts",
            "type": "bool",
            "default": False,
            'help': ("This also disables default keyboard shortcuts, like copy/paste and fullscreen toggling.")
        },
        {
            "option": "disable_scrolling",
            "label": "Disable page scrolling and hide scrollbars",
            "type": "bool",
            "default": False,
            'help': ("Disables scrolling on the page.")
        },
        {
            "option": "hide_cursor",
            "label": "Hide mouse cursor",
            "type": "bool",
            "default": False,
            'help': ("Prevents the mouse cursor from showing when hovering above the window.")
        },
        {
            'option': 'open_links',
            'label': 'Open links in game window',
            'type': 'bool',
            'default': False,
            'help': ("Enable this option if you want clicked links to open inside the game window. By default all links open in your default web browser.")
        },
        {
            "option": "enable_flash",
            "label": "Enable Adobe Flash Player",
            "type": "bool",
            "default": False,
            'help': ("Enable Adobe Flash Player.")
        },
        {
            "option": "devtools",
            "label": "Debug with Developer Tools",
            "type": "bool",
            "default": False,
            'help': ("Let's you debug the page."),
            'advanced': True
        },
    ]
    runner_executable = 'web/electron/electron'
    system_options_override = [
        {
            'option': 'disable_runtime',
            'default': False,
        }
    ]

    def get_env(self, full=True):
        if full:
            env = os.environ.copy()
        else:
            env = {}

        env['ENABLE_FLASH_PLAYER'] = '1' if self.runner_config['enable_flash'] else '0'

        return env

    def play(self):
        url = self.game_config.get('main_file')
        if not url:
            return {'error': 'CUSTOM',
                    'text': ("The web address is empty, \n"
                             "verify the game's configuration."), }

        game_data = pga.get_game_by_field(self.config.game_config_id, 'configpath')

        icon = datapath.get_icon_path(game_data.get('slug'))
        if not os.path.exists(icon):
            icon = DEFAULT_ICON

        command = [self.get_executable()]

        command.append(os.path.join(settings.RUNNER_DIR, 'web/electron/resources/app.asar'))

        command.append(url)

        command.append("--name")
        command.append(game_data.get('name'))

        command.append("--icon")
        command.append(icon)

        if self.runner_config.get("fullscreen"):
            command.append("--fullscreen")

        if self.runner_config.get("frameless"):
            command.append("--frameless")

        if self.runner_config.get("disable_resizing"):
            command.append("--disable-resizing")

        if self.runner_config.get("disable_menu_bar"):
            command.append("--disable-menu-bar")

        if self.runner_config.get("window_size"):
            command.append("--window-size")
            command.append(self.runner_config.get("window_size"))

        if self.runner_config.get("maximize_window"):
            command.append("--maximize-window")

        if self.runner_config.get("disable_scrolling"):
            command.append("--disable-scrolling")

        if self.runner_config.get("hide_cursor"):
            command.append("--hide-cursor")

        if self.runner_config.get("open_links"):
            command.append("--open-links")

        if self.runner_config.get("devtools"):
            command.append("--devtools")

        return {'command': command, 'env': self.get_env()}
