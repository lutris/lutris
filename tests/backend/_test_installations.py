"""Run install scripts end to end with local files, a local web server and library data."""

import asyncio
import functools
import hashlib
import http.server
import shutil
import tarfile
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from lutris import settings
from lutris.backend import events, installations, installers, runners
from lutris.backend.models import GameInfo, InstallationInfo, InstallerCatalog
from lutris.database import games as games_db
from lutris.delegates import InstallUIDelegate
from lutris.exceptions import LutrisError
from lutris.installer import interpreter
from lutris.installer.installer import LutrisInstaller
from lutris.runners.runner import Runner
from lutris.util.test_config import setup_test_environment
from lutris.util.wine import proton
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


def test_runner_manager_downloads_and_removes_an_architecture_suffixed_proton_build(
    server: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tag = "GE-Proton11-7"
    build_name = tag + "-x86_64"
    compat_dir = tmp_path / "compatibilitytools.d"
    alternate = tmp_path / "other-tools"
    cache = tmp_path / "cache"
    alternate.mkdir()
    cache.mkdir()
    previous = alternate / "GE-Proton10-2"
    previous.mkdir()
    (previous / "proton").touch()
    source = tmp_path / "proton"
    source.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    source.chmod(0o755)
    archive = tmp_path / "served" / f"{build_name}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(source, arcname=f"{build_name}/proton")
    checksum = hashlib.sha512(archive.read_bytes()).hexdigest()
    (tmp_path / "served" / "checksum").write_text(f"{checksum}  {archive.name}\n", encoding="utf-8")
    monkeypatch.setattr(settings, "CACHE_DIR", str(cache))
    monkeypatch.setattr(proton.LINUX_SYSTEM, "arch", "x86_64")
    monkeypatch.setattr(proton, "get_steam_compat_dir", lambda: str(compat_dir))
    monkeypatch.setattr(proton, "_iter_proton_locations", lambda: iter((str(alternate), str(compat_dir))))
    monkeypatch.setattr(
        proton, "get_ge_proton_release_urls", lambda _tag: (f"{server}/{archive.name}", server + "/checksum")
    )
    progress: list[tuple[str, float | None]] = []

    async def no_questions(*args: str) -> Any:
        pytest.fail(f"Unexpected runner prompt: {args!r}")

    def trash(path: str, completion: Callable[[], None], _error: Callable[[Exception], None]) -> None:
        shutil.move(path, tmp_path / "trash")
        completion()

    monkeypatch.setattr(runners.system, "remove_folder", trash)
    interaction = runners.RunnerInstallInteraction(
        lambda text, fraction: progress.append((text, fraction)), no_questions, no_questions
    )

    async def run() -> None:
        await asyncio.wait_for(runners.install_runner("wine", tag, interaction=interaction), timeout=10)
        assert (compat_dir / build_name / "proton").is_file()
        assert (await runners.list_proton_builds((tag,)))[0] == runners.ProtonBuild(tag, True, True)
        assert progress and progress[0][0] == "Downloading…"
        await runners.uninstall_runner("wine", tag)
        assert (tmp_path / "trash" / "proton").is_file()
        with pytest.raises(LutrisError, match="outside"):
            await runners.uninstall_runner("wine", previous.name)
        assert previous.is_dir()

    proton.get_proton_versions.cache_clear()
    try:
        asyncio.run(run())
    finally:
        proton.get_proton_versions.cache_clear()


def test_runner_manager_asks_for_firmware_from_the_main_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    answers: list[str | None] = []

    class FirmwareRunner(Runner):
        def install(
            self,
            install_ui_delegate: InstallUIDelegate,
            version: str | None = None,
            callback: Callable[[], None] | None = None,
        ) -> None:
            assert install_ui_delegate.show_install_yesno_inquiry("Continue?", "Firmware")
            answers.append(install_ui_delegate.show_install_file_inquiry("Use a BIOS?", "Firmware", "Select a BIOS"))

        def is_installed(self, flatpak_allowed: bool = True) -> bool:
            return answers == ["/games/firmware/bios.bin"]

    monkeypatch.setattr(runners, "import_runner", lambda _name: FirmwareRunner)

    async def run() -> None:
        loop = asyncio.get_running_loop()

        async def question(title: str, message: str) -> bool:
            assert (title, message) == ("Firmware", "Continue?")
            assert asyncio.get_running_loop() is loop
            return True

        async def file(title: str, question: str, message: str) -> str:
            assert (title, question, message) == ("Firmware", "Use a BIOS?", "Select a BIOS")
            assert asyncio.get_running_loop() is loop
            return "/games/firmware/bios.bin"

        interaction = runners.RunnerInstallInteraction(lambda _status, _fraction: None, question, file)
        await runners.install_runner("firmware", interaction=interaction)

    asyncio.run(run())
    assert answers == ["/games/firmware/bios.bin"]


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


def make_catalog(files: list[dict[str, str]], commands: list[Any]) -> InstallerCatalog:
    script = {
        "name": "Installations Test",
        "game_slug": SLUG,
        "slug": SLUG + "-local",
        "version": "Local",
        "runner": "linux",
        "script": {"game": {"exe": "$GAMEDIR/payload.txt"}, "files": files, "installer": commands},
    }
    return installers._catalog_from_scripts([script])


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


async def start(catalog: InstallerCatalog, directory: Path) -> InstallationInfo:
    return await installations.start_installation(catalog.id, catalog.choices[0].id, str(directory))


def test_installs_downloaded_and_chosen_files_and_asks_the_script_menu(
    game_id: str, server: str, tmp_path: Path, fake_main_loop: FakeMainLoop
) -> None:
    manual = tmp_path / "manual.txt"
    manual.write_text("chosen by the user", encoding="utf-8")
    catalog = make_catalog(
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
        info = await start(catalog, target)
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
    game_id: str, tmp_path: Path, fake_main_loop: FakeMainLoop
) -> None:
    catalog = make_catalog(
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
        info = await start(catalog, target)
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


def test_failed_commands_report_the_error(game_id: str, tmp_path: Path, fake_main_loop: FakeMainLoop) -> None:
    catalog = make_catalog([], [{"move": {"src": "$GAMEDIR/missing", "dst": "$GAMEDIR/elsewhere"}}])
    tracker = Tracker(fake_main_loop)

    async def run() -> None:
        info = await start(catalog, tmp_path / "Games" / SLUG)
        failed = await tracker.wait_for(lambda info: info.stage == "failed")
        assert "missing" in failed.status
        await installations.close_installation(info.id)

    try:
        asyncio.run(run())
    finally:
        tracker.close()


@pytest.mark.parametrize("cancel", [False, True])
def test_steam_install_waits_for_manifest_and_keeps_steam_data(
    cancel: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_main_loop: FakeMainLoop
) -> None:
    from lutris.installer import steam_installer
    from lutris.services.steam import SteamService
    from lutris.util.steam.vdfutils import vdf_write

    appid = "298341"
    steamapps = tmp_path / "steamapps"
    target = steamapps / "common" / "Fixture"
    target.mkdir(parents=True)
    payload = target / "game.bin"
    payload.touch()
    manifest = steamapps / f"appmanifest_{appid}.acf"
    vdf_write(str(manifest), {"AppState": {"installdir": target.name, "StateFlags": 2}})
    (tmp_path / "config" / "games").mkdir(parents=True)
    monkeypatch.setattr(settings, "CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setattr(settings, "INSTALLER_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(interpreter, "fetch_game_artwork", lambda slug: 0)
    monkeypatch.setattr(LutrisInstaller, "_get_discord_id_from_api", lambda self: None)
    monkeypatch.setattr(steam_installer, "get_steamapps_dirs", lambda: [str(steamapps)])
    monkeypatch.setattr(steam_installer.steam.steam, "is_installed", lambda self: True)
    service = SteamService()
    script = service.generate_installer({"appid": appid, "name": "Steam Fixture", "slug": "steam-fixture"})
    catalog = installers._catalog_from_scripts([script], installers._Origin(service, appid))
    tracker = Tracker(fake_main_loop)

    async def run() -> None:
        loop = asyncio.get_running_loop()
        requested = asyncio.Event()

        def request_install(_steam: steam_installer.steam.steam, requested_appid: str) -> None:
            assert requested_appid == appid
            loop.call_soon_threadsafe(requested.set)

        monkeypatch.setattr(steam_installer.steam.steam, "install_game", request_install)
        info = await start(catalog, tmp_path)
        try:
            files = (await tracker.wait_for_stage("files")).files
            assert [(file.provider, file.ready) for file in files] == [("steam", True)]
            await installations.start_files(info.id)
            await asyncio.wait_for(requested.wait(), timeout=2)
            assert (await installations.get_installation(info.id)).stage == "downloading"
            if cancel:
                await installations.cancel_installation(info.id)
                await tracker.wait_for_stage("cancelled")
                assert not games_db.get_games(filters={"service": "steam", "service_id": appid})
            else:
                vdf_write(str(manifest), {"AppState": {"installdir": target.name, "StateFlags": 4}})
                result = await tracker.wait_for_stage("finished")
                row = games_db.get_game_by_field(result.game_id, "id")
                assert row is not None and row["directory"] == str(target) and row["service_id"] == appid
        finally:
            await installations.close_installation(info.id)
            for row in games_db.get_games(filters={"service": "steam", "service_id": appid}):
                games_db.delete_game(row["id"])

    try:
        asyncio.run(run())
    finally:
        tracker.close()
    assert payload.is_file()


def test_runner_prompt_releases_the_worker_on_cancel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_main_loop: FakeMainLoop
) -> None:
    answers: list[bool] = []

    class PromptRunner(Runner):
        name = "firmware"

        def install(
            self,
            install_ui_delegate: InstallUIDelegate,
            version: str | None = None,
            callback: Callable[[], None] | None = None,
        ) -> None:
            answers.append(install_ui_delegate.show_install_yesno_inquiry("Install firmware?", "Firmware"))

    monkeypatch.setattr(settings, "INSTALLER_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(interpreter.ScriptInterpreter, "get_runners_to_install", lambda self: [PromptRunner()])
    catalog = make_catalog([], [{"write_file": {"file": "$GAMEDIR/game.txt", "content": "test"}}])
    tracker = Tracker(fake_main_loop)

    async def run() -> None:
        info = await start(catalog, tmp_path / "game")
        try:
            prompt = (await tracker.wait_for_stage("runner_prompt")).runner_prompt
            assert prompt and prompt.question == "Install firmware?"
            await installations.cancel_installation(info.id)
            await tracker.wait_for_stage("cancelled")
        finally:
            await installations.close_installation(info.id)

    try:
        asyncio.run(run())
    finally:
        tracker.close()
    assert answers == [False]
    assert not (tmp_path / "game").exists()
