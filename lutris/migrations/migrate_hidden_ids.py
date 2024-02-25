"""Move hidden games from settings to database"""
from lutris import settings
from lutris.game import Game


def get_hidden_ids():
    """Return a list of game IDs to be excluded from the library view"""
    # Load the ignore string and filter out empty strings to prevent issues
    ignores_raw = settings.read_setting("library_ignores").split(",")
    return [ignore.strip() for ignore in ignores_raw if ignore]


def migrate():
    """Run migration"""
    try:
        game_ids = get_hidden_ids()
    except:
        print("Failed to read hidden game IDs")
        return []
    for game_id in game_ids:
        game = Game(game_id)
        game.mark_as_hidden(True)
    settings.write_setting("library_ignores", "", section="lutris")
