from lutris.pga import PGA_DB, get_games
from lutris.game import Game
from lutris.util import sql
from lutris.util.log import logger



def migrate():
    for pga_game in get_games():
        game = Game(pga_game["id"])
        if not game.config:
            continue
        d9vk = game.config.raw_runner_config.get("d9vk")
        if not d9vk:
            continue
        game.config.raw_runner_config.pop("d9vk")
        game.config.runner_config.pop("d9vk")
        if "d9vk_version" in game.config.raw_runner_config:
            game.config.raw_runner_config.pop("d9vk_version")
            game.config.runner_config.pop("d9vk_version")
        game.config.raw_runner_config["dxvk"] = True
        game.config.runner_config["dxvk"] = True
        game.config.save()
        print("Migrated %s" % game)

