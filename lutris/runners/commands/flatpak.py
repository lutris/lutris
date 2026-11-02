"""Installer task for user Flatpak applications."""

from collections.abc import Callable
from gettext import gettext as _
from typing import Any

from lutris.installer.errors import FlatpakSetupError, ScriptingError
from lutris.monitored_command import MonitoredCommand
from lutris.util.flatpak_install import (
    FlatpakInstallError,
    FlatpakPrerequisiteError,
    InstallPlan,
    get_user_ref,
    prepare_install,
)


class FlatpakInstallCommand(MonitoredCommand):
    def __init__(self, plan: InstallPlan, game_config: dict[str, Any]):
        super().__init__(plan.command, title=_("Installing Flatpak application: %s") % plan.appid)
        self.plan = plan
        self.game_config = game_config
        self.stop_func = self._cleanup

    def _cleanup(self) -> bool:
        self.plan.cleanup()
        return True

    def finish_installation(self) -> None:
        if self.return_code != "0":
            raise ScriptingError(_("Flatpak installation failed."))
        save_installation(self.plan, self.game_config)


def save_installation(plan: InstallPlan, game_config: dict[str, Any]) -> None:
    try:
        ref = get_user_ref(plan.appid, plan.arch, plan.branch)
        if not ref:
            raise FlatpakInstallError(_("Flatpak completed, but the requested application is not installed."))
    except FlatpakInstallError as error:
        raise ScriptingError(str(error)) from error
    _kind, appid, arch, branch = ref.split("/")
    game_config.update(
        appid=appid,
        arch=arch,
        branch=branch,
        install_type="user",
        flatpak_installed_by_lutris=bool(game_config.get("flatpak_installed_by_lutris")) or not plan.was_installed,
    )


def install_flatpak(
    appid: str,
    file: str | None = None,
    remote: str = "flathub",
    arch: str = "",
    branch: str = "",
    game_config: dict[str, Any] | None = None,
    confirm: Callable[[str], bool] | None = None,
) -> FlatpakInstallCommand | None:
    """Install a Flathub ID, or a downloaded file supplied by the YAML files section."""
    if game_config is None:
        game_config = {}
    try:
        plan = prepare_install(appid, file, remote, arch, branch, confirm)
    except FlatpakPrerequisiteError as error:
        raise FlatpakSetupError(error.reason) from error
    except FlatpakInstallError as error:
        raise ScriptingError(str(error)) from error
    if plan.was_installed:
        save_installation(plan, game_config)
        return None
    command = FlatpakInstallCommand(plan, game_config)
    try:
        command.start()
        if command.game_process is None:
            plan.cleanup()
            raise ScriptingError(_("Unable to start Flatpak installation."))
    except Exception:
        plan.cleanup()
        raise
    return command
