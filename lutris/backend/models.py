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


@dataclass(frozen=True)
class LibraryGame:
    """A row of a library view: a game in the library, or in a service's view, a game the
    service offers, with what the library knows about it if it was installed from there."""

    # Unique in its view: the game's id, or in a service's view, the service's id for it
    id: str
    # The library's id for the game, if it's in the library
    game_id: str | None
    name: str
    # The name to sort by, if it's not the name itself
    sortname: str
    slug: str
    year: int | None
    runner: str | None
    # The runner's name for people
    runner_name: str | None
    platform: str | None
    installed: bool
    # When the game was installed and last played, in seconds since the epoch, as recorded
    installed_at: int | None
    lastplayed: int | None
    # Hours played
    playtime: float | None
    service: str | None
    # The service's id for a library game installed from one
    service_id: str | None
    # The service's id for a game in its view
    appid: str | None
    # The icon the service provided, for some services
    icon: str | None
