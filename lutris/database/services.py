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
    def link_service_game(cls, service: str, appid: str, lutris_slug: str) -> None:
        """Update a service game to point to a Lutris game slug."""
        sql.db_update(
            settings.DB_PATH,
            "service_games",
            {"lutris_slug": lutris_slug},
            conditions={"appid": appid, "service": service},
        )

    @classmethod
    def link_lutris_game(cls, service: str, appid: str, lutris_game_id: str) -> None:
        """Update a Lutris game to point to a service game."""
        sql.db_update(
            settings.DB_PATH,
            "games",
            {"service": service, "service_id": appid},
            conditions={"id": lutris_game_id},
        )
