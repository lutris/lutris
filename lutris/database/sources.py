import os
from typing import List, Union

from lutris import settings
from lutris.database import sql
from lutris.util import system
from lutris.util.log import logger


def add_source(uri: str) -> None:
    sql.db_insert(settings.DB_PATH, "sources", {"uri": uri})


def delete_source(uri: str) -> None:
    sql.db_delete(settings.DB_PATH, "sources", "uri", uri)


def read_sources() -> List[str]:
    with sql.db_cursor(settings.DB_PATH) as cursor:
        rows = cursor.execute("select uri from sources")
        results = rows.fetchall()
    return [row[0] for row in results]


def write_sources(sources: List[str]) -> None:
    db_sources = read_sources()
    for uri in db_sources:
        if uri not in sources:
            sql.db_delete(settings.DB_PATH, "sources", "uri", uri)
    for uri in sources:
        if uri not in db_sources:
            sql.db_insert(settings.DB_PATH, "sources", {"uri": uri})


def check_for_file(game: str, file_id: str) -> Union[str, bool]:
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
