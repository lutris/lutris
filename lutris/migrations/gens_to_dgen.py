from lutris import pga


def migrate():
    pga.sql.db_update(pga.PGA_DB, "games", {"runner": "dgen"}, ("runner", "gens"))
