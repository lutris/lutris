"""Run the commands that need no GUI, whichever frontend the command line reached.

The command-line frontend runs them when no Lutris instance is running; when one
is, Gio forwards the command line to it, and its frontend runs them the same way.
"""

import logging
from gettext import gettext as _

from gi.repository import GLib

from lutris import settings
from lutris.cli import listing, runners
from lutris.cli.options import LUTRIS_EXPERIMENTAL_FEATURES_ENABLED
from lutris.cli.output import CommandOutput
from lutris.database import games as games_db
from lutris.delegates import LaunchUIDelegate
from lutris.game import Game, export_game, import_game
from lutris.migrations import migrate
from lutris.monitored_command import exec_command
from lutris.startup import init_lutris, run_all_checks
from lutris.util import log
from lutris.util.log import logger
from lutris.util.savesync import save_check, show_save_stats, upload_save
from lutris.util.standalone_scripts import generate_script


def start_lutris(options: GLib.VariantDict, run_checks_async: bool) -> None:
    """Get Lutris ready to run a command line: logging, the database and the
    startup checks. The checks run on a thread if run_checks_async is set."""
    if options.contains("debug"):
        log.console_handler.setFormatter(log.DEBUG_FORMATTER)
        logger.setLevel(logging.DEBUG)

    logger.info("Starting Lutris %s", settings.VERSION)
    init_lutris()
    migrate()
    run_all_checks(async_ops=run_checks_async)


def _get_string(options: GLib.VariantDict, name: str) -> str | None:
    value = options.lookup_value(name)
    return value.get_string() if value else None


def run_text_command(
    options: GLib.VariantDict, output: CommandOutput, launch_ui_delegate: LaunchUIDelegate
) -> int | None:
    """Run the command the options name, and return its exit status; if they name
    none that needs no GUI, return None. launch_ui_delegate answers what generating
    a script asks."""
    if slug := _get_string(options, "output-script"):
        return write_game_script(output, slug, launch_ui_delegate)

    if options.contains("list-games"):
        listing.list_games(options, output)
        return 0

    if service := _get_string(options, "list-service-games"):
        listing.list_service_games(options, output, service)
        return 0

    if options.contains("list-all-service-games"):
        listing.list_service_games(options, output)
        return 0

    if options.contains("list-steam-games"):
        listing.print_steam_list(output)
        return 0

    if options.contains("list-steam-folders"):
        listing.print_steam_folders(output)
        return 0

    if options.contains("list-runners"):
        listing.print_runners(output)
        return 0

    if options.contains("list-wine-versions"):
        listing.print_wine_runners(output)
        return 0

    if runner := _get_string(options, "install-runner"):
        runners.install_runner(output, runner)
        return 0

    if runner := _get_string(options, "uninstall-runner"):
        runners.uninstall_runner(output, runner)
        return 0

    dest_dir = _get_string(options, "dest")
    if slug := _get_string(options, "export"):
        if not dest_dir:
            output.print_error(_("No destination dir given"))
            return 1
        export_game(slug, output.get_path(dest_dir))
        return 0

    if file_path := _get_string(options, "import"):
        if not dest_dir:
            output.print_error(_("No destination dir given"))
            return 1
        import_game(output.get_path(file_path), output.get_path(dest_dir))
        return 0

    if LUTRIS_EXPERIMENTAL_FEATURES_ENABLED:
        if slug := _get_string(options, "save-stats"):
            if game := find_game(output, slug):
                show_save_stats(game, output_format="json" if options.contains("json") else "text")
            return 0
        if slug := _get_string(options, "save-upload"):
            if game := find_game(output, slug):
                upload_save(game)
            return 0
        if slug := _get_string(options, "save-check"):
            if game := find_game(output, slug):
                save_check(game)
            return 0

    if command := _get_string(options, "exec"):
        return execute_command(command)

    return None


def write_game_script(output: CommandOutput, search: str, launch_ui_delegate: LaunchUIDelegate) -> int:
    """Write a script that runs a game without the client (--output-script), in the
    working directory."""
    game = (
        games_db.get_game_by_field(search, "id")
        or games_db.get_game_by_field(search, "slug")
        or games_db.get_game_by_field(search, "installer_slug")
    )
    if not game or not game["id"]:
        logger.warning(
            "No valid game (%s) provided to generate the script. Use the -l option to find suitable games!",
            search,
        )
        return 1
    generate_script(logger, launch_ui_delegate, game, output.get_path(f"{game['slug']}.sh"))
    return 0


def find_game(output: CommandOutput, slug: str) -> Game | None:
    """Return the one game matching a slug, or None after saying why there isn't one."""
    # First look for an exact match
    games = games_db.get_games_by_slug(slug)
    if not games:
        # Then look for matches
        games = games_db.get_games(searches={"slug": slug})
    if len(games) > 1:
        output.print_error("Multiple games matching %s: %s" % (slug, ",".join(game["slug"] for game in games)))
        return None
    if not games:
        output.print_error("No matching game for %s" % slug)
        return None
    return Game(games[0]["id"])


def execute_command(command: str) -> int:
    """Execute an arbitrary command in a Lutris context
    with the runtime enabled and monitored by a MonitoredCommand;
    returns its exit code, 128 + the signal number if it was killed,
    or 1 if it could not be run.
    """
    logger.info("Running command '%s'", command)
    monitored_command = exec_command(command)
    if not monitored_command.game_process:
        return 1

    loop = GLib.MainLoop()

    def on_stop() -> bool:
        loop.quit()
        return True

    # The child watch can't fire until the loop runs, so this can't miss the exit.
    monitored_command.stop_func = on_stop
    try:
        loop.run()
    except KeyboardInterrupt:
        monitored_command.stop()
    if not monitored_command.return_code:
        return 1  # the wrapper wrote no return code, so the command never ran
    return_code = int(monitored_command.return_code)
    if return_code < 0:  # killed by signal -return_code; exit with 128 + it, as a shell does
        return 128 - return_code
    return return_code
