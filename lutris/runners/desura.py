# -*- coding: utf-8 -*-
"""Runner for Desura"""

import os
import subprocess

from lutris.runners.runner import Runner
from lutris.util.log import logger
from lutris.util import system
from lutris import settings


def get_desura_link(action, sitearea, siteareaid, optional):
    """ Return link for Desura app """
    if optional is None:
        link = "desura://%(action)s/%(sitearea)s/%(siteareaid)s/" % locals()
    else:
        link = ("desura://%(action)s/%(sitearea)s/%(siteareaid)s/%(optional)s"
                % locals())
    logger.debug("Desura link %s", link)
    return link


class desura(Runner):
    """ Runs Desura games (or mods, or tools) """
    platform = "Desura"
    package = "desura"
    game_options = [
        {
            "option": "sitearea",
            "label": "Site area (mods, games, download, tools)",
            "type": "string",
        },
        {
            "option": "siteareaid",
            "label": "Site area ID (name or id of the item based on moddb)",
            "type": "string",
        },
        {
            "option": "optional",
            "label": "Optional information (not required)",
            "type": "string",
        }
    ]
    runner_options = [
        {
            "option": "desura_path",
            "label": "Path to desura folder",
            "type": "string",
        }
    ]

    def get_path(self):
        return self.runner_config.get(
            'desura_path', os.path.join(settings.RUNNER_DIR, "desura")
        )

    def get_executable(self):
        return os.path.join(self.get_path(), "desura")

    def get_common_path(self):
        return os.path.join(self.get_path(), "common")

    def get_installed_app_path(self, siteareaid):
        return os.path.join(self.get_common_path(), siteareaid)

    def get_game_path(self):
        """ Browse Desura game dir (or specific game dir) """
        siteareaid = self.settings.get("game").get("siteareaid")
        if os.path.exists(self.get_installed_app_path(siteareaid)):
            return self.get_installed_app_path(siteareaid)
        if os.path.exists(self.get_common_path()):
            return self.get_common_path()

    def install(self):
        self.logger.debug("Installing desura")
        if self.arch == "x64":
            tarball = "desura-x86_64.tar.gz"
        else:
            tarball = "desura-i686.tar.gz"
        self.download_and_extract(tarball,
                                  settings.RUNNER_DIR,
                                  source_url="http://www.desura.com/")
        subprocess.Popen([self.get_executable()])

    def is_installed(self):
        return bool(system.find_executable(self.get_executable()))

    def play(self):
        settings = self.settings.get("game")
        return {"command": [
            self.get_executable(),
            get_desura_link("install",
                            settings.get("sitearea"),
                            settings.get("siteareaid"),
                            settings.get("optional"))
        ]}
