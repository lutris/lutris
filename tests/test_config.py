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
