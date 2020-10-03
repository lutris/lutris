"""Migrate MESS games to MAME"""
from lutris.database.games import get_games
from lutris.game import Game


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
