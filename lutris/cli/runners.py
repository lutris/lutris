"""Commands that install and uninstall runners (--install-runner, --uninstall-runner)."""

import os

from lutris import settings
from lutris.cli.output import CommandOutput
from lutris.delegates import InstallUIDelegate
from lutris.runners import InvalidRunnerError, RunnerInstallationError, import_runner
from lutris.util import system
from lutris.util.log import logger


def install_runner(output: CommandOutput, runner: str) -> None:
    if runner.startswith("lutris"):
        install_wine_version(output, runner)
    else:
        install_runner_by_name(output, runner)


def uninstall_runner(output: CommandOutput, runner: str) -> None:
    if "wine" in runner:
        if output.ask_yes_or_no("Are sure you want to delete Wine and all of the installed runners?"):
            uninstall_runner_by_name(output, runner)
        else:
            output.print("Not Removing Wine")
    elif runner.startswith("lutris"):
        uninstall_wine_version(output, runner)
    else:
        uninstall_runner_by_name(output, runner)


def _get_wine_version_path(version: str) -> tuple[str, str]:
    """Return the full name of a Lutris Wine version, and where it's installed."""
    version = f"{version}{'' if '-x86_64' in version else '-x86_64'}"
    return version, os.path.join(settings.RUNNER_DIR, "wine", version)


def install_wine_version(output: CommandOutput, version: str) -> None:
    """Download a Lutris Wine version (lutris -r lutris-...)."""
    _full_version, runner_path = _get_wine_version_path(version)
    if os.path.isdir(runner_path):
        output.print(f"Wine version '{version}' is already installed.")
        return
    try:
        runner = import_runner("wine")
        runner().install(InstallUIDelegate(), version=version)
        output.print(f"Wine version '{version}' has been installed.")
    except (InvalidRunnerError, RunnerInstallationError) as ex:
        output.print_error(ex.message)


def uninstall_wine_version(output: CommandOutput, version: str) -> None:
    version, runner_path = _get_wine_version_path(version)
    if os.path.isdir(runner_path):
        system.remove_folder(runner_path)
        output.print(f"Wine version '{version}' has been removed.")
    else:
        output.print_error(
            f"Specified version of Wine is not installed: {version}.\n"
            "Please check if the Wine Runner and specified version are installed "
            "(for that use --list-wine-versions).\n"
            "Also, check that the version specified is in the correct format."
        )


def install_runner_by_name(output: CommandOutput, runner_name: str) -> None:
    try:
        runner = import_runner(runner_name)()
        if runner.is_installed():
            output.print(f"'{runner_name}' is already installed.")
        else:
            runner.install(InstallUIDelegate(), version=None, callback=None)
            output.print(f"'{runner_name}' has been installed")
    except (InvalidRunnerError, RunnerInstallationError) as ex:
        output.print_error(ex.message)


def uninstall_runner_by_name(output: CommandOutput, runner_name: str) -> None:
    try:
        runner = import_runner(runner_name)()
    except InvalidRunnerError:
        logger.error("Failed to import Runner: %s", runner_name)
        return
    if not runner.is_installed():
        output.print(f"Runner '{runner_name}' is not installed.")
        return
    if runner.can_uninstall():
        runner.uninstall()
        output.print(f"'{runner_name}' has been uninstalled.")
    else:
        output.print(f"Runner '{runner_name}' cannot be uninstalled.")
