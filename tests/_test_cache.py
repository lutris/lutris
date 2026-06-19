import os
import json

import pytest

from lutris import cache


def test_get_installer_cache_entries(monkeypatch, tmp_path):
    cache_root = tmp_path / "installer"
    game_cache = cache_root / "some-game" / "gog"
    game_cache.mkdir(parents=True)
    installer = game_cache / "setup.exe"
    installer.write_bytes(b"installer")
    (game_cache / "setup.exe.cache_lock").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(cache, "get_cache_path", lambda: str(cache_root))

    entries = cache.get_installer_cache_entries()

    assert entries == [
        {
            "name": "some-game",
            "path": str(cache_root / "some-game"),
            "size": len(b"installer"),
            "file_count": 1,
        }
    ]


def test_delete_installer_cache_entry_refuses_outside_cache(monkeypatch, tmp_path):
    cache_root = tmp_path / "installer"
    cache_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    monkeypatch.setattr(cache, "get_cache_path", lambda: str(cache_root))

    with pytest.raises(ValueError):
        cache.delete_installer_cache_entry(str(outside))

    assert os.path.isdir(outside)


def test_delete_installer_cache_entry_refuses_symlink(monkeypatch, tmp_path):
    cache_root = tmp_path / "installer"
    cache_root.mkdir()
    target = tmp_path / "target"
    target.mkdir()
    link = cache_root / "linked-cache"
    link.symlink_to(target)

    monkeypatch.setattr(cache, "get_cache_path", lambda: str(cache_root))

    with pytest.raises(ValueError):
        cache.delete_installer_cache_entry(str(link))

    assert link.is_symlink()
    assert os.path.isdir(target)


def test_delete_installer_cache_entry_refuses_nested_path(monkeypatch, tmp_path):
    cache_root = tmp_path / "installer"
    nested = cache_root / "game" / "gog"
    nested.mkdir(parents=True)

    monkeypatch.setattr(cache, "get_cache_path", lambda: str(cache_root))

    with pytest.raises(ValueError):
        cache.delete_installer_cache_entry(str(nested))

    assert os.path.isdir(nested)


def test_get_incomplete_installer_cache_entries(monkeypatch, tmp_path):
    cache_root = tmp_path / "installer"
    download_dir = cache_root / "game" / "gog"
    download_dir.mkdir(parents=True)
    tmp_file = download_dir / "setup.exe.tmp"
    tmp_file.write_bytes(b"partial")
    progress_file = download_dir / "setup.exe.progress"
    progress_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(cache, "get_cache_path", lambda: str(cache_root))

    entries = cache.get_incomplete_installer_cache_entries()

    assert [entry["path"] for entry in entries] == [str(progress_file), str(tmp_file)]
    assert [entry["size"] for entry in entries] == [2, len(b"partial")]


def test_get_incomplete_installer_cache_entries_includes_orphaned_downloading_lock(monkeypatch, tmp_path):
    cache_root = tmp_path / "installer"
    download_dir = cache_root / "game" / "gog"
    download_dir.mkdir(parents=True)
    lock_file = download_dir / "setup.exe.cache_lock"
    lock_file.write_text(json.dumps({"state": "downloading"}), encoding="utf-8")

    monkeypatch.setattr(cache, "get_cache_path", lambda: str(cache_root))

    entries = cache.get_incomplete_installer_cache_entries()

    assert len(entries) == 1
    assert entries[0]["path"] == str(lock_file)


def test_get_incomplete_installer_cache_entries_ignores_lock_with_final_file(monkeypatch, tmp_path):
    cache_root = tmp_path / "installer"
    download_dir = cache_root / "game" / "gog"
    download_dir.mkdir(parents=True)
    final_file = download_dir / "setup.exe"
    final_file.write_bytes(b"complete")
    lock_file = download_dir / "setup.exe.cache_lock"
    lock_file.write_text(json.dumps({"state": "downloading"}), encoding="utf-8")

    monkeypatch.setattr(cache, "get_cache_path", lambda: str(cache_root))

    assert cache.get_incomplete_installer_cache_entries() == []


def test_delete_incomplete_installer_cache_entries(monkeypatch, tmp_path):
    cache_root = tmp_path / "installer"
    cache_root.mkdir()
    tmp_file = cache_root / "setup.exe.tmp"
    tmp_file.write_bytes(b"partial")

    monkeypatch.setattr(cache, "get_cache_path", lambda: str(cache_root))

    cache.delete_incomplete_installer_cache_entries([str(tmp_file)])

    assert not tmp_file.exists()


def test_delete_incomplete_installer_cache_entries_refuses_outside_cache(monkeypatch, tmp_path):
    cache_root = tmp_path / "installer"
    cache_root.mkdir()
    outside = tmp_path / "setup.exe.tmp"
    outside.write_bytes(b"partial")

    monkeypatch.setattr(cache, "get_cache_path", lambda: str(cache_root))

    with pytest.raises(ValueError):
        cache.delete_incomplete_installer_cache_entries([str(outside)])

    assert outside.exists()


def test_delete_incomplete_installer_cache_entries_refuses_symlink(monkeypatch, tmp_path):
    cache_root = tmp_path / "installer"
    cache_root.mkdir()
    target = tmp_path / "target.tmp"
    target.write_bytes(b"partial")
    link = cache_root / "setup.exe.tmp"
    link.symlink_to(target)

    monkeypatch.setattr(cache, "get_cache_path", lambda: str(cache_root))

    with pytest.raises(ValueError):
        cache.delete_incomplete_installer_cache_entries([str(link)])

    assert link.is_symlink()
    assert target.exists()
