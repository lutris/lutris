"""Set service ID for Steam games"""
from lutris import settings
from lutris.database.games import get_games, sql


def migrate():
    """Run migration"""
    for game in get_games():
        if not game.get("steamid"):
            continue
        if game["runner"] and game["runner"] != "steam":
            continue
        print("Migrating Steam game %s" % game["name"])
        sql.db_update(
            settings.PGA_DB,
            "games",
            {"service": "steam", "service_id": game["steamid"]},
            {"id": game["id"]}
        )
