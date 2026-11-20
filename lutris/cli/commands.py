"""Run the commands that need no GUI, whichever frontend the command line reached.

The command-line frontend runs them when no Lutris instance is running; when one
is, Gio forwards the command line to it, and its frontend runs them the same way.
They only use the backend's API (lutris.backend).
"""

import asyncio
import logging
from gettext import gettext as _

from gi.repository import Gio, GLib

from lutris.backend import games, processes, saves
from lutris.backend.errors import LutrisError
from lutris.backend.models import GameInfo
from lutris.backend.startup import start_backend
from lutris.cli import listing, runners
from lutris.cli.options import LUTRIS_EXPERIMENTAL_FEATURES_ENABLED
from lutris.cli.output import CommandOutput
from lutris.delegates import LaunchUIDelegate
from lutris.util import log
from lutris.util.log import logger

# The exit status of a command the user interrupted, as a shell reports SIGINT
INTERRUPTED_STATUS = 130


def start_lutris(options: GLib.VariantDict, run_checks_async: bool) -> None:
    """Get Lutris ready to run a command line: logging, then the backend. The startup
    checks run on a thread if run_checks_async is set."""
    if options.contains("debug"):
        log.console_handler.setFormatter(log.DEBUG_FORMATTER)
        logger.setLevel(logging.DEBUG)
    start_backend(run_checks_async)


async def handle_command_line(command_line: Gio.ApplicationCommandLine, launch_ui_delegate: LaunchUIDelegate) -> int:
    """Run the text command a command line names, then report its exit status to the
    invoking process and release it; returns that status too, as GLib doesn't report
    it for a command line that this process received from itself."""
    output = CommandOutput(command_line)
    status = 1
    try:
        status = await run_text_command(command_line.get_options_dict(), output, launch_ui_delegate) or 0
    except asyncio.CancelledError:
        status = INTERRUPTED_STATUS
        raise
    except LutrisError as ex:
        output.print_error(ex.message)
    except Exception as ex:
        logger.exception("The command failed: %s", ex)
        output.print_error(str(ex))
    finally:
        command_line.set_exit_status(status)
        command_line.done()
    return status


def _get_string(options: GLib.VariantDict, name: str) -> str | None:
    value = options.lookup_value(name)
    return value.get_string() if value else None


async def run_text_command(  # noqa: C901
    options: GLib.VariantDict, output: CommandOutput, launch_ui_delegate: LaunchUIDelegate
) -> int | None:
    """Run the command the options name, and return its exit status; if they name
    none that needs no GUI, return None. launch_ui_delegate answers what generating
    a script asks."""
    if search := _get_string(options, "output-script"):
        return await write_game_script(output, search, launch_ui_delegate)

    if options.contains("list-games"):
        await listing.list_games(options, output)
        return 0

    if service := _get_string(options, "list-service-games"):
        await listing.list_service_games(options, output, service)
        return 0

    if options.contains("list-all-service-games"):
        await listing.list_service_games(options, output)
        return 0

    if options.contains("list-steam-games"):
        await listing.print_steam_list(output)
        return 0

    if options.contains("list-steam-folders"):
        await listing.print_steam_folders(output)
        return 0

    if options.contains("list-runners"):
        await listing.print_runners(output)
        return 0

    if options.contains("list-wine-versions"):
        await listing.print_wine_runners(output)
        return 0

    if runner := _get_string(options, "install-runner"):
        await runners.install_runner(output, runner)
        return 0

    if runner := _get_string(options, "uninstall-runner"):
        await runners.uninstall_runner(output, runner)
        return 0

    dest_dir = _get_string(options, "dest")
    if slug := _get_string(options, "export"):
        if not dest_dir:
            output.print_error(_("No destination dir given"))
            return 1
        await games.export_game(slug, output.get_path(dest_dir))
        return 0

    if file_path := _get_string(options, "import"):
        if not dest_dir:
            output.print_error(_("No destination dir given"))
            return 1
        await games.import_game(output.get_path(file_path), output.get_path(dest_dir))
        return 0

    if LUTRIS_EXPERIMENTAL_FEATURES_ENABLED:
        if slug := _get_string(options, "save-stats"):
            if game := await find_game(output, slug):
                await saves.show_save_stats(game.id, output_format="json" if options.contains("json") else "text")
            return 0
        if slug := _get_string(options, "save-upload"):
            if game := await find_game(output, slug):
                await saves.upload_saves(game.id)
            return 0
        if slug := _get_string(options, "save-check"):
            if game := await find_game(output, slug):
                await saves.check_saves(game.id)
            return 0

    if command := _get_string(options, "exec"):
        return await processes.run_command(command)

    return None


async def write_game_script(output: CommandOutput, search: str, launch_ui_delegate: LaunchUIDelegate) -> int:
    """Write a script that runs a game without the client (--output-script), in the
    working directory."""
    game = await games.find_game(search)
    if not game:
        logger.warning(
            "No valid game (%s) provided to generate the script. Use the -l option to find suitable games!",
            search,
        )
        return 1
    await games.write_game_script(game.id, output.get_path(f"{game.slug}.sh"), launch_ui_delegate)
    return 0


async def find_game(output: CommandOutput, slug: str) -> GameInfo | None:
    """Return the one game matching a slug, or None after saying why there isn't one."""
    matches = await games.find_games_by_slug(slug)
    if len(matches) > 1:
        output.print_error("Multiple games matching %s: %s" % (slug, ",".join(game.slug for game in matches)))
        return None
    if not matches:
        output.print_error("No matching game for %s" % slug)
        return None
    return matches[0]
