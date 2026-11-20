"""The options of the `lutris` command, shared by every frontend that handles them.

Gio forwards a command line to the primary instance of the application with the
options already parsed, so whichever frontend runs it must define the same ones.
"""

import os
from gettext import gettext as _

from gi.repository import Gio, GLib

LUTRIS_EXPERIMENTAL_FEATURES_ENABLED = os.environ.get("LUTRIS_EXPERIMENTAL_FEATURES_ENABLED") == "1"

# Options that name a command needing no GUI, in the order they're looked for
TEXT_COMMANDS = (
    "output-script",
    "list-games",
    "list-service-games",
    "list-all-service-games",
    "list-steam-games",
    "list-steam-folders",
    "list-runners",
    "list-wine-versions",
    "install-runner",
    "uninstall-runner",
    "export",
    "import",
    "save-stats",
    "save-upload",
    "save-check",
    "exec",
)

# Name, short name, argument, description and argument's description of each option
_OPTIONS: list[tuple[str, str, GLib.OptionArg, str, str | None]] = [
    ("version", "v", GLib.OptionArg.NONE, _("Print the version of Lutris and exit"), None),
    ("debug", "d", GLib.OptionArg.NONE, _("Show debug messages"), None),
    ("install", "i", GLib.OptionArg.STRING, _("Install a game from a yml file"), None),
    ("force", "f", GLib.OptionArg.NONE, _("Force updates"), None),
    ("output-script", "b", GLib.OptionArg.STRING, _("Generate a bash script to run a game without the client"), None),
    ("exec", "e", GLib.OptionArg.STRING, _("Execute a program with the Lutris Runtime"), None),
    ("list-games", "l", GLib.OptionArg.NONE, _("List all games in database"), None),
    ("installed", "o", GLib.OptionArg.NONE, _("Only list installed games"), None),
    ("list-steam-games", "s", GLib.OptionArg.NONE, _("List available Steam games"), None),
    ("list-steam-folders", "", GLib.OptionArg.NONE, _("List all known Steam library folders"), None),
    ("list-runners", "", GLib.OptionArg.NONE, _("List all known runners"), None),
    ("list-wine-versions", "", GLib.OptionArg.NONE, _("List all known Wine versions"), None),
    ("list-all-service-games", "a", GLib.OptionArg.NONE, _("List all games for all services in database"), None),
    ("list-service-games", "", GLib.OptionArg.STRING, _("List all games for provided service in database"), None),
    ("install-runner", "r", GLib.OptionArg.STRING, _("Install a Runner"), None),
    ("uninstall-runner", "u", GLib.OptionArg.STRING, _("Uninstall a Runner"), None),
    ("export", "", GLib.OptionArg.STRING, _("Export a game"), None),
    ("import", "", GLib.OptionArg.STRING, _("Import a game"), None),
]

_EXPERIMENTAL_OPTIONS: list[tuple[str, str, GLib.OptionArg, str, str | None]] = [
    ("save-stats", "", GLib.OptionArg.STRING, _("Show statistics about a game saves"), None),
    ("save-upload", "", GLib.OptionArg.STRING, _("Upload saves"), None),
    ("save-check", "", GLib.OptionArg.STRING, _("Verify status of save syncing"), None),
]

_FINAL_OPTIONS: list[tuple[str, str, GLib.OptionArg, str, str | None]] = [
    ("dest", "", GLib.OptionArg.STRING, _("Destination path for export"), None),
    ("json", "j", GLib.OptionArg.NONE, _("Display the list of games in JSON format"), None),
    ("reinstall", "", GLib.OptionArg.NONE, _("Reinstall game"), None),
    ("submit-issue", "", GLib.OptionArg.NONE, _("Submit an issue"), None),
    (GLib.OPTION_REMAINING, "", GLib.OptionArg.STRING_ARRAY, _("URI to open"), "URI"),
]


def add_options(application: Gio.Application) -> None:
    """Define the options of the `lutris` command on an application."""
    application.set_option_context_summary(
        _(
            "Run a game directly by adding the parameter lutris:rungame/game-identifier.\n"
            "If several games share the same identifier you can use the numerical ID "
            "(displayed when running lutris --list-games) and add "
            "lutris:rungameid/numerical-id.\n"
            "To install a game, add lutris:install/game-identifier."
        )
    )
    options = _OPTIONS + (_EXPERIMENTAL_OPTIONS if LUTRIS_EXPERIMENTAL_FEATURES_ENABLED else []) + _FINAL_OPTIONS
    for name, short_name, argument, description, argument_description in options:
        application.add_main_option(
            name,
            ord(short_name) if short_name else 0,
            GLib.OptionFlags.NONE,
            argument,
            description,
            argument_description,
        )


def is_text_command(options: GLib.VariantDict) -> bool:
    """True if the options name a command that needs no GUI."""
    return any(options.contains(name) for name in TEXT_COMMANDS)
