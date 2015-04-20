from lutris.util.log import logger
from lutris.config import LutrisConfig

if __name__ == "__main__":
    lc = LutrisConfig(runner_slug="wine")
    logger.error("system level config : ")
    print lc.system_level
    print "runner level config : "
    print lc.runner_level
    print "global config"
    print lc.config

    print ("*****************")
    print ("* testing games *")
    print ("*****************")

    lc = LutrisConfig(game_slug="wine-Ghostbusters")
    print "system level config : "
    print lc.system_level
    print ("-----------------------")
    print "runner level config : "
    print lc.runner_level
    print ("-----------------------")
    print "game level config :"
    print lc.game_level
    print ("-----------------------")
    print "global config"
    print lc.config
