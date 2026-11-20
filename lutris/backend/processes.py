"""Calls that run programs the way Lutris runs games."""

import asyncio

from lutris.monitored_command import exec_command
from lutris.util.log import logger


async def run_command(command: str) -> int:
    """Run a shell-style command line, monitored like a game, and
    return its exit code, 128 + the signal number if it was killed, or 1 if it could not
    be run. Cancelling the call stops the command."""
    logger.info("Running command '%s'", command)
    monitored_command = exec_command(command)
    if not monitored_command.game_process:
        return 1

    stopped = asyncio.get_running_loop().create_future()

    def on_stop() -> bool:
        if not stopped.done():
            stopped.set_result(None)
        return True

    # The child watch is a GLib source, so it can't fire before this awaits
    monitored_command.stop_func = on_stop
    try:
        await stopped
    except asyncio.CancelledError:
        monitored_command.stop()
        raise
    if not monitored_command.return_code:
        return 1  # the wrapper wrote no return code, so the command never ran
    return_code = int(monitored_command.return_code)
    if return_code < 0:  # killed by signal -return_code; exit with 128 + it, as a shell does
        return 128 - return_code
    return return_code
