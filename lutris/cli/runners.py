"""Commands that install and uninstall runners (--install-runner, --uninstall-runner)."""

from lutris.backend import runners
from lutris.backend.errors import InvalidRunnerError, LutrisError
from lutris.cli.output import CommandOutput
from lutris.util.log import logger


async def install_runner(output: CommandOutput, runner: str) -> None:
    name, version = runners.parse_runner_name(runner)
    label = f"Wine version '{version}'" if version else f"'{name}'"
    try:
        if await runners.is_runner_installed(name, version):
            output.print(f"{label} is already installed.")
            return
        await runners.install_runner(name, version)
        output.print(f"{label} has been installed.")
    except LutrisError as ex:
        output.print_error(ex.message)


async def uninstall_runner(output: CommandOutput, runner: str) -> None:
    name, version = runners.parse_runner_name(runner)
    if version:
        await uninstall_wine_version(output, version)
        return
    if name == "wine":
        if not output.ask_yes_or_no("Are sure you want to delete Wine and all of the installed runners?"):
            output.print("Not Removing Wine")
            return
    await uninstall_runner_by_name(output, runner)


async def uninstall_wine_version(output: CommandOutput, version: str) -> None:
    if not await runners.is_runner_installed("wine", version):
        output.print_error(
            f"Specified version of Wine is not installed: {version}.\n"
            "Please check if the Wine Runner and specified version are installed "
            "(for that use --list-wine-versions).\n"
            "Also, check that the version specified is in the correct format."
        )
        return
    await runners.uninstall_runner("wine", version)
    output.print(f"Wine version '{version}' has been removed.")


async def uninstall_runner_by_name(output: CommandOutput, runner_name: str) -> None:
    try:
        installed = await runners.is_runner_installed(runner_name)
    except InvalidRunnerError:
        logger.error("Failed to import Runner: %s", runner_name)
        return
    if not installed:
        output.print(f"Runner '{runner_name}' is not installed.")
    elif not await runners.can_uninstall_runner(runner_name):
        output.print(f"Runner '{runner_name}' cannot be uninstalled.")
    else:
        await runners.uninstall_runner(runner_name)
        output.print(f"'{runner_name}' has been uninstalled.")
