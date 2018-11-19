from lutris.services import xdg
from lutris import pga
from lutris.game import Game


def migrate():
    for game in [Game(pga_game["id"]) for pga_game in pga.get_games()]:
        if xdg.desktop_launcher_exists(game.slug, game.id):
            xdg.create_launcher(game.slug, game.id, game.name, desktop=True)
        if xdg.menu_launcher_exists(game.slug, game.id):
            xdg.create_launcher(game.slug, game.id, game.name, menu=True)
