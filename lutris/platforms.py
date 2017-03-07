"""Generic platform functions."""

from lutris import pga
from lutris import runners
from lutris.game import Game

# gets populated by load_platforms()
__all__ = {}


def load_platforms():
    for runner_name in runners.__all__:
        runner = runners.import_runner(runner_name)()
        platforms = runner.platforms

        # convert platforms into a 2D tuple
        if type(platforms) is str:
            platforms = (platforms,)
        if (isinstance(platforms, tuple) or isinstance(platforms, list)) and not isinstance(platforms[0], tuple):
            platforms = (platforms,)

        for platform in platforms:
            prefix = ''
            for p in platform:
                p = prefix + p
                prefix = p + ' / '
                if not __all__.get(p):
                    __all__[p] = []
                __all__.get(p).append(runner_name)


def get_active(sort=True):
    """Return a list of platforms with games (strings)."""
    active_platforms = []
    all_games = pga.get_games(filter_installed=True, select='id')
    for game in all_games:
        # load game info
        game = Game(id=game.get('id'))
        platform = game.get_platform(string=False)
        if not platform:
            continue
        # convert to tuple if string
        if isinstance(platform, str):
            platform = (platform,)
        prefix = ''

        for p in platform:
            p = prefix + p
            prefix = p + ' / '
            if p not in active_platforms:
                active_platforms.append(p)
    return sorted(active_platforms) if sort else active_platforms


load_platforms()
