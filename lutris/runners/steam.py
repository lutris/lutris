"""Steam for Linux runner"""

import os
import signal
import time
from collections.abc import Iterable
from gettext import gettext as _
from typing import Optional

from lutris.exceptions import MissingGameExecutableError, UnavailableRunnerError
from lutris.monitored_command import MonitoredCommand
from lutris.runners import NonInstallableRunnerError
from lutris.runners.runner import Runner, kill_processes
from lutris.util import linux, system
from lutris.util.log import logger
from lutris.util.steam.appmanifest import AppManifest, get_appmanifest_from_appid, get_path_from_appmanifest
from lutris.util.steam.config import get_default_acf, get_steam_dir, get_steamapps_dirs
from lutris.util.steam.vdfutils import to_vdf
from lutris.util.strings import split_arguments

# Steam appmanifest StateFlags that mean the game should be treated as "still
# alive" so beat() keeps polling. "AppRunning" is the normal running case. The
# others cover the transient window between the Play click and AppRunning being
# set, when Steam runs a launch-time update/validate ("Update Running",
# "Validating", "Update Started") and the launcher process may already have
# exited. Persistent library states that are NOT tied to an active launch
# (e.g. "Update Required", "Update Paused", "Downloading") are deliberately
# excluded, so a game with a pending background update isn't seen as running.
STEAM_ALIVE_STATES = {
    "AppRunning",
    "Update Running",
    "Update Started",
    "Validating",
}

# Default time (seconds) to keep monitoring after the launcher exits while
# waiting for Steam's per-game reaper to appear, before concluding the launch
# failed. Covers slow hand-off, shader pre-caching and first-launch
# prerequisites. Overridable per-game via the "launch_grace_seconds" option.
DEFAULT_LAUNCH_GRACE_SECONDS = 120


def get_steam_pid() -> Optional[str]:
    """Return pid of Steam process.

    Steam is single-instance, so this resolves to at most one PID (the call
    uses pgrep without ``multiple``).
    """
    pid = system.get_pid("steam$")
    # get_pid() can return a list only with multiple=True, which we never pass;
    # narrow the type so callers get a plain Optional[str].
    if isinstance(pid, list):
        return pid[0] if pid else None
    return pid


def get_steam_game_pids(appid: str) -> list[int]:
    """Return the PIDs of the Steam "reaper" processes launched for a given appid.

    When Steam launches a game it spawns a reaper process whose command line
    contains "SteamLaunch AppId=<appid>". This reaper exists for the entire
    lifetime of the game (through shader pre-caching and play) and exits when
    the game stops, for native, Proton/Wine and Flatpak Steam alike.

    This is far more reliable than the appmanifest "AppRunning" StateFlag, which
    is not updated for Flatpak Steam installs, and it covers the launch window
    (the reaper appears before the game window does), so beat() does not call
    on_game_quit() prematurely.
    """
    if not appid:
        return []
    # The reaper cmdline looks like: "reaper SteamLaunch AppId=440 -- ...".
    # Match "AppId=<appid>" followed by a space or end of string so that appid
    # 440 does not also match a reaper for 4400 / 44012 (substring collision).
    prefix = "SteamLaunch AppId=%s" % appid
    pids = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(os.path.join("/proc", pid, "cmdline"), "rb") as cmdline_file:
                cmdline = cmdline_file.read().replace(b"\x00", b" ").decode("utf-8", "replace")
        except OSError:
            continue
        if "reaper" not in cmdline:
            continue
        idx = cmdline.find(prefix)
        if idx == -1:
            continue
        # Character immediately after the appid must be a space or end-of-string.
        after = cmdline[idx + len(prefix) : idx + len(prefix) + 1]
        if after in ("", " "):
            pids.append(int(pid))
    return pids


def is_running():
    """Checks if Steam is running."""
    return bool(get_steam_pid())


