"""The plain data the backend's calls return. Each is a frozen dataclass of
JSON-compatible values, so that it can cross a process boundary as it is."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GameInfo:
    """A game in the library."""

    id: str
    name: str
    slug: str
    runner: str | None
    platform: str | None
    year: int | None
    directory: str | None
    installed: bool
    # Hours played
    playtime: float | None
    # When the game was last played, in seconds since the epoch
    lastplayed: int | None
    service: str | None
    service_id: str | None
    installer_slug: str | None
    # The cover art's file, if it has been downloaded
    cover_path: str | None


@dataclass(frozen=True)
class ServiceGameInfo:
    """A game a service (Steam, GOG, ...) offers, which may not be in the library."""

    id: str
    name: str
    slug: str
    service: str
    appid: str
    installed: bool
    # The service's own details about the game, as JSON
    details: str | None


@dataclass(frozen=True)
class SteamGameInfo:
    """A game found in a local Steam library."""

    appid: str
    name: str | None
    states: tuple[str, ...]
