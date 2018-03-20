# -*- coding: utf-8 -*-

import os
import string
import shlex
from urllib.parse import urlparse

from lutris.runners.runner import Runner
from lutris.util import datapath
from lutris import pga, settings

DEFAULT_ICON = os.path.join(datapath.get(), 'media/default_icon.png')


class web(Runner):
    human_name = "Web"
    description = _("Runs web based games")
    platforms = ["Web"]
    game_options = [
        {
            "option": "main_file",
            "type": "string",
            "label": _("Full URL or HTML file path"),
            'help': _(
                "The full address of the game's web page or path to a HTML file."
            )
        }
    ]
    runner_options = [
        {
            "option": "fullscreen",
            "label": _("Open in fullscreen"),
            "type": "bool",
            "default": False,
            'help': _("Launch the game in fullscreen.")
        },
        {
            "option": "maximize_window",
            "label": _("Open window maximized"),
            "type": "bool",
            "default": False,
            'help': _("Maximizes the window when game starts.")
        },
        {
            'option': 'window_size',
            'label': _('Window size'),
            'type': 'choice_with_entry',
            'choices': ["640x480", "800x600", "1024x768",
                        "1280x720", "1280x1024", "1920x1080"],
            'default': '800x600',
            'help': _("The initial size of the game window when not opened.")
        },
        {
            "option": "disable_resizing",
            "label": _("Disable window resizing (disables fullscreen and maximize)"),
            "type": "bool",
            "default": False,
            'help': _("You can't resize this window.")
        },
        {
            "option": "frameless",
            "label": _("Borderless window"),
            "type": "bool",
            "default": False,
            'help': _("The window has no borders/frame.")
        },
        {
            "option": "disable_menu_bar",
            "label": _("Disable menu bar and default shortcuts"),
            "type": "bool",
            "default": False,
            'help': _(
                "This also disables default keyboard shortcuts, "
                "like copy/paste and fullscreen toggling."
            )
        },
        {
            "option": "disable_scrolling",
            "label": _("Disable page scrolling and hide scrollbars"),
            "type": "bool",
            "default": False,
            'help': _("Disables scrolling on the page.")
        },
        {
            "option": "hide_cursor",
            "label": _("Hide mouse cursor"),
            "type": "bool",
            "default": False,
            'help': _(
                "Prevents the mouse cursor from showing "
                "when hovering above the window."
            )
        },
        {
            'option': 'open_links',
            'label': _('Open links in game window'),
            'type': 'bool',
            'default': False,
            'help': _(
                "Enable this option if you want clicked links to open inside the "
                "game window. By default all links open in your default web browser."
            )
        },
        {
            "option": "remove_margin",
            "label": _("Remove default <body> margin & padding"),
            "type": "bool",
            "default": False,
            'help': _(
                "Sets margin and padding to zero "
                "on &lt;html&gt; and &lt;body&gt; elements."
            )
        },
        {
            "option": "enable_flash",
            "label": _("Enable Adobe Flash Player"),
            "type": "bool",
            "default": False,
            'help': _("Enable Adobe Flash Player.")
        },
        {
            "option": "devtools",
            "label": _("Debug with Developer Tools"),
            "type": "bool",
            "default": False,
            'help': _("Let's you debug the page."),
            'advanced': True
        },
        {
            'option': 'external_browser',
            'label': _('Open in web browser (old behavior)'),
            'type': 'bool',
            'default': False,
            'help': _("Launch the game in a web browser.")
        },
        {
            'option': 'custom_browser_executable',
            'label': _("Custom web browser executable"),
            'type': 'file',
            'help': _(
                'Select the executable of a browser on your system.'
                'If left blank, Lutris will launch your default browser (xdg-open).'
            )
        },
        {
            'option': 'custom_browser_args',
            'label': _("Web browser arguments"),
            'type': 'string',
            'default': '"$GAME"',
            'help': _(
                'Command line arguments to pass to the executable.'
                '$GAME or $URL inserts the game url.'
                'For Chrome/Chromium app mode use: --app="$GAME"'
            )
        }
    ]
    system_options_override = [
        {
            'option': 'disable_runtime',
            'default': True,
        }
    ]
    runner_executable = 'web/electron/electron'

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
                    'text': _(
                        "The web address is empty,"
                        "verify the game's configuration."
                    ), }

        # check if it's an url or a file
        isUrl = urlparse(url).scheme is not ''

        if not isUrl:
            if not os.path.exists(url):
                nourl_message = {
                    'error': 'CUSTOM',
                    'text': _(
                        "The file {filepath} does not exist, "
                        "verify the game's configuration."
                    ).format(filepath=url),
                }

                return nourl_message
            url = 'file://' + url

        game_data = pga.get_game_by_field(self.config.game_config_id, 'configpath')

        # keep the old behavior from browser runner, but with support for extra arguments!
        if self.runner_config.get("external_browser"):
            # is it possible to disable lutris runtime here?
            browser = self.runner_config.get('custom_browser_executable') or 'xdg-open'

            args = self.runner_config.get('custom_browser_args')
            if args == '':
                args = '"$GAME"'
            arguments = string.Template(args).safe_substitute({
                'GAME': url,
                'URL': url
            })

            command = [browser]

            for arg in shlex.split(arguments):
                command.append(arg)

            return {'command': command}

        icon = datapath.get_icon_path(game_data.get('slug'))
        if not os.path.exists(icon):
            icon = DEFAULT_ICON

        command = [self.get_executable()]

        command.append(os.path.join(settings.RUNNER_DIR,
                                    'web/electron/resources/app.asar'))

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

        if self.runner_config.get("remove_margin"):
            command.append("--remove-margin")

        if self.runner_config.get("devtools"):
            command.append("--devtools")

        return {'command': command, 'env': self.get_env(False)}
