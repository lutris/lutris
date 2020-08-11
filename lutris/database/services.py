from lutris import settings
from lutris.database import sql

PGA_DB = settings.PGA_DB


class ServiceGameCollection:

    @classmethod
    def get_for_service(cls, service):
        return sql.db_select(PGA_DB, "service_games", condition=("service", service))
