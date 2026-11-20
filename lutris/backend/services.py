"""Calls about the games services (Steam, GOG, ...) offer."""

import asyncio
from dataclasses import dataclass
from gettext import gettext as _

from lutris import settings
from lutris.backend.models import ServiceGameInfo, ServiceInfo
from lutris.backend.store_login import login_input
from lutris.database import games as games_db
from lutris.database.services import ServiceGameCollection
from lutris.exceptions import LutrisError
from lutris.services import SERVICES, get_enabled_services
from lutris.services.base import AuthTokenExpiredError, BaseService, OnlineService


@dataclass(frozen=True)
class SourceStatus:
    name: str
    online: bool
    signed_in: bool
    can_sign_in: bool


@dataclass(frozen=True)
class SourceLauncher:
    id: str
    name: str
    directory: str


def _get_service(service_id: str) -> BaseService:
    service = SERVICES.get(service_id)
    if service is None:
        raise LutrisError(_("This game source is unavailable."))
    return service()


async def get_source_status(service_id: str) -> SourceStatus:
    return await asyncio.to_thread(_get_source_status, service_id)


async def list_source_launchers(service_id: str) -> tuple[SourceLauncher, ...]:
    launchers = await asyncio.to_thread(_get_service(service_id).list_launchers)
    return tuple(SourceLauncher(item["id"], item["name"], item.get("directory") or "") for item in launchers)


async def set_source_launcher(service_id: str, game_id: str) -> None:
    if not any(launcher.id == game_id for launcher in await list_source_launchers(service_id)):
        raise LutrisError(_("This launcher is no longer available."))
    settings.write_setting(f"{service_id}_launcher", game_id, section="services")


def _get_source_status(service_id: str) -> SourceStatus:
    service = _get_service(service_id)
    online = isinstance(service, OnlineService)
    signed_in = isinstance(service, OnlineService) and bool(service.is_authenticated())
    return SourceStatus(str(service.name), online, signed_in, login_input(service_id) is not None)


async def sync_source(service_id: str) -> None:
    await asyncio.to_thread(_sync_source, service_id)


def _sync_source(service_id: str) -> None:
    service = _get_service(service_id)
    if isinstance(service, OnlineService) and not service.is_authenticated():
        raise LutrisError(_("Sign in to sync %s.") % service.name)
    try:
        service.reload()
    except AuthTokenExpiredError:
        if isinstance(service, OnlineService):
            service.logout()
        raise LutrisError(_("Your session expired. Sign in again to sync %s.") % service.name) from None


async def disconnect_source(service_id: str) -> None:
    await asyncio.to_thread(_disconnect_source, service_id)


def _disconnect_source(service_id: str) -> None:
    service = _get_service(service_id)
    if isinstance(service, OnlineService):
        service.logout()


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
    if service == "flathub":
        return []
    installed = {
        (game["service"], game.get("service_id"))
        for game in games_db.get_games(filters={"installed": 1})
        if not service or game["service"] == service
    }
    if service:
        db_games = ServiceGameCollection.get_for_service(service)
    else:
        db_games = ServiceGameCollection.get_service_games(excludes={"service": "flathub"})
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
