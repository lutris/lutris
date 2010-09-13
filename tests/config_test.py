import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lutris.config import LutrisConfig

if  __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logging.debug('logging enabled')
    lc = LutrisConfig(runner="wine")
    print "system config : "
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

