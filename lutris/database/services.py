from collections.abc import Sequence
from typing import TypeAlias

from lutris import settings
from lutris.database import sql
from lutris.util.log import logger

DBServiceGame: TypeAlias = dict[str, str | int]


class ServiceGameCollection:
    @classmethod
    def get_service_games(
        cls,
        searches: dict[str, str] | None = None,
        filters: sql.DBConditionsDict | None = None,
        excludes: sql.DBConditionsDict | None = None,
        sorts: Sequence[str] | None = None,
    ) -> list[DBServiceGame]:
        return sql.filtered_query(
            settings.DB_PATH, "service_games", searches=searches, filters=filters, excludes=excludes, sorts=sorts
        )

    @classmethod
    def get_for_service(cls, service: str) -> list[DBServiceGame]:
        if not service:
            raise ValueError("No service provided")
        return sql.filtered_query(settings.DB_PATH, "service_games", filters={"service": service})

    @classmethod
    def get_game(cls, service: str, appid: str) -> DBServiceGame | None:
        """Return a single game referred by its appid"""
        if not service:
            raise ValueError("No service provided")
        if not appid:
            raise ValueError("No appid provided")
        results: list[DBServiceGame] = sql.filtered_query(
            settings.DB_PATH, "service_games", filters={"service": service, "appid": appid}
        )
        if not results:
            return None
        if len(results) > 1:
            logger.warning("More than one game found for %s on %s", appid, service)
        return results[0]

    @classmethod
    def replace_for_service(cls, service: str, games: Sequence[DBServiceGame]) -> None:
        """Replace everything stored for a service with `games`, in a single transaction, so
        that it either all happens or nothing does. Each game is a row as returned by
        get_for_service(). The ids are not kept: they are rowids that another service may
        have been given in the meantime, and nothing refers to them."""
        if not service:
            raise ValueError("No service provided")
        with sql.db_cursor(settings.DB_PATH) as cursor:
            sql.cursor_execute(cursor, "delete from service_games where service=?", (service,))
            if games:
                columns = [column for column in games[0].keys() if column != "id"]
                placeholders = ", ".join("?" * len(columns))
                cursor.executemany(
                    "insert into service_games({0}) values ({1})".format(", ".join(columns), placeholders),
                    [tuple(game[column] for column in columns) for game in games],
                )
