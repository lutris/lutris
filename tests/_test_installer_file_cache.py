import hashlib

from lutris.installer.installer_file import InstallerFile
from lutris.installer.installer_file_collection import InstallerFileCollection


def _installer_file(monkeypatch, tmp_path, file_meta):
    monkeypatch.setattr("lutris.installer.installer_file.get_url_cache_path", lambda *_args, **_kwargs: str(tmp_path))
    return InstallerFile("test-game", "setup", file_meta)


def test_installer_file_valid_cache_requires_matching_size(monkeypatch, tmp_path):
    installer_file = _installer_file(
        monkeypatch,
        tmp_path,
        {"url": "https://example.com/setup.exe", "filename": "setup.exe", "size": 4},
    )
    installer_file.dest_file = str(tmp_path / "setup.exe")
    (tmp_path / "setup.exe").write_bytes(b"bad")

    assert installer_file.is_cached
    assert not installer_file.has_valid_cache


def test_installer_file_valid_cache_requires_matching_checksum(monkeypatch, tmp_path):
    expected_hash = hashlib.md5(b"good", usedforsecurity=False).hexdigest()
    installer_file = _installer_file(
        monkeypatch,
        tmp_path,
        {
            "url": "https://example.com/setup.exe",
            "filename": "setup.exe",
            "checksum": "md5:%s" % expected_hash,
        },
    )
    installer_file.dest_file = str(tmp_path / "setup.exe")
    (tmp_path / "setup.exe").write_bytes(b"bad")

    assert installer_file.is_cached
    assert not installer_file.has_valid_cache


def test_installer_file_collection_valid_cache_requires_all_files(monkeypatch, tmp_path):
    valid = _installer_file(
        monkeypatch,
        tmp_path,
        {"url": "https://example.com/valid.exe", "filename": "valid.exe", "size": 5},
    )
    valid.dest_file = str(tmp_path / "valid.exe")
    (tmp_path / "valid.exe").write_bytes(b"valid")

    invalid = _installer_file(
        monkeypatch,
        tmp_path,
        {"url": "https://example.com/invalid.exe", "filename": "invalid.exe", "size": 7},
    )
    invalid.dest_file = str(tmp_path / "invalid.exe")
    (tmp_path / "invalid.exe").write_bytes(b"short")

    collection = InstallerFileCollection("test-game", "setup", [valid, invalid])

    assert collection.is_cached
    assert not collection.has_valid_cache


def test_installer_file_collection_valid_cache_requires_total_size(monkeypatch, tmp_path):
    first = _installer_file(
        monkeypatch,
        tmp_path,
        {"url": "https://example.com/part1.bin", "filename": "part1.bin", "total_size": 10},
    )
    first.dest_file = str(tmp_path / "part1.bin")
    (tmp_path / "part1.bin").write_bytes(b"12345")

    second = _installer_file(
        monkeypatch,
        tmp_path,
        {"url": "https://example.com/part2.bin", "filename": "part2.bin"},
    )
    second.dest_file = str(tmp_path / "part2.bin")
    (tmp_path / "part2.bin").write_bytes(b"1234")

    collection = InstallerFileCollection("test-game", "setup", [first, second])

    assert collection.is_cached
    assert not collection.has_valid_cache
