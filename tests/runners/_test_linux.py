"""Steam Linux Runtime selection for native games."""

from pathlib import Path

import pytest

from lutris.exceptions import GameConfigError
from lutris.runner_interpreter import get_launch_parameters
from lutris.runners.linux import linux
from lutris.util.steam import runtime


@pytest.fixture
def steamapps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    steamapps = tmp_path / "Secondary Steam library" / "steamapps"
    monkeypatch.setattr(runtime, "get_steamapps_dirs", lambda: [str(steamapps)])
    monkeypatch.setattr(runtime, "search_in_steam_dirs", lambda _path: None)
    monkeypatch.setattr(runtime, "machine", lambda: "x86_64")
    monkeypatch.delenv("container", raising=False)
    monkeypatch.delenv("HOST_XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("STEAM_COMPAT_CLIENT_INSTALL_PATH", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    return steamapps


def make_launcher(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    path.chmod(0o755)
    return path


@pytest.mark.parametrize(
    ("key", "folder"),
    [
        ("soldier", "SteamLinuxRuntime_soldier"),
        ("sniper", "SteamLinuxRuntime_sniper"),
        ("steamrt4", "SteamLinuxRuntime_4"),
    ],
)
def test_container_runtime_uses_steam_library(steamapps: Path, key: str, folder: str) -> None:
    launcher = make_launcher(steamapps / "common" / folder / "run")
    assert runtime.get_runtime_command(key, {}) == [str(launcher), "--"]


def test_scout_uses_soldier_and_mounts_scout_tool(steamapps: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scout = make_launcher(steamapps / "common" / "SteamLinuxRuntime" / "scout-on-soldier-entry-point-v2")
    soldier = steamapps / "common" / "SteamLinuxRuntime_soldier" / "run"
    with pytest.raises(GameConfigError, match=r"steam://install/1391110"):
        runtime.get_runtime_command("scout", {})
    make_launcher(soldier)
    assert runtime.get_runtime_command("scout", {}) == [
        str(soldier),
        f"--filesystem={scout.parent}:rw",
        "--",
        str(scout),
        "--",
    ]
    client = steamapps.parent
    archive = client / "ubuntu12_32" / "steam-runtime.tar.xz"
    monkeypatch.setattr(runtime, "search_in_steam_dirs", lambda _path: str(archive))
    env: dict[str, str] = {}
    runtime.get_runtime_command("scout", env)
    assert env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] == str(client)


def test_runtime_can_use_umu_installation(steamapps: Path, tmp_path: Path) -> None:
    with pytest.raises(GameConfigError, match=r"steam://install/4183110"):
        runtime.get_runtime_command("steamrt4", {})
    launcher = make_launcher(tmp_path / "data" / "umu" / "steamrt4" / "run")
    assert runtime.get_runtime_command("steamrt4", {}) == [str(launcher), "--"]


def test_runtime_wraps_primary_and_alternate_launches(steamapps: Path, tmp_path: Path) -> None:
    launcher = make_launcher(steamapps / "common" / "SteamLinuxRuntime_sniper" / "run")
    primary = make_launcher(tmp_path / "primary game")
    alternate = make_launcher(tmp_path / "alternate game")
    runner = linux()
    runner.game_config.update(exe=str(primary), args="--original")
    runner.system_config.update(prefix_command="wrapper --flag")
    runner.runner_config["steam_linux_runtime"] = "sniper"
    info = runner.play()
    command, env = get_launch_parameters(runner, info)
    assert command == ["wrapper", "--flag", str(launcher), "--", "./primary game", "--original"]
    assert "LD_LIBRARY_PATH" not in env

    runner.apply_launch_config(info, {"exe": str(alternate), "args": '--name "a b"'})
    command, _ = get_launch_parameters(runner, info)
    assert command == ["wrapper", "--flag", str(launcher), "--", "./alternate game", "--name", "a b"]


def test_none_runs_against_no_library_overrides(tmp_path: Path) -> None:
    runner = linux()
    runner.game_config["exe"] = str(make_launcher(tmp_path / "game"))
    runner.system_config.update(use_sniper_runtime=True)

    command, env = get_launch_parameters(runner, runner.play())
    assert command == ["./game"]
    assert "LD_LIBRARY_PATH" not in env
