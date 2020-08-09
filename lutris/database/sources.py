import os

from lutris import settings
from lutris.database import sql
from lutris.util import system
from lutris.util.log import logger

PGA_DB = settings.PGA_DB


def add_source(uri):
    sql.db_insert(PGA_DB, "sources", {"uri": uri})


def delete_source(uri):
    sql.db_delete(PGA_DB, "sources", "uri", uri)


def read_sources():
    with sql.db_cursor(PGA_DB) as cursor:
        rows = cursor.execute("select uri from sources")
        results = rows.fetchall()
    return [row[0] for row in results]


def write_sources(sources):
    db_sources = read_sources()
    for uri in db_sources:
        if uri not in sources:
            sql.db_delete(PGA_DB, "sources", "uri", uri)
    for uri in sources:
        if uri not in db_sources:
            sql.db_insert(PGA_DB, "sources", {"uri": uri})


def check_for_file(game, file_id):
    for source in read_sources():
        if source.startswith("file://"):
            source = source[7:]
        else:
            protocol = source[:7]
            logger.warning("PGA source protocol %s not implemented", protocol)
            continue
        if not system.path_exists(source):
            logger.info("PGA source %s unavailable", source)
            continue
        game_dir = os.path.join(source, game)
        if not system.path_exists(game_dir):
            continue
        for game_file in os.listdir(game_dir):
            game_base, _ext = os.path.splitext(game_file)
            if game_base == file_id:
                return os.path.join(game_dir, game_file)
    return False
