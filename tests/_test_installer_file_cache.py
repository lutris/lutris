import hashlib
import os
import tempfile
from unittest import TestCase
from unittest.mock import patch

from lutris.installer.installer_file import InstallerFile
from lutris.installer.installer_file_collection import InstallerFileCollection


def _installer_file(tmpdir, file_meta):
    with patch("lutris.installer.installer_file.get_url_cache_path", return_value=tmpdir):
        return InstallerFile("test-game", "setup", file_meta)


class TestInstallerFileCache(TestCase):
    def test_installer_file_valid_cache_requires_matching_size(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            installer_file = _installer_file(
                tmpdir,
                {"url": "https://example.com/setup.exe", "filename": "setup.exe", "size": 4},
            )
            installer_file.dest_file = os.path.join(tmpdir, "setup.exe")
            with open(installer_file.dest_file, "wb") as setup:
                setup.write(b"bad")

            self.assertTrue(installer_file.is_cached)
            self.assertFalse(installer_file.has_valid_cache)

    def test_installer_file_valid_cache_requires_matching_checksum(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            expected_hash = hashlib.md5(b"good", usedforsecurity=False).hexdigest()
            installer_file = _installer_file(
                tmpdir,
                {
                    "url": "https://example.com/setup.exe",
                    "filename": "setup.exe",
                    "checksum": "md5:%s" % expected_hash,
                },
            )
            installer_file.dest_file = os.path.join(tmpdir, "setup.exe")
            with open(installer_file.dest_file, "wb") as setup:
                setup.write(b"bad")

            self.assertTrue(installer_file.is_cached)
            self.assertFalse(installer_file.has_valid_cache)

    def test_installer_file_collection_valid_cache_requires_all_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            valid = _installer_file(
                tmpdir,
                {"url": "https://example.com/valid.exe", "filename": "valid.exe", "size": 5},
            )
            valid.dest_file = os.path.join(tmpdir, "valid.exe")
            with open(valid.dest_file, "wb") as valid_file:
                valid_file.write(b"valid")

            invalid = _installer_file(
                tmpdir,
                {"url": "https://example.com/invalid.exe", "filename": "invalid.exe", "size": 7},
            )
            invalid.dest_file = os.path.join(tmpdir, "invalid.exe")
            with open(invalid.dest_file, "wb") as invalid_file:
                invalid_file.write(b"short")

            collection = InstallerFileCollection("test-game", "setup", [valid, invalid])

            self.assertTrue(collection.is_cached)
            self.assertFalse(collection.has_valid_cache)

    def test_installer_file_collection_valid_cache_requires_total_size(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            first = _installer_file(
                tmpdir,
                {"url": "https://example.com/part1.bin", "filename": "part1.bin", "total_size": 10},
            )
            first.dest_file = os.path.join(tmpdir, "part1.bin")
            with open(first.dest_file, "wb") as first_file:
                first_file.write(b"12345")

            second = _installer_file(
                tmpdir,
                {"url": "https://example.com/part2.bin", "filename": "part2.bin"},
            )
            second.dest_file = os.path.join(tmpdir, "part2.bin")
            with open(second.dest_file, "wb") as second_file:
                second_file.write(b"1234")

            collection = InstallerFileCollection("test-game", "setup", [first, second])

            self.assertTrue(collection.is_cached)
            self.assertFalse(collection.has_valid_cache)
