"""Edit game, runner and system options through configuration forms."""

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest

from lutris import settings
from lutris.backend import configuration, events
from lutris.backend.models import ConfigForm, ConfigOptionInfo, GameInfo
from lutris.database import games as games_db
from lutris.exceptions import LutrisError
from lutris.util.test_config import setup_test_environment
from lutris.util.yaml import read_yaml_from_file, write_yaml_to_file
from tests.conftest import FakeMainLoop

setup_test_environment()


@pytest.fixture
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config = tmp_path / "config"
    (config / "games").mkdir(parents=True)
    (config / "runners").mkdir()
    monkeypatch.setattr(settings, "CONFIG_DIR", str(config))
    monkeypatch.setattr(settings, "RUNNERS_CONFIG_DIR", str(config / "runners"))
    return config


@pytest.fixture
def game_id(config_dir: Path) -> Iterator[str]:
    write_yaml_to_file({"game": {"exe": "/games/example/run.sh"}}, str(config_dir / "games" / "example-1.yml"))
    new_id = str(
        games_db.add_game(
            name="Config Example", slug="config-example", runner="linux", configpath="example-1", installed=1
        )
    )
    yield new_id
    games_db.delete_game(new_id)


def find(form: ConfigForm, section: str, key: str) -> ConfigOptionInfo:
    page = next(page for page in form.pages if page.section == section)
    return next(option for option in page.options if option.key == key)


def test_game_form_edits_and_saves_game_level_options(
    game_id: str, config_dir: Path, fake_main_loop: FakeMainLoop
) -> None:
    changed: list[GameInfo] = []
    registration = events.GAME_CHANGED.register(changed.append)

    async def run() -> None:
        form = await configuration.open_game_config(game_id)
        assert form.level == "game" and form.title == "Configure Config Example"
        assert [page.section for page in form.pages] == ["game", "runner", "system"]
        assert form.pages[1].description and form.pages[2].description

        exe = find(form, "game", "exe")
        assert exe.type == "file" and exe.value == "/games/example/run.sh" and exe.set_here

        form = await configuration.set_option(form.id, "game", "args", "--windowed")
        assert find(form, "game", "args").value == "--windowed"
        form = await configuration.set_option(form.id, "system", "disable_screen_saver", False)
        option = find(form, "system", "disable_screen_saver")
        assert option.type == "bool" and option.value is False and option.set_here
        form = await configuration.reset_option(form.id, "system", "disable_screen_saver")
        assert not find(form, "system", "disable_screen_saver").set_here

        await configuration.save_config(form.id)
        await configuration.close_config(form.id)
        with pytest.raises(LutrisError):
            await configuration.get_config_form(form.id)

    try:
        asyncio.run(run())
        fake_main_loop.run_pending()
    finally:
        registration.unregister()

    saved = read_yaml_from_file(str(config_dir / "games" / "example-1.yml"))
    assert saved["game"] == {"exe": "/games/example/run.sh", "args": "--windowed"}
    assert "disable_screen_saver" not in (saved.get("system") or {})
    assert [game.id for game in changed] == [game_id]


def test_unsaved_changes_are_discarded(game_id: str, config_dir: Path) -> None:
    async def run() -> None:
        form = await configuration.open_game_config(game_id)
        await configuration.set_option(form.id, "game", "args", "--unsaved")
        await configuration.close_config(form.id)
        reopened = await configuration.open_game_config(game_id)
        assert find(reopened, "game", "args").value == ""
        await configuration.close_config(reopened.id)

    asyncio.run(run())


def test_values_are_checked_against_the_option_type(game_id: str) -> None:
    async def run() -> None:
        form = await configuration.open_game_config(game_id)
        with pytest.raises(LutrisError):
            await configuration.set_option(form.id, "system", "disable_screen_saver", "maybe")
        with pytest.raises(LutrisError):
            await configuration.set_option(form.id, "game", "no_such_option", "x")
        form = await configuration.set_option(form.id, "system", "env", {" DXVK_HUD ": "1", "": "dropped"})
        assert find(form, "system", "env").value == {"DXVK_HUD": "1"}
        await configuration.close_config(form.id)

    asyncio.run(run())


def test_runner_and_system_forms_write_their_own_files(config_dir: Path) -> None:
    async def run() -> None:
        runner = await configuration.open_runner_config("linux")
        assert runner.level == "runner" and [page.section for page in runner.pages] == ["runner", "system"]
        await configuration.set_option(runner.id, "system", "env", {"RUNNER_LEVEL": "1"})
        await configuration.save_config(runner.id)
        await configuration.close_config(runner.id)

        system = await configuration.open_system_config()
        assert [page.section for page in system.pages] == ["system"]
        assert not system.pages[0].description
        game_path = find(system, "system", "game_path")
        assert game_path.type == "directory"
        await configuration.set_option(system.id, "system", "game_path", "/games")
        await configuration.save_config(system.id)
        await configuration.close_config(system.id)

        with pytest.raises(LutrisError):
            await configuration.open_runner_config("no-such-runner")

    asyncio.run(run())
    assert read_yaml_from_file(str(config_dir / "runners" / "linux.yml"))["system"] == {"env": {"RUNNER_LEVEL": "1"}}
    assert read_yaml_from_file(str(config_dir / "system.yml"))["system"]["game_path"] == "/games"


def test_choices_mark_the_default_and_keep_unknown_values(config_dir: Path) -> None:
    write_yaml_to_file({"system": {"gamescope_window_mode": "--gone"}}, str(config_dir / "system.yml"))

    async def run() -> None:
        form = await configuration.open_system_config()
        mode = find(form, "system", "gamescope_window_mode")
        assert mode.type == "choice"
        assert mode.choices[0].value == "--gone" and mode.value == "--gone"
        assert "no longer available" in mode.warning
        assert [choice.value for choice in mode.choices if choice.label.endswith("(default)")] == ["-f"]
        assert mode.default == "-f" and mode.default_label
        await configuration.close_config(form.id)

    asyncio.run(run())
