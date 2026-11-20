"""Find and select install scripts for library games without running them."""

import asyncio
import os
from collections.abc import Iterator
from typing import Any

import pytest

from lutris.backend import installers
from lutris.database import games as games_db
from lutris.exceptions import LutrisError
from lutris.util.http import HTTPError
from lutris.util.test_config import setup_test_environment

setup_test_environment()

SLUG = "backend-installers-test"


def make_script(version: str, **script: Any) -> dict[str, Any]:
    return {
        "name": "Installer Test",
        "game_slug": SLUG,
        "slug": f"{SLUG}-{version.lower()}",
        "version": version,
        "runner": "linux",
        "description": f"  The {version} version  ",
        "notes": "Bring your own files",
        "credits": "",
        "script": {
            "game": {"exe": "$GAMEDIR/game.sh"},
            "files": [{"setup": "N/A:Select the game"}],
            "installer": [{"extract": {"file": "setup", "dst": "$GAMEDIR"}}],
            **script,
        },
    }


@pytest.fixture
def library() -> Iterator[dict[str, str]]:
    ids = {
        "uninstalled": str(games_db.add_game(name="Installer Test", slug=SLUG, runner="linux", installed=0)),
        "installed": str(games_db.add_game(name="Installed Test", slug=SLUG, runner="linux", installed=1)),
        "service": str(games_db.add_game(name="Service Test", slug=SLUG, service="gog", installed=0)),
    }
    yield ids
    for game_id in ids.values():
        games_db.delete_game(game_id)


@pytest.fixture
def scripts(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    found = [
        make_script("Native"),
        {"name": "Broken", "version": "Missing fields"},
        make_script("Extra", files=[{"one": "a", "two": "b"}]),
        {**make_script("Flatpak"), "runner": "flatpak"},
        make_script("Requires", requires="backend-installers-base-game"),
    ]
    requested: list[str] = []

    def get_installers(game_slug: str) -> list[dict[str, Any]]:
        requested.append(game_slug)
        return found

    monkeypatch.setattr(installers, "get_installers", get_installers)
    return found


def test_catalog_lists_usable_scripts_as_plain_choices(library: dict[str, str], scripts: list[dict[str, Any]]) -> None:
    catalog = asyncio.run(installers.find_game_installers(library["uninstalled"]))

    assert catalog.game_name == "Installer Test"
    assert catalog.game_slug == SLUG
    assert [choice.version for choice in catalog.choices] == ["Native", "Requires"]
    native = catalog.choices[0]
    assert native.runner == "linux"
    assert native.runner_name == "Linux"
    assert native.description == "The Native version"
    assert native.notes == "Bring your own files"
    assert native.credits == ""
    asyncio.run(installers.close_catalog(catalog.id))


@pytest.mark.parametrize("kind", ["installed", "service"])
def test_installed_and_store_games_are_not_offered_scripts(
    library: dict[str, str], scripts: list[dict[str, Any]], kind: str
) -> None:
    with pytest.raises(LutrisError):
        asyncio.run(installers.find_game_installers(library[kind]))


def test_fetch_failures_and_empty_catalogs_are_user_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def unreachable(game_slug: str) -> list[dict[str, Any]]:
        raise HTTPError("Unreachable")

    monkeypatch.setattr(installers, "get_installers", unreachable)
    with pytest.raises(LutrisError, match="could not be downloaded"):
        asyncio.run(installers.find_installers(SLUG))

    monkeypatch.setattr(installers, "get_installers", lambda game_slug: [])
    with pytest.raises(LutrisError, match="No installer available"):
        asyncio.run(installers.find_installers(SLUG))


def test_selecting_checks_the_script_without_running_it(library: dict[str, str], scripts: list[dict[str, Any]]) -> None:
    async def run() -> None:
        catalog = await installers.find_game_installers(library["uninstalled"])
        selection = await installers.select_installer(catalog.id, catalog.choices[0].id)

        assert selection.catalog_id == catalog.id
        assert selection.version == "Native"
        assert selection.creates_game_folder
        assert selection.default_directory.endswith(os.sep + SLUG)
        assert not os.path.exists(selection.default_directory)
        assert selection.runners_to_install == ()
        assert selection.required_game_slug is None
        # Selecting again starts from the script as it was found
        assert await installers.select_installer(catalog.id, catalog.choices[0].id) == selection
        await installers.close_catalog(catalog.id)

    asyncio.run(run())
    assert "requires" not in scripts[0]["script"]


def test_selection_reports_a_missing_required_game(library: dict[str, str], scripts: list[dict[str, Any]]) -> None:
    async def run() -> None:
        catalog = await installers.find_game_installers(library["uninstalled"])
        selection = await installers.select_installer(catalog.id, catalog.choices[1].id)

        assert selection.required_game_slug == "backend-installers-base-game"
        assert selection.default_directory == ""
        await installers.close_catalog(catalog.id)

    asyncio.run(run())


def test_closed_and_evicted_catalogs_are_forgotten(scripts: list[dict[str, Any]]) -> None:
    async def run() -> None:
        first = await installers.find_installers(SLUG)
        await installers.close_catalog(first.id)
        with pytest.raises(LutrisError, match="no longer available"):
            await installers.select_installer(first.id, "0")

        oldest = await installers.find_installers(SLUG)
        newer = [await installers.find_installers(SLUG) for _ in range(installers._CATALOG_LIMIT)]
        with pytest.raises(LutrisError, match="no longer available"):
            await installers.select_installer(oldest.id, "0")
        for catalog in newer:
            await installers.close_catalog(catalog.id)

    asyncio.run(run())
