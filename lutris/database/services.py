from lutris import settings
from lutris.database import sql
from lutris.util.log import logger

PGA_DB = settings.PGA_DB


class ServiceGameCollection:

    @classmethod
    def get_for_service(cls, service):
        if not service:
            raise ValueError("No service provided")
        return sql.filtered_query(PGA_DB, "service_games", filters={"service": service})

    @classmethod
    def get_game(cls, service, appid):
        """Return a single game refered by its appid"""
        if not service:
            raise ValueError("No service provided")
        if not appid:
            raise ValueError("No appid provided")
        results = sql.filtered_query(PGA_DB, "service_games", filters={"service": service, "appid": appid})
        if not results:
            return
        if len(results) > 1:
            logger.warning("More than one game found for %s on %s", appid, service)
        return results[0]