class steam(Runner):
    description = _("Runs Steam for Linux games")
    human_name = _("Steam")
    platform_dict = Runner.to_platform_dict([_("Linux")])
    runner_executable = "steam"
    flatpak_id = "com.valvesoftware.Steam"
    game_options = [
        {
            "option": "appid",
            "label": _("Application ID"),
            "type": "string",
            "help": _(
                "The application ID can be retrieved from the game's "
                "page at steampowered.com. Example: 235320 is the "
                "app ID for <i>Original War</i> in: \n"
                "http://store.steampowered.com/app/<b>235320</b>/"
            ),
        },
        {
            "option": "args",
            "type": "string",
            "label": _("Arguments"),
            "help": _(
                "Command line arguments used when launching the game.\nIgnored when Steam Big Picture mode is enabled."
            ),
        },
        {
            "option": "run_without_steam",
            "label": _("DRM free mode (Do not launch Steam)"),
            "type": "bool",
            "default": False,
            "advanced": True,
            "help": _("Run the game directly without Steam, requires the game binary path to be set"),
        },
        {
            "option": "steamless_binary",
            "type": "file",
            "label": _("Game binary path"),
            "advanced": True,
            "help": _("Path to the game executable (Required by DRM free mode)"),
        },
    ]
    runner_options = [
        {
            "option": "start_in_big_picture",
            "label": _("Start Steam in Big Picture mode"),
            "type": "bool",
            "default": False,
            "help": _(
                "Launches Steam in Big Picture mode.\n"
                "Only works if Steam is not running or "
                "already running in Big Picture mode.\n"
                "Useful when playing with a Steam Controller."
            ),
        },
        {
            "option": "args",
            "type": "string",
            "label": _("Arguments"),
            "advanced": True,
            "help": _("Extra command line arguments used when launching Steam"),
        },
        {
            "option": "launch_grace_seconds",
            "type": "string",
            "label": _("Launch grace period (seconds)"),
            "advanced": True,
            "help": _(
                "How long Lutris keeps monitoring after the Steam launcher exits "
                "while waiting for the game to appear, before assuming the launch "
                "failed. Covers shader pre-caching and first-launch prerequisites. "
                "Leave blank to use the default (%s seconds)."
            )
            % DEFAULT_LAUNCH_GRACE_SECONDS,
        },
    ]
    system_options_override = [
        {"option": "disable_runtime", "default": True},
        {"option": "gamemode", "default": False},
    ]

    # Cache the reaper-PID scan for a fraction of a heartbeat so the two calls
    # in a single Game.beat() (filter_game_pids + keep_game_alive) only walk
    # /proc once. Kept well below HEARTBEAT_DELAY so each beat re-scans.
    _REAPER_CACHE_TTL = 1.0

    def __init__(self, config=None):
        super().__init__(config)
        # Cache for the resolved appmanifest path so beat() doesn't re-walk
        # every steamapps dir on each heartbeat (see _get_cached_appmanifest).
        self._cached_appmanifest_appid: Optional[str] = None
        self._cached_appmanifest_path: Optional[str] = None
        # Launch-window tracking for keep_game_alive().
        self._launch_monitor_start: Optional[float] = None
        self._steam_reaper_seen: bool = False
        # Per-beat cache of the reaper PID scan (see _get_reaper_pids).
        self._reaper_pids_cache: list[int] = []
        self._reaper_pids_cache_at: float = 0.0

    @property
    def launch_grace_seconds(self) -> float:
        """Launch grace period, from the per-game option if set and valid,
        otherwise DEFAULT_LAUNCH_GRACE_SECONDS."""
        raw = self.runner_config.get("launch_grace_seconds")
        if raw not in (None, ""):
            try:
                value = float(raw)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                value = None
            if value is not None and value > 0:
                return value
            logger.warning("Invalid launch_grace_seconds %r; using default", raw)
        return DEFAULT_LAUNCH_GRACE_SECONDS

    def _get_reaper_pids(self) -> list[int]:
        """Reaper PIDs for this appid, cached briefly so the two calls within a
        single Game.beat() (filter_game_pids + keep_game_alive) share one
        /proc scan instead of walking it twice."""
        if not self.appid:
            return []
        now = time.monotonic()
        if now - self._reaper_pids_cache_at < self._REAPER_CACHE_TTL:
            return self._reaper_pids_cache
        self._reaper_pids_cache = get_steam_game_pids(self.appid)
        self._reaper_pids_cache_at = now
        return self._reaper_pids_cache

    @property
    def runnable_alone(self):
        return not linux.LINUX_SYSTEM.is_flatpak()

    @property
    def appid(self):
        return self.game_config.get("appid") or ""

    @property
    def game_path(self):
        if not self.appid:
            return None
        return self.get_game_path_from_appid(self.appid)

    @property
    def steam_data_dir(self):
        """Main installation directory for Steam"""
        return get_steam_dir()

    def get_appmanifest(self):
        """Return an AppManifest instance for the game"""
        appmanifests = []
        for apps_path in get_steamapps_dirs():
            appmanifest = get_appmanifest_from_appid(apps_path, self.appid)
            if appmanifest:
                appmanifests.append(appmanifest)
        if len(appmanifests) > 1:
            logger.warning("More than one AppManifest for %s returning only 1st", self.appid)
        if appmanifests:
            return appmanifests[0]

    def get_executable(self) -> str:
        if linux.LINUX_SYSTEM.is_flatpak():
            # Fallback to xgd-open for Steam URIs in Flatpak
            return system.find_required_executable("xdg-open")
        runner_executable = self.runner_config.get("runner_executable")
        if runner_executable and os.path.isfile(runner_executable):
            return runner_executable
        return system.find_required_executable(self.runner_executable)

    @property
    def has_working_dir(self) -> bool:
        return bool(self._get_steamless_working_dir() or super().has_working_dir)

    @property
    def working_dir(self):
        """Return the working directory to use when running the game."""
        return self._get_steamless_working_dir() or super().working_dir

    def _get_steamless_working_dir(self) -> str | None:
        """Return the working directory to use when running the game."""
        if self.game_config.get("run_without_steam"):
            steamless_binary = self.game_config.get("steamless_binary")
            if steamless_binary and os.path.isfile(steamless_binary):
                return os.path.dirname(steamless_binary)
        return None

    @property
    def launch_args(self):
        """Provide launch arguments for Steam"""
        command = self.get_command()
        if self.runner_config.get("start_in_big_picture"):
            command.append("-bigpicture")
        return command + split_arguments(self.runner_config.get("args") or "")

    def get_game_path_from_appid(self, appid):
        """Return the game directory."""
        for apps_path in get_steamapps_dirs():
            game_path = get_path_from_appmanifest(apps_path, appid)
            if game_path:
                return game_path
        logger.info("Data path for SteamApp %s not found.", appid)
        return ""

    def get_default_steamapps_path(self):
        steamapps_paths = get_steamapps_dirs()
        if steamapps_paths:
            return steamapps_paths[0]
        return ""

    def install(self, install_ui_delegate, version=None, callback=None):
        raise NonInstallableRunnerError(
            message=_("Steam for Linux installation is not handled by Lutris."),
            message_markup=_(
                "Steam for Linux installation is not handled by Lutris.\n"
                "Please go to "
                "<a href='http://steampowered.com'>http://steampowered.com</a>"
                " or install Steam with the package provided by your distribution."
            ),
        )

    def install_game(self, appid, generate_acf=False):
        logger.debug("Installing steam game %s", appid)
        if generate_acf:
            acf_data = get_default_acf(appid, appid)
            acf_content = to_vdf(acf_data)
            steamapps_path = self.get_default_steamapps_path()
            if not steamapps_path:
                raise UnavailableRunnerError(_("Could not find Steam path, is Steam installed?"))
            acf_path = os.path.join(steamapps_path, "appmanifest_%s.acf" % appid)
            with open(acf_path, "w", encoding="utf-8") as acf_file:
                acf_file.write(acf_content)
        system.spawn(self.get_command() + [f"steam://install/{appid}"])

    def get_run_data(self):
        return {"command": self.launch_args, "env": self.get_env()}

    def play(self):
        # Reset launch-window tracking for this run (the runner instance may be
        # reused across launches); see keep_game_alive().
        self._launch_monitor_start = None
        self._steam_reaper_seen = False
        self._reaper_pids_cache = []
        self._reaper_pids_cache_at = 0.0
        game_args = self.game_config.get("args") or ""

        binary_path = self.game_config.get("steamless_binary")
        if self.game_config.get("run_without_steam") and binary_path:
            # Start without steam
            if not system.path_exists(binary_path):
                raise MissingGameExecutableError(filename=binary_path)
            command = [binary_path]
        else:
            # Start through steam
            if linux.LINUX_SYSTEM.is_flatpak():
                if game_args:
                    steam_uri = "steam://run/%s//%s/" % (self.appid, game_args)
                else:
                    steam_uri = "steam://rungameid/%s" % self.appid
                return {
                    "command": self.launch_args + [steam_uri],
                    "env": self.get_env(),
                }
            command = self.launch_args
            if self.runner_config.get("start_in_big_picture") or not game_args:
                command.append("steam://rungameid/%s" % self.appid)
            else:
                command.append("-applaunch")
                command.append(self.appid)

        if game_args:
            for arg in split_arguments(game_args):
                command.append(arg)

        return {
            "command": command,
            "env": self.get_env(),
        }

    def filter_game_pids(self, candidate_pids: Iterable[int], game_uuid: str, game_folder: str) -> set[int]:
        """Track a running Steam game by its Steam-spawned processes.

        Steam games launch via non-blocking URI handlers (steam://rungameid/ or
        steam -applaunch) that exit almost immediately, and the real game runs
        under Steam's PID tree without inheriting LUTRIS_GAME_UUID. So the base
        PID detection finds nothing and beat() fires on_game_quit() too early.

        The reliable signal is Steam's per-game "reaper" process, whose command
        line contains "SteamLaunch AppId=<appid>". It exists for the whole life
        of the game (including the shader pre-cache / launch window, before the
        game window appears) and exits when the game stops -- for native,
        Proton/Wine and Flatpak Steam alike. While it is present we report its
        PID so beat() keeps polling; once it is gone the set goes empty and
        on_game_quit() fires correctly.

        The appmanifest "AppRunning" StateFlag is also honoured as a secondary
        signal where Steam updates it (it is not updated for Flatpak installs),
        in which case the Steam process PID is tracked instead.
        """
        pids = super().filter_game_pids(candidate_pids, game_uuid, game_folder)

        if self.appid:
            reaper_pids = self._get_reaper_pids()
            if reaper_pids:
                pids.update(reaper_pids)
            elif self._game_is_alive_in_steam():
                steam_pid = self._get_steam_pid_int()
                if steam_pid:
                    pids.add(steam_pid)

        return pids

    def force_stop_game(self, game_pids: Iterable[int]) -> None:
        """Stop a running Steam game without harming the Steam client.

        The base implementation SIGTERMs every tracked PID. filter_game_pids()
        may track Steam's own PID (appmanifest fallback), so a blind SIGTERM
        could kill the user's whole Steam client. Here we SIGTERM the game's
        reaper process(es) -- terminating the reaper stops just this game -- and
        any other tracked PIDs that are not the Steam client itself. We never
        signal the Steam PID directly.
        """
        steam_pid = self._get_steam_pid_int()
        reaper_pids = set(get_steam_game_pids(self.appid)) if self.appid else set()

        target_pids = {pid for pid in game_pids if pid != steam_pid}
        target_pids.update(reaper_pids)

        if target_pids:
            kill_processes(signal.SIGTERM, target_pids)

    def keep_game_alive(self, game_pids: Iterable[int], game_thread_running: bool) -> bool:
        """Keep beat() monitoring a Steam game across the out-of-process launch.

        Steam launches the game via a non-blocking URI, so game_thread exits
        within seconds. There's then a brief window before Steam's per-game
        reaper process appears. We:

        * report alive while game_thread is still running (normal early phase);
        * report alive while the reaper for this appid is present (the whole
          game lifetime, detected via the reaper PID scan);
        * during the launch window -- after game_thread exits but before the
          reaper has ever appeared -- report alive until LAUNCH_GRACE_SECONDS
          elapses, so a slow hand-off / shader pre-cache doesn't trigger a
          premature on_game_quit(). Once the reaper has been seen and then
          disappears, the game has genuinely quit and we return False.
        """
        if not self.appid:
            return False

        reaper_alive = bool(self._get_reaper_pids())

        if game_thread_running or reaper_alive:
            if reaper_alive:
                self._steam_reaper_seen = True
            self._launch_monitor_start = self._launch_monitor_start or time.monotonic()
            return True

        # game_thread has exited and no reaper is visible.
        if self._steam_reaper_seen:
            # We saw the game running and it's now gone -> genuinely quit.
            return False

        # Reaper has never appeared yet: stay alive through the launch window.
        if self._launch_monitor_start is None:
            self._launch_monitor_start = time.monotonic()
        return (time.monotonic() - self._launch_monitor_start) < self.launch_grace_seconds

    def _get_steam_pid_int(self) -> Optional[int]:
        """Return the Steam process PID as an int, or None.

        get_steam_pid() returns a string (from pgrep), but candidate_pids and
        the tracked PID set are ints, so it must be converted before use."""
        steam_pid = get_steam_pid()
        if not steam_pid:
            return None
        try:
            return int(steam_pid)
        except (TypeError, ValueError):
            return None

    def _game_is_alive_in_steam(self) -> bool:
        """True if Steam's appmanifest reports the game as running or busy.

        "AppRunning" covers the normal running case. The update/validate states
        cover the window between the Play click and AppRunning being set (Steam
        starting, "Update Running", "Validating", first-launch prereqs), during
        which the game thread may already have exited; treating them as alive
        keeps beat() from firing on_game_quit() prematurely in that window."""
        appmanifest = self._get_cached_appmanifest()
        if not appmanifest:
            return False
        return bool(set(appmanifest.states) & STEAM_ALIVE_STATES)

    def _get_cached_appmanifest(self) -> Optional[AppManifest]:
        """Return the AppManifest for the current appid, re-reading StateFlags
        each call but resolving (and caching) the file path only once.

        get_appmanifest() walks every steamapps dir and re-parses VDF; doing
        that every beat (every HEARTBEAT_DELAY seconds) is wasteful, so the
        resolved path is cached per appid and only the file is re-read."""
        if not self.appid:
            return None
        if self._cached_appmanifest_appid != self.appid:
            self._cached_appmanifest_path = None
            self._cached_appmanifest_appid = self.appid
        if self._cached_appmanifest_path:
            return AppManifest(self._cached_appmanifest_path)
        appmanifest = self.get_appmanifest()
        if appmanifest:
            self._cached_appmanifest_path = appmanifest.appmanifest_path
        return appmanifest

    def remove_game_data(self, app_id=None, **kwargs):
        if not self.is_installed():
            return False
        app_id = app_id or self.appid
        command = MonitoredCommand(
            self.get_command() + [f"steam://uninstall/{app_id}"],
            runner=self,
            env=self.get_env(),
        )
        command.start()
