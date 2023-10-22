import shutil
from gettext import gettext as _

from lutris.exceptions import UnavailableRunnerError
from lutris.util.system import read_process_output


def get_executable():
    """Return the executable used to access Flatpak. None if Flatpak is not installed.

    In the case where Lutris is a Flatpak, we use flatpak-spawn.
    """
    return shutil.which("flatpak-spawn") or shutil.which("flatpak")


def is_installed():
    """Returns Flatpak is installed"""
    return bool(get_executable())


def get_command():
    """Return the full command used to interact with Flatpak."""
    exe = get_executable()
    if not exe:
        raise UnavailableRunnerError(_("Flatpak is not installed"))
    if "flatpak-spawn" in exe:
        return [exe, "--host", "flatpak"]
    return [exe]


def get_installed_apps():
    if not is_installed():
        return []

    command = get_command() + ["list"]
    package_list = read_process_output(command)
    packages = []
    for package in package_list.split("\n"):
        if package:
            try:
                name, appid, version, branch, origin, installation = package.split("\t")
            except ValueError:
                # For older Flatpak versions
                name, appid, version, branch, installation = package.split("\t")
                origin = ""
            packages.append({
                "name": name,
                "appid": appid,
                "version": version,
                "branch": branch,
                "origin": origin,
                "installation": installation
            })
    return packages


def is_app_installed(appid):
    """Return whether an app is installed"""
    if not appid:
        return False
    for app in get_installed_apps():
        if app["appid"] == appid:
            return True
    return False


def get_run_command(appid, arch=None, fcommand=None, branch=None):
    """Return command to launch a Flatpak app"""
    command = get_command()
    command.append("run")
    if arch:
        command.append(f"--arch={arch}")
    if fcommand:
        command.append(f"--command={fcommand}")
    if branch:
        command.append(f"--branch={branch}")
    command.append(appid)
    return command
