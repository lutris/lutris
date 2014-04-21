# -*- coding:Utf-8 -*-
###############################################################################
## Lutris
##
## Copyright (C) 2009 Mathieu Comandon strycore@gmail.com
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
###############################################################################

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
         link = "desura://%(action)s/%(sitearea)s/%(siteareaid)s/%(optional)s" % locals()
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
        runner = self.__class__.__name__
        runner_config = self.settings.get(runner) or {}
        return runner_config.get('desura_path', os.path.join(settings.RUNNER_DIR, "desura"))

    def get_executable(self):
        return os.path.join(self.get_path(), "desura")

    def get_common_path(self):
        return os.path.join(self.get_path(), "common")

    def get_installed_app_path(self, siteareaid):
        return os.path.join(self.get_common_path(), siteareaid)

    @property
    def browse_dir(self):
        """ Browse Desura game dir (or specific game dir) """
        siteareaid = self.settings.get("game").get("siteareaid")
        if os.path.exists(self.get_installed_app_path(siteareaid)):
            return self.get_installed_app_path(siteareaid)
        if os.path.exists(self.get_common_path()):
            return self.get_common_path()
        return None

    def install(self):
        self.logger.debug("Installing desura")
        if self.arch == "x64":
            tarball = "desura-x86_64.tar.gz"
        else:
            tarball = "desura-i686.tar.gz"
        self.download_and_extract(tarball, settings.RUNNER_DIR, source_url="http://www.desura.com/")
        subprocess.Popen([self.get_executable()])

    def is_installed(self):
        return bool(system.find_executable(self.get_executable()))

    def play(self):
        settings = self.settings.get("game")
        logger.debug("Calling desura")
        return {"command": [self.get_executable(), get_desura_link("install", settings.get("sitearea"), settings.get("siteareaid"), settings.get("optional"))]}