from lutris import settings
from lutris.database import sql
from lutris.util.log import logger


class ServiceGameCollection:

    @classmethod
    def get_service_games(
        cls,
        searches=None,
        filters=None,
        excludes=None,
        sorts=None
    ):
        return sql.filtered_query(
            settings.PGA_DB,
            "service_games",
            searches=searches,
            filters=filters,
            excludes=excludes,
            sorts=sorts
        )

    @classmethod
    def get_for_service(cls, service):
        if not service:
            raise ValueError("No service provided")
        return sql.filtered_query(settings.PGA_DB, "service_games", filters={"service": service})

    @classmethod
    def get_game_by_field(cls, appid, service, field):
        """Query a service game based on a database field"""
        if not appid:
            raise ValueError("No game_slug provided")
        if not service:
            raise ValueError("No service provided")
        if field not in ("slug", "lutris_slug", "appid", "name"):
            raise ValueError("Can't query by field '%s'" % field)
        results = sql.filtered_query(settings.PGA_DB, "service_games", filters={field: appid, "service": service})
        if not results:
            return
        if len(results) > 1:
            logger.warning("More than one game found for %s on %s", appid, service)
        return results[0]

    @classmethod
    def get_game(cls, service, appid):
        """Return a single game referred by its appid"""
        logger.debug("Getting service game %s for %s", appid, service)
        if not service:
            raise ValueError("No service provided")
        if not appid:
            raise ValueError("No appid provided")
        results = sql.filtered_query(settings.PGA_DB, "service_games", filters={"service": service, "appid": appid})
        if not results:
            return
        if len(results) > 1:
            logger.warning("More than one game found for %s on %s", appid, service)
        return results[0]
