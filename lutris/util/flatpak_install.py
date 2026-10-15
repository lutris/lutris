"""User-scoped Flatpak operations, including calls from the Lutris sandbox."""

import configparser
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from gettext import gettext as _
from pathlib import Path

from lutris.exceptions import UnavailableRunnerError
from lutris.util import flatpak
from lutris.util.log import logger

FLATHUB_URL = "https://dl.flathub.org/repo/flathub.flatpakrepo"
APP_ID_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*(?:\.[A-Za-z_][A-Za-z0-9_-]*){2,}")


class FlatpakInstallError(RuntimeError):
    """A host, repository, installation or removal error."""


class FlatpakPrerequisiteError(FlatpakInstallError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def validate_appid(appid: str) -> None:
    if not APP_ID_PATTERN.fullmatch(appid):
        raise FlatpakInstallError(_("Invalid Flatpak application ID: %s") % appid)


def _validate_component(value: str, label: str) -> None:
    if value and not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", value):
        raise FlatpakInstallError(_("Invalid Flatpak %s") % label)


def run_host(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    """Never invoke a shell or use a sandbox-local flatpak installation."""
    try:
        return subprocess.run(flatpak.get_command() + args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError, UnavailableRunnerError) as error:
        raise FlatpakInstallError(_("Unable to run Flatpak on the host: %s") % error) from error


def _check(result: subprocess.CompletedProcess[str]) -> str:
    if result.returncode:
        message = result.stderr.strip() or result.stdout.strip() or str(result.returncode)
        raise FlatpakInstallError(message)
    return result.stdout.strip()


def check_host() -> None:
    if not flatpak.get_executable():
        reason = "access" if flatpak.is_sandboxed() else "missing"
        raise FlatpakPrerequisiteError(reason)
    try:
        result = run_host(["--version"])
    except FlatpakInstallError as error:
        logger.error("Flatpak host check failed: %s", error)
        raise FlatpakPrerequisiteError("access") from error
    if result.returncode:
        logger.error("Flatpak host check failed: %s", result.stderr.strip() or result.stdout.strip())
        raise FlatpakPrerequisiteError("access")


def get_user_ref(appid: str, arch: str = "", branch: str = "") -> str:
    validate_appid(appid)
    _validate_component(arch, "architecture")
    _validate_component(branch, "branch")
    args = ["info", "--user", "--show-ref"]
    if arch:
        args.append(f"--arch={arch}")
    args.append(appid)
    if branch:
        args.append(branch)
    result = run_host(args)
    if result.returncode:
        return ""
    ref = result.stdout.strip()
    parts = ref.split("/")
    if len(parts) != 4 or parts[0] != "app" or parts[1] != appid:
        raise FlatpakInstallError(_("Unexpected Flatpak application reference: %s") % ref)
    if (arch and parts[2] != arch) or (branch and parts[3] != branch):
        raise FlatpakInstallError(_("Flatpak installed a different architecture or branch than requested."))
    return ref


def ensure_user_remote(remote: str, confirm: Callable[[str], bool]) -> None:
    _validate_component(remote, "repository")
    remotes = _check(run_host(["remotes", "--user", "--columns=name"]))
    if remote in remotes.splitlines():
        return
    if remote != "flathub":
        raise FlatpakInstallError(_("Flatpak repository '%s' is not configured for this user.") % remote)
    if not confirm(_("Add the Flathub repository to your user Flatpak installation?")):
        raise FlatpakInstallError(_("Adding the Flatpak repository was cancelled."))
    _check(run_host(["remote-add", "--user", "--if-not-exists", remote, FLATHUB_URL]))


def _stage_file(path: Path) -> tuple[Path, str]:
    """Sandbox /tmp is private; stage downloads in the shared application cache."""
    if not flatpak.is_sandboxed():
        return path, ""
    appid = os.environ.get("FLATPAK_ID", "")
    if not appid:
        info = configparser.ConfigParser(interpolation=None)
        info.read("/.flatpak-info")
        appid = info.get("Application", "name", fallback="")
    validate_appid(appid)
    # Flatpak exposes this per-application cache at the same absolute path on
    # the host. Do not pass a private sandbox path to flatpak-spawn --host.
    cache = Path.home() / ".var/app" / appid / "cache/lutris/flatpak-install"
    cache.mkdir(parents=True, exist_ok=True)
    directory = tempfile.mkdtemp(prefix="package-", dir=cache)
    target = Path(directory) / path.name
    try:
        shutil.copyfile(path, target)
    except OSError:
        shutil.rmtree(directory)
        raise
    return target, directory


@dataclass
class InstallPlan:
    appid: str
    command: list[str]
    was_installed: bool
    arch: str = ""
    branch: str = ""
    staged_directory: str = ""

    def cleanup(self) -> None:
        if self.staged_directory:
            shutil.rmtree(self.staged_directory, ignore_errors=True)


def prepare_install(
    appid: str,
    file: str | None = None,
    remote: str = "flathub",
    arch: str = "",
    branch: str = "",
    confirm: Callable[[str], bool] | None = None,
) -> InstallPlan:
    validate_appid(appid)
    _validate_component(arch, "architecture")
    _validate_component(branch, "branch")
    check_host()
    if get_user_ref(appid, arch, branch):
        return InstallPlan(appid, [], True, arch, branch)
    if confirm is None:

        def confirm(_question: str) -> bool:
            return False

    args = ["install", "--user", "--noninteractive", "--assumeyes"]
    if arch:
        args.append(f"--arch={arch}")
    staged = ""
    if file:
        path = Path(file).expanduser().absolute()
        if not path.is_file() or path.suffix not in (".flatpak", ".flatpakref"):
            raise FlatpakInstallError(_("Select a downloaded .flatpak or .flatpakref file."))
        if path.suffix == ".flatpakref":
            info = configparser.ConfigParser(interpolation=None)
            try:
                with path.open(encoding="utf-8") as source:
                    info.read_file(source)
                if info.get("Flatpak Ref", "Name", fallback="") != appid:
                    raise FlatpakInstallError(_("The Flatpak reference does not match the application ID."))
                if info.getboolean("Flatpak Ref", "IsRuntime", fallback=False):
                    raise FlatpakInstallError(_("A Flatpak runtime cannot be installed as a game."))
            except (OSError, ValueError, configparser.Error) as error:
                raise FlatpakInstallError(_("Invalid Flatpak reference: %s") % error) from error
            if not confirm(_("Install this Flatpak reference? It may add user repositories and download runtimes.")):
                raise FlatpakInstallError(_("Flatpak installation was cancelled."))
            args.append("--from")
        else:
            args.append("--bundle")
        path, staged = _stage_file(path)
        args.append(str(path))
    else:
        ensure_user_remote(remote, confirm)
        # remote-info checks the exact application and reports download/configuration
        # errors before starting an installation; no fuzzy-name matching is used.
        info_args = ["remote-info", "--user", "--show-ref"]
        if arch:
            info_args.append(f"--arch={arch}")
        info_args += [remote, appid]
        if branch:
            info_args.append(branch)
        available_ref = _check(run_host(info_args))
        parts = available_ref.split("/")
        if len(parts) != 4 or parts[:2] != ["app", appid]:
            raise FlatpakInstallError(_("Application not found in the Flatpak repository."))
        args += [remote, available_ref]
    return InstallPlan(appid, flatpak.get_command() + args, False, arch, branch, staged)


def uninstall_user(appid: str, arch: str = "", branch: str = "") -> None:
    check_host()
    ref = get_user_ref(appid, arch, branch)
    if ref:
        # Do not delete personal data, remove unused dependencies or touch system apps.
        _check(run_host(["uninstall", "--user", "--noninteractive", "--assumeyes", ref], timeout=180))
