"""Generic platform functions."""

from lutris import pga
from lutris.runners import import_runner


def get_installed(sort=True):
    """Return a list of installed platforms (strings)."""
    used_platforms = []
    all_games = pga.get_games(filter_installed=True)
    for game in all_games:
        if not game.get('runner'):
            continue
        platform = game.get('platform')
        if not platform:
            runner = import_runner(game.get('runner'))()

            if runner:
                platform = runner.platform
        if platform and platform not in used_platforms:
            used_platforms.append(platform)
    return sorted(used_platforms) if sort else used_platforms
