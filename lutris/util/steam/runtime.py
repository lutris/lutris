"""Discover and launch Valve's Steam Linux Runtime containers for native games."""

import os
from gettext import gettext as _
from pathlib import Path
from platform import machine

from lutris.exceptions import GameConfigError
from lutris.util.steam.config import get_steamapps_dirs, search_in_steam_dirs

NO_STEAM_RUNTIME = "none"

_RUNTIMES = {
    "scout": (_("Steam Linux Runtime 1.0 (Scout)"), "1070560", "SteamLinuxRuntime"),
    "soldier": (_("Steam Linux Runtime 2.0 (Soldier)"), "1391110", "SteamLinuxRuntime_soldier"),
    "sniper": (_("Steam Linux Runtime 3.0 (Sniper)"), "1628350", "SteamLinuxRuntime_sniper"),
    "steamrt4": (_("Steam Linux Runtime 4.0"), "4183110", "SteamLinuxRuntime_4"),
}

STEAM_RUNTIME_CHOICES = [(_("None"), NO_STEAM_RUNTIME), *((details[0], key) for key, details in _RUNTIMES.items())]


def _find_launcher(directories: list[Path], basename: str) -> Path | None:
    for directory in directories:
        launcher = directory / basename
        if launcher.is_file() and os.access(launcher, os.X_OK):
            return launcher
    return None


def get_runtime_command(runtime: str, env: dict[str, str]) -> list[str]:
    """Build the runtime prefix and set Scout's Steam client path when detected."""
    if runtime == NO_STEAM_RUNTIME:
        return []
    if runtime not in _RUNTIMES:
        raise GameConfigError(_("Unknown Steam Linux Runtime: %s") % runtime)

    libraries = [Path(directory) / "common" for directory in get_steamapps_dirs()]
    data_home_var = "HOST_XDG_DATA_HOME" if os.environ.get("container") == "flatpak" else "XDG_DATA_HOME"
    data_home = os.environ.get(data_home_var)
    umu = (Path(data_home) if data_home else Path.home() / ".local" / "share") / "umu"

    def find(runtime_id: str, launcher_name: str = "run") -> Path:
        label, app_id, dirname = _RUNTIMES[runtime_id]
        if runtime_id == "steamrt4" and machine() == "aarch64":
            app_id = "4185400"
            dirname = "SteamLinuxRuntime_4-arm64"
        directories = [library / dirname for library in libraries]
        if runtime_id != "scout":
            directories.append(umu / runtime_id)
        launcher = _find_launcher(directories, launcher_name)
        if launcher is None:
            raise GameConfigError(
                _("%(runtime)s is required. Install it in Steam with steam://install/%(appid)s.")
                % {"runtime": label, "appid": app_id}
            )
        return launcher

    if runtime == "scout":
        scout = find("scout", "scout-on-soldier-entry-point-v2")
        soldier = find("soldier")
        # Scout writes files in its compatibility tool's var directory
        command = [str(soldier), f"--filesystem={scout.parent}:rw"]
        if not (scout.parent / "steam-runtime").is_dir() and not (
            env.get("STEAM_COMPAT_CLIENT_INSTALL_PATH") or os.environ.get("STEAM_COMPAT_CLIENT_INSTALL_PATH")
        ):
            archive = search_in_steam_dirs("ubuntu12_32/steam-runtime.tar.xz")
            if archive:
                client = Path(archive).parents[1].resolve()
                env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = str(client)
        return [*command, "--", str(scout), "--"]
    return [str(find(runtime)), "--"]
