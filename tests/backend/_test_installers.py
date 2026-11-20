"""Find and select install scripts for library games without running them."""

import asyncio
import os
from pathlib import Path
from typing import Any

import pytest

from lutris.backend import installers
from lutris.exceptions import LutrisError
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
def scripts() -> list[dict[str, Any]]:
    return [
        make_script("Native"),
        {"name": "Broken", "version": "Missing fields"},
        make_script("Extra", files=[{"one": "a", "two": "b"}]),
        {**make_script("Flatpak"), "runner": "flatpak"},
        make_script("Requires", requires="backend-installers-base-game"),
    ]


def test_catalog_lists_usable_plans_as_plain_choices(scripts: list[dict[str, Any]]) -> None:
    catalog = installers._catalog_from_scripts(scripts)

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


def test_unknown_sources_and_empty_catalogs_are_user_errors() -> None:
    with pytest.raises(LutrisError, match="source is unavailable"):
        asyncio.run(installers.find_store_installers("unknown-store", "42"))
    with pytest.raises(LutrisError, match="No installer available"):
        installers._catalog_from_scripts([])


def test_selecting_checks_the_script_without_running_it(scripts: list[dict[str, Any]]) -> None:
    async def run() -> None:
        catalog = installers._catalog_from_scripts(scripts)
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


def test_selection_reports_a_missing_required_game(scripts: list[dict[str, Any]]) -> None:
    async def run() -> None:
        catalog = installers._catalog_from_scripts(scripts)
        selection = await installers.select_installer(catalog.id, catalog.choices[1].id)

        assert selection.required_game_slug == "backend-installers-base-game"
        assert selection.default_directory == ""
        await installers.close_catalog(catalog.id)

    asyncio.run(run())


def test_closed_and_evicted_catalogs_are_forgotten(scripts: list[dict[str, Any]]) -> None:
    async def run() -> None:
        first = installers._catalog_from_scripts(scripts)
        await installers.close_catalog(first.id)
        with pytest.raises(LutrisError, match="no longer available"):
            await installers.select_installer(first.id, "0")

        oldest = installers._catalog_from_scripts(scripts)
        newer = [installers._catalog_from_scripts(scripts) for _ in range(installers._CATALOG_LIMIT)]
        with pytest.raises(LutrisError, match="no longer available"):
            await installers.select_installer(oldest.id, "0")
        for catalog in newer:
            await installers.close_catalog(catalog.id)

    asyncio.run(run())


def test_store_content_targets_the_selected_installation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from lutris.database import games as games_db
    from lutris.installer import InstallationKind
    from lutris.installer.interpreter import ScriptInterpreter
    from lutris.services.gog import GOGService

    slug = "shared-install-slug"
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    wrong = games_db.add_game(name="Other", slug=slug, installed=1, directory=str(first))
    expected = games_db.add_game(
        name="GOG game", slug=slug, installed=1, directory=str(second), service="gog", service_id="4780", runner="linux"
    )
    script = {**make_script("Patch", extends=slug), "game_slug": slug}
    monkeypatch.setattr(GOGService, "is_authenticated", lambda self: True)
    monkeypatch.setattr(GOGService, "get_update_installers", lambda self, row: [script])

    async def run() -> None:
        catalog = await installers.find_store_installers("gog", "4780", str(expected), InstallationKind.UPDATE)
        try:
            selection = await installers.select_installer(catalog.id, "0")
            assert not selection.creates_game_folder and selection.default_directory == str(second)
            interpreter, kind = await installers.build_interpreter(
                catalog.id, "0", ScriptInterpreter.InterpreterUIDelegate()
            )
            assert kind == InstallationKind.UPDATE
            assert interpreter.installer.save() == (str(expected), None)
        finally:
            await installers.close_catalog(catalog.id)

    try:
        asyncio.run(run())
    finally:
        games_db.delete_game(str(wrong))
        games_db.delete_game(str(expected))


@pytest.mark.parametrize(("windows_version", "locale"), [("win10", ""), ("win7", "ja_JP.utf8")])
def test_windows_setup_preserves_a_literal_executable_path(tmp_path: Path, windows_version: str, locale: str) -> None:
    from lutris.installer.interpreter import ScriptInterpreter

    executable = tmp_path / "Setup $GAMEDIR.exe"
    executable.touch()

    async def run() -> None:
        catalog = await installers.prepare_windows_setup("Test Game", str(executable), windows_version, locale)
        try:
            interpreter, _ = await installers.build_interpreter(
                catalog.id, "0", ScriptInterpreter.InterpreterUIDelegate()
            )
            assert interpreter.installer.runner == "wine"
            assert interpreter.installer.creates_game_folder
            assert interpreter._substitute("$SETUP_EXE") == str(executable)
            tasks = [step["task"] for step in interpreter.installer.script["installer"]]
            assert tasks[-1] == {"name": "wineexec", "executable": "$SETUP_EXE", "arch": "win64"}
            assert interpreter.script_env == ({"LC_ALL": locale} if locale else {})
            if windows_version == "win10":
                assert len(tasks) == 1
            else:
                assert tasks[0] == {"name": "winetricks", "app": windows_version, "arch": "win64"}
        finally:
            await installers.close_catalog(catalog.id)

    asyncio.run(run())
