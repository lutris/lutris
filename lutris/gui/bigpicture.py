"""Big Picture mode: a fullscreen, controller-friendly view of the library.

The interface itself is a separate program (see the bigpicture directory at the
top of the source tree). Lutris starts it as a child process, hides its own
window, and talks to it over the child's standard input and output with one
JSON object per line. Lutris stays in charge of everything that matters: it
sends the library and the state of the games, and it carries out what the user
asks for in there - launching and stopping games, marking favorites, and coming
back to the desktop interface when Big Picture mode is left.
"""

import json
import os
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from gettext import gettext as _
from typing import TYPE_CHECKING, Any

from gi.repository import Gio, GLib

from lutris import settings
from lutris.database import categories as categories_db
from lutris.database import games as games_db
from lutris.exceptions import MissingExecutableError
from lutris.game import (
    GAME_INSTALLED,
    GAME_LAUNCH_STATUS,
    GAME_START,
    GAME_STARTED,
    GAME_STOPPED,
    GAME_UPDATED,
    Game,
)
from lutris.gui.dialogs.delegates import LaunchUIDelegate
from lutris.gui.views.store_item import StoreItem, sanitize_timestamp
from lutris.gui.widgets import NotificationRegistration
from lutris.runners import get_runner_human_name, import_runner
from lutris.runners.steam import get_steam_pid
from lutris.services.base import LutrisCoverart
from lutris.util import datapath, system
from lutris.util.log import logger
from lutris.util.strings import get_formatted_playtime

if TYPE_CHECKING:
    from lutris.gui.application import LutrisApplication

EXECUTABLE_NAME = "lutris-bigpicture"

# The exit status with which the interface says that the user asked to quit
# Lutris altogether, rather than just to leave Big Picture mode.
EXIT_QUIT_LUTRIS = 3

# The setting that holds the ID of the selected navigation sound pack; unset
# means the default pack, and "off" no sounds at all.
SOUND_PACK_SETTING = "bigpicture_sound_pack"

# The setting that says whether Big Picture mode opens with its animation of
# the Lutris icon; it does unless this has been switched off.
SPLASH_SETTING = "bigpicture_start_animation"

# The app ID of the Steam client itself, which every Steam has and which has
# no controller layout: told to use it, Steam leaves the controller alone.
STEAM_CLIENT_APPID = 7

# The app ID that has Steam go back to choosing the layout by itself.
STEAM_NO_FORCED_APPID = 0

# How often to check, in seconds, that Steam still leaves the controller alone.
STEAM_INPUT_CHECK_INTERVAL = 5

# How long, in seconds, Steam gets to take a request; it normally hands it to
# the Steam that is running and returns at once.
STEAM_REQUEST_TIMEOUT = 10

# How long, in seconds, leaving Big Picture mode waits for Steam to be told
# to take the controller back, which is a little longer than one request.
STEAM_RELEASE_TIMEOUT = 15

# How long to wait for further changes before sending the library again; a
# single action can update a game several times over. In milliseconds.
LIBRARY_UPDATE_DELAY = 300

# How often to check whether Lutris has finished updating its components, in
# milliseconds.
COMPONENT_UPDATE_POLL_DELAY = 500


def find_big_picture_executable() -> str | None:
    """Returns the path of the Big Picture program, or None if it is not installed.

    $LUTRIS_BIGPICTURE overrides the search. Otherwise a build in the source
    tree comes first, so that running Lutris from a checkout uses its own
    build, then the directory Lutris was started from, then $PATH."""
    override = os.environ.get("LUTRIS_BIGPICTURE")
    if override:
        return override if os.access(override, os.X_OK) else None

    source_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidates = [
        os.path.join(source_root, "bigpicture", "target", "release", EXECUTABLE_NAME),
        os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), EXECUTABLE_NAME),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return system.find_executable(EXECUTABLE_NAME)


