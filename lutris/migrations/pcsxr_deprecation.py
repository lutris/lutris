from lutris.pga import sql, PGA_DB
from lutris.game import Game


def migrate():
    pcsxr_game_ids = sql.db_query(PGA_DB, "select id from games where runner='pcsxr'")
    for game_id in pcsxr_game_ids:
        game = Game(game_id["id"])
        main_file = game.config.raw_game_config.get("iso")
        game.config.game_level = {
            "game": {"core": "pcsx_rearmed", "main_file": main_file}
        }
        game.config.save()
    sql.db_update(PGA_DB, "games", {"runner": "libretro"}, where=("runner", "pcsxr"))
