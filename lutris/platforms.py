"""Generic platform functions."""
from collections import defaultdict

from lutris import pga
from lutris import runners
from lutris.game import Game

# gets populated by _init_platforms()
__all__ = defaultdict(list)


def _init_platforms():
    for runner_name in runners.__all__:
        runner = runners.import_runner(runner_name)()
        for platform in runner.platforms:
            __all__[platform].append(runner_name)


def update_platforms():
    pga_games = pga.get_games(filter_installed=True)
    for pga_game in pga_games:
        if pga_game.get("platform") or not pga_game["runner"]:
            continue
        game = Game(game_id=pga_game["id"])
        game.set_platform_from_runner()
        game.save(metadata_only=True)


_init_platforms()
