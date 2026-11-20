"""Update runtime components with their progress announced as plain data."""

import asyncio
import threading
from typing import Any

import pytest

from lutris.backend import runtime_updates
from lutris.backend.models import RuntimeUpdateStatus
from lutris.runtime import ComponentUpdater, RuntimeUpdater
from lutris.sysoptions import system_options
from lutris.util.progress_info import ProgressInfo
from tests.conftest import FakeMainLoop


class FakeComponent(ComponentUpdater):
    def __init__(self, name: str, release: threading.Event) -> None:
        self._name = name
        self._release = release
        self.installed = False

    @property
    def name(self) -> str:
        return self._name

    def install_update(self, updater: Any) -> None:
        self._release.wait(5)
        self.installed = True

    def get_progress(self) -> ProgressInfo:
        if self.installed:
            return ProgressInfo.ended(f"<b>Updated {self._name}</b>")
        return ProgressInfo(0.5, f"Downloading {self._name}")


def test_updates_report_progress_and_run_one_at_a_time(
    monkeypatch: pytest.MonkeyPatch, fake_main_loop: FakeMainLoop
) -> None:
    release = threading.Event()
    components = [FakeComponent("dxvk", release), FakeComponent("umu", release)]
    forced: list[bool] = []

    class FakeRuntimeUpdater:
        def __init__(self, force: bool = False) -> None:
            forced.append(force)

        def create_component_updaters(self) -> list[ComponentUpdater]:
            return list(components)

    monkeypatch.setattr(runtime_updates, "RuntimeUpdater", FakeRuntimeUpdater)
    monkeypatch.setattr(runtime_updates, "POLL_SECONDS", 0.01)
    monkeypatch.setattr(runtime_updates, "clear_wine_version_cache", lambda: None)
    statuses: list[RuntimeUpdateStatus] = []
    registration = runtime_updates.RUNTIME_UPDATE_CHANGED.register(statuses.append)

    async def run() -> None:
        first = asyncio.create_task(runtime_updates.update_runtime(force=True))
        await asyncio.sleep(0.05)
        assert (await runtime_updates.get_runtime_update_status()).running
        # A second request while one runs does nothing
        assert await runtime_updates.update_runtime() == ()
        release.set()
        assert await first == ("dxvk", "umu")

    try:
        asyncio.run(run())
        fake_main_loop.run_pending()
    finally:
        registration.unregister()

    assert forced == [True]
    assert statuses[0].running and statuses[0].components[0].status == "Downloading dxvk"
    assert statuses[0].components[0].fraction == 0.5
    final = statuses[-1]
    assert not final.running and [component.status for component in final.components] == ["Updated dxvk", "Updated umu"]
    assert all(component.finished for component in final.components)


def test_nothing_to_update(monkeypatch: pytest.MonkeyPatch, fake_main_loop: FakeMainLoop) -> None:
    class UpToDate:
        def __init__(self, force: bool = False) -> None:
            pass

        def create_component_updaters(self) -> list[ComponentUpdater]:
            return []

    monkeypatch.setattr(runtime_updates, "RuntimeUpdater", UpToDate)
    assert asyncio.run(runtime_updates.update_runtime()) == ()
    fake_main_loop.run_pending()


def test_the_old_lutris_runtime_libraries_are_not_downloaded() -> None:
    def component(name: str) -> dict[str, Any]:
        return {"name": name, "architecture": "all", "url": f"https://example.invalid/{name}.tar.xz"}

    names = ("umu", "gogdl", "winetricks", "Ubuntu-18.04-i686", "Ubuntu-18.04-x86_64", "network-tools")
    updaters = RuntimeUpdater._get_runtime_updaters({"runtimes": {name: component(name) for name in names}})
    assert [updater.name for updater in updaters] == ["umu", "gogdl", "winetricks"]


def test_system_options_no_longer_offer_the_lutris_runtime() -> None:
    options = {option["option"] for option in system_options}
    assert not {"disable_runtime", "prefer_system_libs"} & options
