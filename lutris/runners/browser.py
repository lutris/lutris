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

""" Runner for browser games """

from lutris.runners.runner import Runner


# pylint: disable=C0103
class browser(Runner):
    """Runner for browser games"""

    def __init__(self, settings=None):
        """Constructor"""
        super(browser, self).__init__()
        self.package = "x-www-browser"
        self.executable = "x-www-browser"
        self.machine = "Web Browser"
        self.description = "Run games in the browser"
        self.game_options = [{"option":"url", "type":"string", "label":"URL"}]
        self.runner_options = [{
            'option': 'browser',
            'type': "file_chooser",
            'label': "Web Browser"
        }]
        if settings:
            self.url = settings["game"]["url"]
            runner_settings = settings["browser"]
            self.browser_exec = runner_settings.get('browser', self.executable)

    def play(self):
        """Run a browser game"""
        command = [self.browser_exec, "\"%s\"" % self.url]
        return command
