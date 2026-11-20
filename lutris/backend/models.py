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
class LibraryArtwork:
    """Local artwork for a library row, with an optional desktop icon name."""

    cover_path: str | None
    banner_path: str | None
    icon_path: str | None
    icon_name: str | None = None


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
    # Resolved only when the query requests artwork
    artwork: LibraryArtwork | None = None


@dataclass(frozen=True)
class SavedSearchInfo:
    """A search saved under a name, which the library can show as a view."""

    name: str
    search: str


@dataclass(frozen=True)
class RunnerInfo:
    """A runner: its id, and its name for people."""

    name: str
    human_name: str


@dataclass(frozen=True)
class ServiceInfo:
    """A service (GOG, Steam...) whose games the library can show; an online one needs
    the user to log in first."""

    id: str
    name: str
    online: bool


@dataclass(frozen=True)
class InstallerChoice:
    """An install script a game can be installed with."""

    # Identifies the script in its catalog
    id: str
    version: str
    runner: str
    # The runner's name for people
    runner_name: str
    description: str
    notes: str
    credits: str


@dataclass(frozen=True)
class InstallerCatalog:
    """The install scripts found for a game. The backend keeps the scripts themselves,
    so a frontend refers to one by the catalog's id and the choice's id."""

    id: str
    game_name: str
    game_slug: str
    choices: tuple[InstallerChoice, ...]


@dataclass(frozen=True)
class InstallerSelection:
    """What installing with a chosen script involves, checked before anything runs."""

    catalog_id: str
    choice_id: str
    game_name: str
    version: str
    # Whether the script installs into a folder of its own, which the user may choose
    creates_game_folder: bool
    # Where the game goes unless the user chooses otherwise; empty if the script decides
    default_directory: str
    # The runners installed before the script runs, by their names for people
    runners_to_install: tuple[str, ...]
    # Set when the script needs another game installed first, which must happen
    # before this script can be used
    required_game_slug: str | None = None


@dataclass(frozen=True)
class InstallerFileInfo:
    """A file an installation needs, and how it will be provided."""

    id: str
    label: str
    # Where the script says the file comes from, for people (a URL, or a hint for the user)
    hint: str
    # Extra details, such as the file's size
    details: str
    # The sources the file can come from: "download", "pga" (the cache) or "user"
    providers: tuple[str, ...]
    provider: str
    # The file the user chose, for the "user" provider
    user_path: str
    # Whether the file can be fetched from its provider as things are
    ready: bool
    # "pending", "downloading", "available", "failed" or "cancelled"
    state: str
    fraction: float
    progress_text: str
    error: str


@dataclass(frozen=True)
class InstallerExtraInfo:
    """Extra content (manuals, soundtracks...) a service offers with a game."""

    id: str
    source: str
    label: str


@dataclass(frozen=True)
class InstallerMenuOption:
    id: str
    label: str


@dataclass(frozen=True)
class InstallationInfo:
    """A snapshot of an installation in progress, sent with INSTALLATION_CHANGED."""

    id: str
    game_name: str
    # "preparing", "extras", "files", "downloading", "installing", "menu", "disc",
    # "cancelling", "finished", "failed" or "cancelled"
    stage: str
    # Whether the installation is still going, rather than finished, failed or cancelled
    running: bool
    status: str
    # None hides the progress, and a negative fraction means busy without a known amount
    progress: float | None
    progress_text: str
    extras: tuple[InstallerExtraInfo, ...] = ()
    files: tuple[InstallerFileInfo, ...] = ()
    menu_options: tuple[InstallerMenuOption, ...] = ()
    menu_preselect: str = ""
    disc_requires: str = ""
    disc_can_eject: bool = False
    # Whether installer commands have written output, which get_installation_log returns
    has_log: bool = False
    # Whether cancelling can remove the folder the installation created
    can_remove_files: bool = False
    # The installed game, once finished
    game_id: str = ""
    error_details: str = ""
