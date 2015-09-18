# -*- coding: utf-8 -*-
"""Runner for Desura"""

import os
import subprocess

from lutris.runners.runner import Runner
from lutris.util.log import logger
from lutris.util import system
from lutris import settings


class desura(Runner):
    """Run Desura games (or mods, or tools)"""
    human_name = "Desura"
    platform = "Desura"
    package = "desura"
    runnable_alone = True
    game_options = [
        {
            "option": "appid",
            "label": "Application ID",
            "type": "string",
            'help': ("The application ID can be retrieved from the game's "
                     "page at desura.com. Example: dungeons-of-dremor is the "
                     "app ID in: \n"
                     "http://desura.com/games/<b>dungeons-of-dredmor</b>")
        },
        {
            'option': 'section',
            'label': "Section",
            'type': 'choice',
            'choices': [('games', 'games'),
                        ('downloads', 'downloads'),
                        ('mods', 'mods'),
                        ('tools', 'tools')],
            'default': 'games',
            'help': ("This corresponds to the download's section at "
                     "desura.com. \n"
                     "Example: <b>games</b> is the section in: \n"
                     "http://desura.com/<b>games</b>/teenagent")
        },
    ]
    runner_options = [
        {
            "option": "desura_path",
            "label": "Custom Desura location",
            "type": "string",
            'help': ("Leave blank to use the installation of Desura bundled "
                     "with Lutris.")
        }
    ]

    @property
    def browse_dir(self):
        """Return the path to open with the Browse Files action."""
        if not self.is_installed():
            installed = self.install_dialog()
            if not installed:
                return False
        return self.game_path

    @property
    def game_path(self):
        """Return game dir or Desura's main dir"""
        appid = self.game_config.get('appid')
        if os.path.exists(self.get_installed_app_path(appid)):
            return self.get_installed_app_path(appid)
        if os.path.exists(self.get_common_path()):
            return self.get_common_path()

    def get_desura_url(self, action, section, appid):
        """Return link for Desura game"""
        section_choices = (k[0] for k in self.game_options[1]['choices'])
        if section not in section_choices:
            section = 'games'
        url = ("desura://%(action)s/%(section)s/%(appid)s/" % locals())
        logger.debug("Desura url: %s", url)
        return url

    def get_path(self):
        return (self.runner_config.get('desura_path')
                or os.path.join(settings.RUNNER_DIR, "desura"))

    def get_executable(self):
        return os.path.join(self.get_path(), "desura")

    def get_common_path(self):
        return os.path.join(self.get_path(), "common")

    def get_installed_app_path(self, appid):
        return os.path.join(self.get_common_path(), appid)

    def install(self):
        self.logger.debug("Installing desura")
        if self.arch == "x64":
            tarball = "desura-x86_64.tar.gz"
        else:
            tarball = "desura-i686.tar.gz"
        self.download_and_extract(tarball,
                                  settings.RUNNER_DIR,
                                  source_url="http://www.desura.com/")
        if not self.is_installed():
            return False
        subprocess.Popen([self.get_executable()], cwd=os.path.expanduser('~'))

    def is_installed(self):
        return bool(system.find_executable(self.get_executable()))

    def play(self):
        return {"command": [
            self.get_executable(),
            self.get_desura_url("launch",
                                self.game_config.get('section'),
                                self.game_config.get('appid'))
        ]}