def get_runtime_dir() -> str | None:
    """The user's runtime directory, where the desktop's sockets are: the one
    the environment names, or else the usual one if it is there."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir:
        return runtime_dir

    usual = "/run/user/%d" % os.getuid()

    return usual if os.path.isdir(usual) else None


def get_wayland_display(runtime_dir: str | None) -> str | None:
    """The Wayland display to use: the one the environment names, or else one
    that is found answering in the runtime directory, if any."""
    display = os.environ.get("WAYLAND_DISPLAY")
    if display or not runtime_dir:
        return display or None

    try:
        names = sorted(name for name in os.listdir(runtime_dir) if name.startswith("wayland-"))
    except OSError:
        return None

    for name in names:
        if name.endswith(".lock"):
            continue

        # A compositor that has gone leaves its socket behind, so try it.
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
            try:
                probe.connect(os.path.join(runtime_dir, name))
            except OSError:
                continue

        return name

    return None


def get_command(executable: str) -> list[str]:
    """The command that starts the Big Picture interface, with the options
    that have to be settled before it has shown anything."""
    command = [executable]
    if not settings.read_bool_setting(SPLASH_SETTING, default=True):
        command.append("--no-splash")
    return command


def get_sound_pack_dirs() -> list[str]:
    """The directories searched for navigation sound packs, each of which is a
    directory of its own in there. The user's packs come first, so they can
    replace packs installed with Lutris."""
    return [
        os.path.join(settings.DATA_DIR, "bigpicture", "sounds"),
        os.path.join(datapath.get(), "bigpicture", "sounds"),
    ]


def get_interface_strings() -> dict[str, str]:
    """The text of the Big Picture interface, translated. The interface looks
    these up by their English text, and falls back on it."""
    return {
        "Home": _("Home"),
        "Library": _("Library"),
        "Recently played": _("Recently played"),
        "Favorites": _("Favorites"),
        "Recently added": _("Recently added"),
        "All games": _("All games"),
        "%d games": _("%d games"),
        "Sorted by name": _("Sorted by name"),
        "Sorted by last played": _("Sorted by last played"),
        "Sorted by play time": _("Sorted by play time"),
        "Search": _("Search"),
        "Sort": _("Sort"),
        "Select": _("Select"),
        "Back": _("Back"),
        "Menu": _("Menu"),
        "Play": _("Play"),
        "Stop": _("Stop"),
        "Launching…": _("Launching…"),
        "Running": _("Running"),
        "Add to favorites": _("Add to favorites"),
        "Remove from favorites": _("Remove from favorites"),
        "Runner": _("Runner"),
        "Platform": _("Platform"),
        "Year": _("Year"),
        "Play time": _("Play time"),
        "Last played": _("Last played"),
        "Resume": _("Resume"),
        "Exit Big Picture": _("Exit Big Picture"),
        "Quit Lutris": _("Quit Lutris"),
        "Sounds": _("Sounds"),
        "Start animation": _("Start animation"),
        "On": _("On"),
        "Default": _("Default"),
        "Off": _("Off"),
        "Space": _("Space"),
        "Delete": _("Delete"),
        "Clear": _("Clear"),
        "Done": _("Done"),
        "Loading library…": _("Loading library…"),
        "Your library is empty": _("Your library is empty"),
        "Install games in Lutris to see them here.": _("Install games in Lutris to see them here."),
        "No games found": _("No games found"),
    }


def get_library() -> list[dict[str, Any]]:
    """The installed games, as the Big Picture interface wants them described.
    Hidden games are left out."""
    category_names = {category["id"]: str(category["name"]) for category in categories_db.get_categories()}
    games_categories = categories_db.get_all_games_categories()
    coverart = LutrisCoverart()
    library = []

    for db_game in games_db.get_games(filters={"installed": "1"}):
        game_id = str(db_game["id"])
        categories = [category_names[c] for c in games_categories.get(game_id, []) if c in category_names]
        if ".hidden" in categories:
            continue

        # StoreItem knows where else to look when Lutris has no cover of its
        # own, such as the media of the service the game came from.
        media_paths = StoreItem(db_game, None, coverart).get_media_paths()
        cover = next((media.path for media in media_paths if media.exists), None)

        playtime = db_game.get("playtime") or 0
        lastplayed = sanitize_timestamp(db_game.get("lastplayed")) or 0
        runner = db_game.get("runner") or ""
        library.append(
            {
                "id": game_id,
                "name": db_game.get("name") or "",
                "sortname": db_game.get("sortname") or "",
                "runner": get_runner_human_name(runner) if runner else "",
                "platform": db_game.get("platform") or "",
                "year": db_game.get("year") or None,
                "playtime": playtime,
                "playtime_text": get_formatted_playtime(playtime) if playtime else "",
                "lastplayed": lastplayed,
                "lastplayed_text": time.strftime("%x", time.localtime(lastplayed)) if lastplayed else "",
                "installed_at": sanitize_timestamp(db_game.get("installed_at")) or 0,
                "cover": cover,
                "favorite": "favorite" in categories,
                "categories": sorted(c for c in categories if c != "favorite" and not c.startswith(".")),
            }
        )
    return library


def force_steam_input_appid(appid: int) -> bool:
    """Tells the running Steam to use the controller layout of the app given,
    whatever window has the focus, or with 0 to go back to choosing by itself.
    This is the request Proton makes for games that Steam cannot see the
    window of. Returns False if it could not be made.

    Steam must be running: the same command would otherwise start it."""
    if not get_steam_pid():
        return False

    # Without these, Steam takes the request to come from a game of its own.
    env = {k: v for k, v in os.environ.items() if k not in ("SteamAppId", "SteamGameId", "STEAM_COMPAT_APP_ID")}
    try:
        command = import_runner("steam")().get_command() + ["steam://forceinputappid/%d" % appid]
        subprocess.run(
            command,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=STEAM_REQUEST_TIMEOUT,
            check=False,
        )
    except Exception as ex:  # pylint: disable=broad-except
        logger.warning("Unable to set the Steam Input app ID to %s: %s", appid, ex)
        return False

    logger.debug("Steam Input app ID set to %s", appid)
    return True


class SteamInputHold:
    """Keeps Steam from acting on the controller while Big Picture mode has it.

    A running Steam reads controllers itself and, unless a game of its own
    has the focus, turns their buttons into key presses and mouse clicks:
    by its desktop layout, in which the bottom face button is Enter, or by
    the layout of a game, if one was forced and never taken back - which is
    what a game run with Proton's Wayland driver leaves behind when it is
    stopped rather than quit. Big Picture mode reads the controller too, so
    it would get everything twice, and a single press would open a game's
    page and start the game.

    So while Big Picture mode is in front, Steam is told to use a layout
    with nothing in it, and when a game starts or the mode is left, to go
    back to choosing layouts by itself. Steam is never started for this, and
    nothing in its settings is changed."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._wanted = False
        self._worker: threading.Thread | None = None
        # The Steam that has been told to keep off, by its process ID.
        self._held_pid: str | None = None

    def hold(self, wait: bool = False) -> None:
        """Has Steam leave the controller alone, if Steam is running."""
        self._set(True, wait)

    def release(self, wait: bool = False) -> None:
        """Lets Steam handle the controller as it sees fit again."""
        self._set(False, wait)

    def _set(self, wanted: bool, wait: bool) -> None:
        with self._lock:
            self._wanted = wanted
            worker = self._worker
            if not worker:
                worker = self._worker = threading.Thread(target=self._apply, daemon=True)
                worker.start()

        if wait:
            worker.join(timeout=STEAM_RELEASE_TIMEOUT)

    def _apply(self) -> None:
        """Brings Steam into line with what is wanted, and again if that has
        changed in the meantime; the requests are slow, so this is a thread."""
        while True:
            with self._lock:
                wanted = self._wanted
                steam_pid = get_steam_pid()
                if not steam_pid:
                    self._held_pid = None  # nothing to hold, and nothing held

                held = bool(steam_pid) and steam_pid == self._held_pid
                if wanted == held or not steam_pid:
                    self._worker = None
                    return

            done = force_steam_input_appid(STEAM_CLIENT_APPID if wanted else STEAM_NO_FORCED_APPID)

            with self._lock:
                if not done:
                    self._worker = None
                    return

                self._held_pid = steam_pid if wanted else None


