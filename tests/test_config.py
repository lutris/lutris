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

from lutris.util.log import logger
from lutris.config import LutrisConfig

if __name__ == "__main__":
    lc = LutrisConfig(runner="wine")
    logger.error("system config : ")
    print lc.system_config
    print "runner config : "
    print lc.runner_config
    print "global config"
    print lc.config

    print ("*****************")
    print ("* testing games *")
    print ("*****************")

    lc = LutrisConfig(game="wine-Ghostbusters")
    print "system config : "
    print lc.system_config
    print ("-----------------------")
    print "runner config : "
    print lc.runner_config
    print ("-----------------------")
    print "game config :"
    print lc.game_config
    print ("-----------------------")
    print "global config"
    print lc.config
