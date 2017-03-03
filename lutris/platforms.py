"""Generic platform functions."""

from lutris import pga
from lutris.runners import import_runner


def get_installed(sort=True):
    """Return a list of installed platforms (strings)."""
    installed_platforms = []
    all_games = pga.get_games(filter_installed=True)
    for game in all_games:
        if not game.get('runner'):
            continue
        platform = game.get('platform')
        if not platform:
            runner = import_runner(game.get('runner'))()

            if runner and runner.is_installed():
                platform = runner.platform
        if platform not in installed_platforms:
            installed_platforms.append(platform)
    return sorted(installed_platforms) if sort else installed_platforms
