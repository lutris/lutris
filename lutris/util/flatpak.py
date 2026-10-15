import os
import shutil
from gettext import gettext as _

from lutris.exceptions import UnavailableRunnerError
from lutris.util import cache_single
from lutris.util.log import logger
from lutris.util.system import read_process_output


def is_sandboxed() -> bool:
    return os.path.exists("/.flatpak-info") or bool(os.environ.get("FLATPAK_ID"))


def is_game_data_directory(path: str, system_config: dict[str, str]) -> bool:
    """Allow trashing external game data, never Flatpak deployments or app data."""
    from lutris.util.system import is_removeable

    if not path:
        return False
    directory = os.path.abspath(os.path.expanduser(path))
    resolved = os.path.realpath(directory)
    if not is_removeable(directory, system_config) or not is_removeable(resolved, system_config):
        return False
    home = os.path.expanduser("~")
    protected = (
        os.path.join(home, ".local", "share", "flatpak"),
        os.path.join(
            os.environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share"),
            "flatpak",
        ),
        os.path.join(home, ".var", "app"),
        "/var/lib/flatpak",
    )
    for root in protected:
        root = os.path.realpath(root)
        if os.path.commonpath((resolved, root)) in (resolved, root):
            return False
    return True


@cache_single
def get_executable() -> str | None:
    """Return the executable used to access Flatpak. None if Flatpak is not installed.

    In the case where Lutris is a Flatpak, we use flatpak-spawn.
    """
    return shutil.which("flatpak-spawn") if is_sandboxed() else shutil.which("flatpak")


def is_installed() -> bool:
    """Returns Flatpak is installed"""
    return bool(get_executable())


def get_command() -> list[str]:
    """Return the full command used to interact with Flatpak."""
    exe = get_executable()
    if not exe:
        raise UnavailableRunnerError(_("Flatpak is not installed"))
    if "flatpak-spawn" in exe:
        return [exe, "--host", "flatpak"]
    return [exe]


def get_installed_apps() -> list[dict[str, str]]:
    if not is_installed():
        return []

    command = get_command() + [
        "list",
        "--columns=name,application,version,branch,arch,origin,installation",
    ]
    package_list = read_process_output(command)
    packages = []
    for package in package_list.split("\n"):
        if package:
            try:
                name, appid, version, branch, arch, origin, installation = package.split("\t")
            except ValueError:
                logger.error("Not able to parse Flatpak output: %s", package)
                continue
            packages.append(
                {
                    "name": name,
                    "appid": appid,
                    "version": version,
                    "branch": branch,
                    "arch": arch,
                    "origin": origin,
                    "installation": installation,
                }
            )
    return packages


def is_app_installed(appid: str | None) -> bool:
    """Return whether an app is installed"""
    if not appid:
        return False
    for app in get_installed_apps():
        if app["appid"] == appid:
            return True
    return False


def get_run_command(
    appid: str,
    arch: str | None = None,
    fcommand: str | None = None,
    branch: str | None = None,
) -> list[str]:
    """Return command to launch a Flatpak app"""
    command = get_bare_run_command(arch, fcommand, branch)
    command.append(appid)
    return command


def get_bare_run_command(
    arch: str | None = None,
    fcommand: str | None = None,
    branch: str | None = None,
    installation: str | None = None,
) -> list[str]:
    """Return command to launch a Flatpak app, without the app-id at the end;
    this is the 'command' of the flatpak runner itself, and a program's
    appid must be appended to it."""
    command = get_command()
    command.append("run")
    if installation in ("user", "system"):
        command.append(f"--{installation}")
    if arch:
        command.append(f"--arch={arch}")
    if fcommand:
        command.append(f"--command={fcommand}")
    if branch:
        command.append(f"--branch={branch}")
    return command