class BigPictureLaunchUIDelegate(LaunchUIDelegate):
    """Launches games without putting dialogs in front of the Big Picture
    interface: a dialog there may be out of reach of a controller. Choices are
    made as for a launch from the command line, and problems are reported
    as errors, which Big Picture mode shows itself."""

    def __init__(self, big_picture: "BigPictureMode") -> None:
        self.big_picture = big_picture

    def wait_for_component_updates(self, game: Game, on_ready: Callable[[], None]) -> None:
        """Holds the launch back while Lutris is updating its components, as
        launching then can crash games or corrupt their Wine prefix. Stopping
        the game in the meantime cancels the launch."""
        big_picture = self.big_picture
        if big_picture.is_download_queue_empty:
            on_ready()
            return

        big_picture.pending_launches.add(game.id)
        big_picture.send_game_state(game.id, Game.STATE_LAUNCHING, _("Waiting for Lutris component updates…"))

        def poll() -> bool:
            if game.id not in big_picture.pending_launches or not big_picture.is_active:
                return False
            if not big_picture.is_download_queue_empty:
                return True
            big_picture.pending_launches.discard(game.id)
            on_ready()
            # If the launch got nowhere, say so; otherwise GAME_START has.
            if game.state == Game.STATE_STOPPED:
                big_picture.send_game_state(game.id, Game.STATE_STOPPED)
            return False

        GLib.timeout_add(COMPONENT_UPDATE_POLL_DELAY, poll)


