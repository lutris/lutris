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


@dataclass(frozen=True)
class ConfigChoice:
    label: str
    value: str


@dataclass(frozen=True)
class ConfigOptionInfo:
    """One option of a configuration form, evaluated against the configuration being edited."""

    # The config section the option belongs to: "game", "runner" or "system"
    section: str
    key: str
    # "label", "string", "bool", "range", "choice", "choice_with_entry", "choice_with_search",
    # "file", "multiple_file", "directory", "mapping" or "command_line"
    type: str
    label: str
    # The heading the option is grouped under, if any
    group: str
    help: str
    # A string, bool, int, list of strings (multiple_file) or dict of strings (mapping)
    value: object
    default: object
    # The default as people would read it, such as a choice's label
    default_label: str
    choices: tuple[ConfigChoice, ...]
    minimum: int | None
    maximum: int | None
    advanced: bool
    visible: bool
    enabled: bool
    # Whether this level of configuration sets the option, so it can be reset
    set_here: bool
    # Whether a lower level changed the option from its default
    changed_below: bool
    warning: str
    error: str


@dataclass(frozen=True)
class ConfigPage:
    section: str
    title: str
    # Explains how this page relates to the levels below it
    description: str
    options: tuple[ConfigOptionInfo, ...]


@dataclass(frozen=True)
class GameDetails:
    """What the library records about a game, as its configuration form edits it."""

    name: str
    sortname: str
    slug: str
    # Empty until a runner is chosen
    runner: str
    # As typed, so empty when unknown
    year: str
    # As people write it, such as "2 hours 30 minutes"
    playtime: str
    # Read only
    directory: str = ""
    config_path: str = ""


@dataclass(frozen=True)
class ConfigForm:
    """A game's, a runner's or the system's options being edited, until saved or closed."""

    id: str
    # "game", "runner" or "system"
    level: str
    title: str
    pages: tuple[ConfigPage, ...]
    show_advanced: bool
    # For a game: its details, and the runners it can use
    game: GameDetails | None = None
    runner_choices: tuple[ConfigChoice, ...] = ()


@dataclass(frozen=True)
class ArtworkSettings:
    """Where artwork comes from. The SteamGridDB API key itself is never handed out."""

    steamgriddb_key_set: bool
    # A key in LUTRIS_STEAMGRIDDB_API_KEY wins over the saved one, and can't be changed here
    steamgriddb_key_from_environment: bool
    # Where users create their SteamGridDB API key
    steamgriddb_key_page: str


@dataclass(frozen=True)
class GameArtworkImage:
    """One of a game's images: "cover", "banner" or "icon"."""

    kind: str
    # The file, if the game has this artwork
    path: str | None
    # Whether the user chose it, so it's kept until reset
    custom: bool


@dataclass(frozen=True)
class ArtworkChoice:
    """An image the user can choose for a game, such as one of SteamGridDB's."""

    url: str
    thumbnail_url: str
    width: int
    height: int


@dataclass(frozen=True)
class RuntimeComponentProgress:
    """A runtime component (umu, Winetricks...) being updated."""

    name: str
    status: str
    # None while the amount is unknown
    fraction: float | None
    finished: bool


@dataclass(frozen=True)
class RuntimeUpdateStatus:
    running: bool
    components: tuple[RuntimeComponentProgress, ...] = ()


@dataclass(frozen=True)
class SourceSetting:
    """A game source (service) the user can turn on or off."""

    id: str
    name: str
    description: str
    enabled: bool
    # Whether its games also appear in the library's Games view
    in_games_view: bool


@dataclass(frozen=True)
class StoragePaths:
    game_path: str
    # Empty when downloads aren't kept
    installer_cache_path: str
    installer_cache_message: str
    installer_cache_valid: bool
    bios_path: str
    bios_warning: str


@dataclass(frozen=True)
class SteamAccount:
    id: str
    name: str
    active: bool


@dataclass(frozen=True)
class SystemInfoSection:
    title: str
    items: tuple[tuple[str, str], ...]
