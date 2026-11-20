"""Find and check the install scripts a library game can use, without running any.

A catalog keeps the scripts it found on the backend's side; frontends see
InstallerChoice metadata and refer to a script by the catalog's id and the
choice's id. Selecting a choice checks what installing with it involves, and
never runs the script.
"""

import asyncio
import copy
from collections import OrderedDict
from gettext import gettext as _
from typing import Any
from uuid import uuid4

from lutris.backend.models import InstallerCatalog, InstallerChoice, InstallerSelection
from lutris.database import games as games_db
from lutris.exceptions import LutrisError
from lutris.installer import get_installers
from lutris.installer.errors import MissingGameDependencyError
from lutris.installer.interpreter import ScriptInterpreter
from lutris.runners import get_runner_human_name
from lutris.util.http import HTTPError
from lutris.util.log import logger

# How many catalogs are kept for frontends that never close theirs
_CATALOG_LIMIT = 8
_REQUIRED_FIELDS = ("name", "game_slug", "slug", "runner", "version", "script")

type _Script = dict[str, Any]

# The scripts of each catalog by choice id, oldest catalog first
_catalogs: OrderedDict[str, dict[str, _Script]] = OrderedDict()


def can_install_game(installed: bool, slug: str | None, service: str | None) -> bool:
    """Test whether a library entry can be installed with a Lutris.net install script."""
    return not installed and bool(slug) and service in (None, "", "lutris")


async def find_game_installers(game_id: str) -> InstallerCatalog:
    """Fetch the Lutris.net install scripts for an uninstalled library game."""
    row = games_db.get_game_by_field(game_id, "id")
    if row is None:
        raise LutrisError(_("This game is no longer in the library."))
    if not can_install_game(bool(row.get("installed")), row.get("slug"), row.get("service")):
        raise LutrisError(_("Lutris can't install %s with an install script.") % row["name"])
    return await find_installers(row["slug"])


async def find_installers(game_slug: str) -> InstallerCatalog:
    """Fetch the Lutris.net install scripts for a game, by its slug."""
    try:
        scripts = await asyncio.to_thread(get_installers, game_slug=game_slug)
    except (HTTPError, RuntimeError, OSError, ValueError) as error:
        logger.warning("Unable to fetch the installers for %s: %s", game_slug, error)
        raise LutrisError(_("The installers for this game could not be downloaded.")) from error
    scripts = [script for script in scripts if _is_usable(script)]
    if not scripts:
        raise LutrisError(_("No installer available."))

    catalog_id = uuid4().hex
    by_choice = {str(index): script for index, script in enumerate(scripts)}
    _catalogs[catalog_id] = by_choice
    while len(_catalogs) > _CATALOG_LIMIT:
        _catalogs.popitem(last=False)
    return InstallerCatalog(
        id=catalog_id,
        game_name=scripts[0]["name"],
        game_slug=game_slug,
        choices=tuple(_to_choice(choice_id, script) for choice_id, script in by_choice.items()),
    )


async def close_catalog(catalog_id: str) -> None:
    """Forget a catalog's scripts once the frontend is done with it."""
    _catalogs.pop(catalog_id, None)


async def select_installer(catalog_id: str, choice_id: str) -> InstallerSelection:
    """Check a script can be used here, and say what installing with it involves."""
    script = copy_script(catalog_id, choice_id)
    return await asyncio.to_thread(_check_script, catalog_id, choice_id, script)


def copy_script(catalog_id: str, choice_id: str) -> _Script:
    """Return a copy of a catalog's script for the backend to use, leaving the catalog's intact."""
    try:
        script = _catalogs[catalog_id][choice_id]
    except KeyError as error:
        raise LutrisError(_("This installer is no longer available. Open the game's installers again.")) from error
    _catalogs.move_to_end(catalog_id)
    return copy.deepcopy(script)


def _is_usable(script: _Script) -> bool:
    missing = [field for field in _REQUIRED_FIELDS if not script.get(field)]
    if missing:
        logger.warning("Skipping install script %s, missing %s", script.get("slug"), ", ".join(missing))
        return False
    if not isinstance(script["script"], dict):
        logger.warning("Skipping install script %s, its script isn't a mapping", script["slug"])
        return False
    files = script["script"].get("files") or []
    if not isinstance(files, list) or any(not isinstance(file, dict) or len(file) != 1 for file in files):
        logger.warning("Skipping install script %s, its files are malformed", script["slug"])
        return False
    return True


def _text(script: _Script, key: str) -> str:
    value = script.get(key)
    return str(value).strip() if value else ""


def _to_choice(choice_id: str, script: _Script) -> InstallerChoice:
    return InstallerChoice(
        id=choice_id,
        version=script["version"],
        runner=script["runner"],
        runner_name=get_runner_human_name(script["runner"]),
        description=_text(script, "description"),
        notes=_text(script, "notes"),
        credits=_text(script, "credits"),
    )


def _check_script(catalog_id: str, choice_id: str, script: _Script) -> InstallerSelection:
    try:
        interpreter = ScriptInterpreter(script)
    except MissingGameDependencyError as error:
        return InstallerSelection(
            catalog_id=catalog_id,
            choice_id=choice_id,
            game_name=script["name"],
            version=script["version"],
            creates_game_folder=False,
            default_directory="",
            runners_to_install=(),
            required_game_slug=error.slug,
        )
    installer = interpreter.installer
    runners = interpreter.get_runners_to_install()
    return InstallerSelection(
        catalog_id=catalog_id,
        choice_id=choice_id,
        game_name=installer.game_name,
        version=installer.version,
        creates_game_folder=installer.creates_game_folder,
        default_directory=interpreter.target_path or "",
        runners_to_install=tuple(runner.human_name for runner in runners),
    )