class BigPictureMode:
    """Runs the Big Picture interface and serves its requests."""

    def __init__(self, application: "LutrisApplication") -> None:
        self.application = application
        self.pending_launches: set[str] = set()
        self._process: Gio.Subprocess | None = None
        self._stdin: Gio.OutputStream | None = None
        self._registrations: list[NotificationRegistration] = []
        self._library_update_source = 0
        self._steam_input = SteamInputHold()
        self._steam_input_source = 0

    @property
    def is_active(self) -> bool:
        """True while the Big Picture interface is running."""
        return self._process is not None

    @property
    def is_download_queue_empty(self) -> bool:
        window = self.application.window
        return not window or window.is_download_queue_empty

    def start(self) -> None:
        """Starts the Big Picture interface; raises MissingExecutableError if
        it is not installed, and GLib.Error if it can't be started."""
        if self._process:
            return

        executable = find_big_picture_executable()
        if not executable:
            raise MissingExecutableError(
                _(
                    "The Big Picture interface is not installed.\n\n"
                    "It is built separately from Lutris: run 'make bigpicture' in the Lutris "
                    "source tree, or install the '%s' program."
                )
                % EXECUTABLE_NAME
            )

        logger.info("Starting Big Picture mode: %s", executable)
        flags = Gio.SubprocessFlags.STDIN_PIPE | Gio.SubprocessFlags.STDOUT_PIPE
        launcher = Gio.SubprocessLauncher.new(flags)

        # The interface finds neither Wayland nor the sound server without
        # these, and Lutris may have been started from somewhere that does
        # not set them.
        runtime_dir = get_runtime_dir()
        if runtime_dir:
            launcher.setenv("XDG_RUNTIME_DIR", runtime_dir, False)

        wayland_display = get_wayland_display(runtime_dir)
        if wayland_display:
            launcher.setenv("WAYLAND_DISPLAY", wayland_display, False)

        process = launcher.spawnv(get_command(executable))
        self._process = process
        self._stdin = process.get_stdin_pipe()

        self._registrations = [
            GAME_START.register(self._on_game_state_changed),
            GAME_STARTED.register(self._on_game_state_changed),
            GAME_STOPPED.register(self._on_game_stopped),
            GAME_LAUNCH_STATUS.register(self._on_game_state_changed),
            GAME_UPDATED.register(self._on_library_changed),
            GAME_INSTALLED.register(self._on_library_changed),
        ]

        # There is one, as the flags above ask for it; the check is for mypy.
        stdout_pipe = process.get_stdout_pipe()
        if stdout_pipe:
            self._read_next_line(process, Gio.DataInputStream.new(stdout_pipe))

        process.wait_async(None, self._on_exited)

    def stop(self) -> None:
        """Asks the Big Picture interface to close. Lutris's own window comes
        back once it has."""
        if self._process:
            self._send({"type": "quit"})

    def force_stop(self) -> None:
        """Ends the Big Picture interface at once, with no further handling;
        for when Lutris itself is shutting down."""
        process = self._process
        if process:
            self._cleanup()
            process.force_exit()

    # Talking to the interface

    def _send(self, message: dict[str, Any]) -> None:
        if not self._stdin:
            return
        try:
            line = json.dumps(message, ensure_ascii=False) + "\n"
            self._stdin.write_all(line.encode("utf-8"), None)
        except GLib.Error as ex:
            # The interface has gone away; _on_exited will tidy up.
            logger.debug("Unable to write to the Big Picture interface: %s", ex)

    def send_game_state(self, game_id: str, state: str, status: str = "") -> None:
        self._send({"type": "game_state", "id": str(game_id), "state": state, "status": status})

    def send_error(self, error: BaseException | str) -> None:
        self._send({"type": "error", "message": str(error)})

    def _send_library(self) -> None:
        library = get_library()
        states = {game.id: game for game in self.application.get_running_games()}
        for entry in library:
            game = states.get(entry["id"])
            if game:
                entry["state"] = game.state
        self._send({"type": "library", "games": library})

    def _read_next_line(self, process: Gio.Subprocess, stdout: Gio.DataInputStream) -> None:
        def on_line_read(_stream: Gio.DataInputStream, result: Gio.AsyncResult) -> None:
            try:
                line, _length = stdout.read_line_finish_utf8(result)
            except GLib.Error as ex:
                logger.warning("Unable to read from the Big Picture interface: %s", ex)
                return
            if line is None or process is not self._process:
                return  # the interface has closed its end, or has been replaced
            try:
                self._handle_message(json.loads(line))
            except Exception as ex:  # pylint: disable=broad-except
                logger.exception("Unable to handle Big Picture message '%s': %s", line, ex)
            self._read_next_line(process, stdout)

        stdout.read_line_async(GLib.PRIORITY_DEFAULT, None, on_line_read)

    def _handle_message(self, message: dict[str, Any]) -> None:
        message_type = message.get("type")
        if message_type == "ready":
            sounds = {"pack": settings.read_setting(SOUND_PACK_SETTING) or "", "dirs": get_sound_pack_dirs()}
            self._send({"type": "init", "strings": get_interface_strings(), "sounds": sounds})
            self._send_library()
            self.application.on_big_picture_ready()

            self._update_steam_input()
            if not self._steam_input_source:
                self._steam_input_source = GLib.timeout_add_seconds(
                    STEAM_INPUT_CHECK_INTERVAL, self._update_steam_input
                )
        elif message_type == "launch":
            self._launch_game(str(message["id"]))
        elif message_type == "stop":
            self._stop_game(str(message["id"]))
        elif message_type == "set_favorite":
            Game(str(message["id"])).mark_as_favorite(bool(message["favorite"]))
        elif message_type == "set_sound_pack":
            settings.write_setting(SOUND_PACK_SETTING, str(message["pack"]))
        elif message_type == "set_splash":
            settings.write_setting(SPLASH_SETTING, bool(message["enabled"]))
        else:
            logger.warning("Unknown Big Picture message: %s", message)

    # Carrying out requests

    def _launch_game(self, game_id: str) -> None:
        if self.application.is_game_running_by_id(game_id) or game_id in self.pending_launches:
            return

        # The controller is the game's from here on, and Steam's to pass on.
        self._steam_input.release()

        game = Game(game_id)
        # With a handler of its own, the game's errors come to us rather than
        # to the error dialogs of the main window.
        game.game_error.register(lambda error: self._on_game_error(game, error))
        try:
            launched = game.launch(BigPictureLaunchUIDelegate(self))
        except Exception as ex:  # pylint: disable=broad-except
            logger.exception("Unable to launch %s: %s", game, ex)
            self.send_error(ex)
            launched = False

        if not launched:
            self.send_game_state(game_id, Game.STATE_STOPPED)
            self._update_steam_input()

    def _stop_game(self, game_id: str) -> None:
        if game_id in self.pending_launches:
            self.pending_launches.discard(game_id)
            self.send_game_state(game_id, Game.STATE_STOPPED)
            return

        for game in self.application.get_running_games():
            if game.id == game_id:
                game.force_stop()
                return
        # Nothing to stop, so the interface is out of date; put it right.
        self.send_game_state(game_id, Game.STATE_STOPPED)

    def _on_game_error(self, game: Game, error: BaseException) -> None:
        logger.error("%s failed in Big Picture mode: %s", game, error, exc_info=error)
        self.send_error(error)
        if game.state == Game.STATE_STOPPED:
            self.send_game_state(game.id, Game.STATE_STOPPED)

    # Keeping the interface up to date

    def _on_game_state_changed(self, game: Game) -> None:
        self.send_game_state(game.id, game.state, game.launch_status or "")
        self._update_steam_input()

    def _on_game_stopped(self, game: Game) -> None:
        self.send_game_state(game.id, Game.STATE_STOPPED)
        self._on_library_changed()  # its play time and last played date have changed
        self._update_steam_input()

    def _update_steam_input(self) -> bool:
        """Has Steam keep off the controller while the Big Picture interface is
        what the user is looking at, and not while a game is. This is also
        called every few seconds, for a Steam that was started since, or that
        a game left set to that game's layout."""
        if not self.is_active:
            return False

        playing = bool(self.pending_launches) or bool(self.application.get_running_games())
        if playing:
            self._steam_input.release()
        else:
            self._steam_input.hold()

        return True

    def _on_library_changed(self, *_args: Any) -> None:
        if not self._library_update_source:
            self._library_update_source = GLib.timeout_add(LIBRARY_UPDATE_DELAY, self._update_library)

    def _update_library(self) -> bool:
        self._library_update_source = 0
        if self._process:
            self._send_library()
        return False

    # Leaving

    def _cleanup(self) -> None:
        for registration in self._registrations:
            registration.unregister()
        self._registrations = []
        if self._library_update_source:
            GLib.source_remove(self._library_update_source)
            self._library_update_source = 0
        if self._steam_input_source:
            GLib.source_remove(self._steam_input_source)
            self._steam_input_source = 0
        self.pending_launches.clear()
        self._process = None
        self._stdin = None

        # Waited for, as Lutris may be about to quit, and Steam must not be
        # left ignoring the controller.
        self._steam_input.release(wait=True)

    def _on_exited(self, process: Gio.Subprocess, result: Gio.AsyncResult) -> None:
        try:
            process.wait_finish(result)
        except GLib.Error as ex:
            logger.warning("Error waiting for the Big Picture interface: %s", ex)
        exit_status = process.get_exit_status() if process.get_if_exited() else None
        if process is not self._process:
            return  # already dealt with

        if exit_status in (0, EXIT_QUIT_LUTRIS):
            logger.info("Leaving Big Picture mode")
        else:
            logger.error("The Big Picture interface ended unexpectedly")
        self._cleanup()
        self.application.on_big_picture_exited(quit_lutris=exit_status == EXIT_QUIT_LUTRIS)
