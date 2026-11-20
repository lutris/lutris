"""Calls about the games services (Steam, GOG, ...) offer."""

from lutris.backend.models import ServiceGameInfo, ServiceInfo
from lutris.database import games as games_db
from lutris.database.services import ServiceGameCollection
from lutris.services import get_enabled_services


async def list_services() -> list[ServiceInfo]:
    """Return the services the user has enabled, in alphabetical order of their names."""
    services = [
        ServiceInfo(service_id, str(service_class.name), bool(service_class.online))
        for service_id, service_class in get_enabled_services().items()
    ]
    return sorted(services, key=lambda s: s.name.casefold())


async def list_service_games(service: str | None = None, installed_only: bool = False) -> list[ServiceGameInfo]:
    """Return the games one service offers, or all services if service is None, with
    whether each is installed in the library."""
    installed = {
        (game["service"], game.get("service_id"))
        for game in games_db.get_games(filters={"installed": 1})
        if not service or game["service"] == service
    }
    if service:
        db_games = ServiceGameCollection.get_for_service(service)
    else:
        db_games = ServiceGameCollection.get_service_games()
    games = [
        ServiceGameInfo(
            id=str(db_game["id"]),
            name=str(db_game["name"]),
            slug=str(db_game["slug"]),
            service=str(db_game["service"]),
            appid=str(db_game["appid"]),
            installed=(db_game["service"], db_game["appid"]) in installed,
            details=str(db_game["details"]) if db_game.get("details") else None,
        )
        for db_game in db_games
    ]
    return [game for game in games if game.installed] if installed_only else games
