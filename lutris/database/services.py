from typing import Dict, List, Optional

from lutris import settings
from lutris.database import sql
from lutris.util.log import logger


class ServiceGameCollection:
    @classmethod
    def get_service_games(cls, searches=None, filters=None, excludes=None, sorts=None) -> List[Dict]:
        return sql.filtered_query(
            settings.DB_PATH, "service_games", searches=searches, filters=filters, excludes=excludes, sorts=sorts
        )

    @classmethod
    def get_for_service(cls, service: Optional[str]):
        if not service:
            raise ValueError("No service provided")
        return sql.filtered_query(settings.DB_PATH, "service_games", filters={"service": service})

    @classmethod
    def get_game(cls, service: Optional[str], appid: Optional[str]) -> Optional[Dict]:
        """Return a single game referred by its appid"""
        if not service:
            raise ValueError("No service provided")
        if not appid:
            raise ValueError("No appid provided")
        results = sql.filtered_query(settings.DB_PATH, "service_games", filters={"service": service, "appid": appid})
        if not results:
            return None
        if len(results) > 1:
            logger.warning("More than one game found for %s on %s", appid, service)
        return results[0]
