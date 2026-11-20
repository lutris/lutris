"""Run install scripts end to end with local files, a local web server and library data."""

import asyncio
import functools
import http.server
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from lutris import settings
from lutris.backend import events, installations, installers
from lutris.backend.models import GameInfo, InstallationInfo
from lutris.database import games as games_db
from lutris.exceptions import LutrisError
from lutris.installer import interpreter
from lutris.installer.installer import LutrisInstaller
from lutris.util.test_config import setup_test_environment
from tests.conftest import FakeMainLoop

setup_test_environment()

SLUG = "backend-installations-test"


@pytest.fixture
def server(tmp_path: Path) -> Iterator[str]:
    served = tmp_path / "served"
    served.mkdir()
    (served / "payload.txt").write_text("downloaded payload", encoding="utf-8")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(served))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture
def game_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    (tmp_path / "config" / "games").mkdir(parents=True)
    monkeypatch.setattr(settings, "CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setattr(settings, "INSTALLER_CACHE_DIR", str(tmp_path / "installer-cache"))
    monkeypatch.setattr(interpreter, "fetch_game_artwork", lambda slug: 0)
    monkeypatch.setattr(LutrisInstaller, "_get_discord_id_from_api", lambda self: None)
    new_id = str(games_db.add_game(name="Installations Test", slug=SLUG, runner="linux", installed=0))
    yield new_id
    games_db.delete_game(new_id)


def use_script(monkeypatch: pytest.MonkeyPatch, files: list[dict[str, str]], commands: list[Any]) -> None:
    script = {
        "name": "Installations Test",
        "game_slug": SLUG,
        "slug": SLUG + "-local",
        "version": "Local",
        "runner": "linux",
        "script": {"game": {"exe": "$GAMEDIR/payload.txt"}, "files": files, "installer": commands},
    }
    monkeypatch.setattr(installers, "get_installers", lambda game_slug: [script])


class Tracker:
    """Follows an installation's snapshots, pumping the fake main loop."""

    def __init__(self, main_loop: FakeMainLoop) -> None:
        self.main_loop = main_loop
        self.latest: InstallationInfo | None = None
        self.installed: list[GameInfo] = []
        self._registrations = [
            installations.INSTALLATION_CHANGED.register(self._on_changed),
            events.GAME_INSTALLED.register(self.installed.append),
        ]

    def _on_changed(self, info: InstallationInfo) -> None:
        self.latest = info

    async def wait_for(self, ready: Callable[[InstallationInfo], bool]) -> InstallationInfo:
        for _ in range(500):
            self.main_loop.run_pending()
            if self.latest and ready(self.latest):
                return self.latest
            await asyncio.sleep(0.01)
        pytest.fail(f"The installation did not get there; it is at {self.latest}")

    async def wait_for_stage(self, stage: str) -> InstallationInfo:
        info = await self.wait_for(lambda info: info.stage in (stage, "failed"))
        assert info.stage == stage, info.status + "\n" + info.error_details
        return info

    def close(self) -> None:
        for registration in self._registrations:
            registration.unregister()


async def start(game_id: str, directory: Path) -> InstallationInfo:
    catalog = await installers.find_game_installers(game_id)
    return await installations.start_installation(catalog.id, catalog.choices[0].id, str(directory))


def test_installs_downloaded_and_chosen_files_and_asks_the_script_menu(
    game_id: str, server: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_main_loop: FakeMainLoop
) -> None:
    manual = tmp_path / "manual.txt"
    manual.write_text("chosen by the user", encoding="utf-8")
    use_script(
        monkeypatch,
        [{"payload": server + "/payload.txt"}, {"manual": "N/A:Select the game manual"}],
        [
            {"input_menu": {"id": "LANG", "options": [{"en": "English"}, {"fr": "French"}], "preselect": "en"}},
            {"copy": {"src": "payload", "dst": "$GAMEDIR"}},
            {"copy": {"src": "manual", "dst": "$GAMEDIR"}},
            {"write_file": {"file": "$GAMEDIR/lang.txt", "content": "$INPUT_LANG"}},
        ],
    )
    target = tmp_path / "Games" / SLUG
    tracker = Tracker(fake_main_loop)

    async def run() -> None:
        info = await start(game_id, target)
        files = (await tracker.wait_for_stage("files")).files
        assert [(file.id, file.provider, file.ready) for file in files] == [
            ("payload", "download", True),
            ("manual", "user", False),
        ]
        assert files[1].hint == "Select the game manual"
        with pytest.raises(LutrisError):
            await installations.start_files(info.id)

        await installations.set_file_source(info.id, "manual", "user", str(manual))
        assert (await installations.get_installation(info.id)).files[1].ready
        await installations.start_files(info.id)

        menu = await tracker.wait_for_stage("menu")
        assert [(option.id, option.label) for option in menu.menu_options] == [("en", "English"), ("fr", "French")]
        assert menu.menu_preselect == "en"
        assert menu.can_remove_files
        with pytest.raises(LutrisError):
            await installations.answer_menu(info.id, "de")
        await installations.answer_menu(info.id, "fr")

        finished = await tracker.wait_for_stage("finished")
        assert finished.game_id == game_id
        await tracker.wait_for(lambda _info: bool(tracker.installed))
        await installations.close_installation(info.id)
        with pytest.raises(LutrisError):
            await installations.get_installation(info.id)

    try:
        asyncio.run(run())
    finally:
        tracker.close()

    assert (target / "payload.txt").read_text(encoding="utf-8") == "downloaded payload"
    assert (target / "manual.txt").read_text(encoding="utf-8") == "chosen by the user"
    assert (target / "lang.txt").read_text(encoding="utf-8") == "fr"
    row = games_db.get_game_by_field(game_id, "id")
    assert row is not None and row["installed"] == 1 and row["directory"] == str(target)
    assert [game.id for game in tracker.installed] == [game_id]


def test_cancelling_reverts_without_marking_the_game_installed(
    game_id: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_main_loop: FakeMainLoop
) -> None:
    use_script(
        monkeypatch,
        [],
        [
            {"write_file": {"file": "$GAMEDIR/started.txt", "content": "yes"}},
            {"input_menu": {"options": [{"go": "Go on"}]}},
            {"write_file": {"file": "$GAMEDIR/finished.txt", "content": "yes"}},
        ],
    )
    target = tmp_path / "Games" / SLUG
    tracker = Tracker(fake_main_loop)

    async def run() -> None:
        info = await start(game_id, target)
        await tracker.wait_for_stage("menu")
        await installations.cancel_installation(info.id, remove_files=False)
        await tracker.wait_for_stage("cancelled")
        with pytest.raises(LutrisError):
            await installations.answer_menu(info.id, "go")
        await installations.close_installation(info.id)

    try:
        asyncio.run(run())
    finally:
        tracker.close()

    assert (target / "started.txt").exists() and not (target / "finished.txt").exists()
    row = games_db.get_game_by_field(game_id, "id")
    assert row is not None and not row["installed"]


def test_failed_commands_report_the_error(
    game_id: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_main_loop: FakeMainLoop
) -> None:
    use_script(monkeypatch, [], [{"move": {"src": "$GAMEDIR/missing", "dst": "$GAMEDIR/elsewhere"}}])
    tracker = Tracker(fake_main_loop)

    async def run() -> None:
        info = await start(game_id, tmp_path / "Games" / SLUG)
        failed = await tracker.wait_for(lambda info: info.stage == "failed")
        assert "missing" in failed.status
        await installations.close_installation(info.id)

    try:
        asyncio.run(run())
    finally:
        tracker.close()
