"""Migrate MESS games to MAME"""
# Lutris Modules
from lutris.game import Game
from lutris.pga import get_games


def migrate():
    """Run migration"""
    for pga_game in get_games():
        game = Game(pga_game["id"])
        if game.runner_name != "mess":
            continue
        if "mess" in game.config.game_level:
            game.config.game_level["mame"] = game.config.game_level.pop("mess")
        game.runner_name = "mame"
        game.save()
