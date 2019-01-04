from lutris.util import xdgshortcuts
from lutris import pga
from lutris.game import Game


def migrate():
    for game in [Game(pga_game["id"]) for pga_game in pga.get_games()]:
        if xdgshortcuts.desktop_launcher_exists(game.slug, game.id):
            xdgshortcuts.create_launcher(game.slug, game.id, game.name, desktop=True)
        if xdgshortcuts.menu_launcher_exists(game.slug, game.id):
            xdgshortcuts.create_launcher(game.slug, game.id, game.name, menu=True)
