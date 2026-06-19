import json
import os
import tempfile
from unittest import TestCase
from unittest.mock import patch

from lutris import cache


class TestInstallerCache(TestCase):
    def test_get_installer_cache_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_root = os.path.join(tmpdir, "installer")
            game_cache = os.path.join(cache_root, "some-game", "gog")
            os.makedirs(game_cache)
            installer = os.path.join(game_cache, "setup.exe")
            with open(installer, "wb") as installer_file:
                installer_file.write(b"installer")
            with open(os.path.join(game_cache, "setup.exe.cache_lock"), "w", encoding="utf-8") as lock_file:
                lock_file.write("{}")

            with patch.object(cache, "get_cache_path", return_value=cache_root):
                entries = cache.get_installer_cache_entries()

            self.assertEqual(
                entries,
                [
                    {
                        "name": "some-game",
                        "path": os.path.join(cache_root, "some-game"),
                        "size": len(b"installer"),
                        "file_count": 1,
                    }
                ],
            )

    def test_delete_installer_cache_entry_refuses_outside_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_root = os.path.join(tmpdir, "installer")
            os.makedirs(cache_root)
            outside = os.path.join(tmpdir, "outside")
            os.makedirs(outside)

            with patch.object(cache, "get_cache_path", return_value=cache_root), self.assertRaises(ValueError):
                cache.delete_installer_cache_entry(outside)

            self.assertTrue(os.path.isdir(outside))

    def test_delete_installer_cache_entry_refuses_symlink(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_root = os.path.join(tmpdir, "installer")
            os.makedirs(cache_root)
            target = os.path.join(tmpdir, "target")
            os.makedirs(target)
            link = os.path.join(cache_root, "linked-cache")
            os.symlink(target, link)

            with patch.object(cache, "get_cache_path", return_value=cache_root), self.assertRaises(ValueError):
                cache.delete_installer_cache_entry(link)

            self.assertTrue(os.path.islink(link))
            self.assertTrue(os.path.isdir(target))

    def test_delete_installer_cache_entry_refuses_nested_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_root = os.path.join(tmpdir, "installer")
            nested = os.path.join(cache_root, "game", "gog")
            os.makedirs(nested)

            with patch.object(cache, "get_cache_path", return_value=cache_root), self.assertRaises(ValueError):
                cache.delete_installer_cache_entry(nested)

            self.assertTrue(os.path.isdir(nested))

    def test_get_incomplete_installer_cache_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_root = os.path.join(tmpdir, "installer")
            download_dir = os.path.join(cache_root, "game", "gog")
            os.makedirs(download_dir)
            tmp_file = os.path.join(download_dir, "setup.exe.tmp")
            with open(tmp_file, "wb") as partial_file:
                partial_file.write(b"partial")
            progress_file = os.path.join(download_dir, "setup.exe.progress")
            with open(progress_file, "w", encoding="utf-8") as progress:
                progress.write("{}")

            with patch.object(cache, "get_cache_path", return_value=cache_root):
                entries = cache.get_incomplete_installer_cache_entries()

            self.assertEqual([entry["path"] for entry in entries], [progress_file, tmp_file])
            self.assertEqual([entry["size"] for entry in entries], [2, len(b"partial")])

    def test_get_incomplete_installer_cache_entries_includes_orphaned_downloading_lock(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_root = os.path.join(tmpdir, "installer")
            download_dir = os.path.join(cache_root, "game", "gog")
            os.makedirs(download_dir)
            lock_file = os.path.join(download_dir, "setup.exe.cache_lock")
            with open(lock_file, "w", encoding="utf-8") as lock:
                json.dump({"state": "downloading"}, lock)

            with patch.object(cache, "get_cache_path", return_value=cache_root):
                entries = cache.get_incomplete_installer_cache_entries()

            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["path"], lock_file)

    def test_get_incomplete_installer_cache_entries_ignores_lock_with_final_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_root = os.path.join(tmpdir, "installer")
            download_dir = os.path.join(cache_root, "game", "gog")
            os.makedirs(download_dir)
            final_file = os.path.join(download_dir, "setup.exe")
            with open(final_file, "wb") as setup:
                setup.write(b"complete")
            lock_file = os.path.join(download_dir, "setup.exe.cache_lock")
            with open(lock_file, "w", encoding="utf-8") as lock:
                json.dump({"state": "downloading"}, lock)

            with patch.object(cache, "get_cache_path", return_value=cache_root):
                self.assertEqual(cache.get_incomplete_installer_cache_entries(), [])

    def test_delete_incomplete_installer_cache_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_root = os.path.join(tmpdir, "installer")
            os.makedirs(cache_root)
            tmp_file = os.path.join(cache_root, "setup.exe.tmp")
            with open(tmp_file, "wb") as partial_file:
                partial_file.write(b"partial")

            with patch.object(cache, "get_cache_path", return_value=cache_root):
                cache.delete_incomplete_installer_cache_entries([tmp_file])

            self.assertFalse(os.path.exists(tmp_file))

    def test_delete_incomplete_installer_cache_entries_refuses_outside_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_root = os.path.join(tmpdir, "installer")
            os.makedirs(cache_root)
            outside = os.path.join(tmpdir, "setup.exe.tmp")
            with open(outside, "wb") as partial_file:
                partial_file.write(b"partial")

            with patch.object(cache, "get_cache_path", return_value=cache_root), self.assertRaises(ValueError):
                cache.delete_incomplete_installer_cache_entries([outside])

            self.assertTrue(os.path.exists(outside))

    def test_delete_incomplete_installer_cache_entries_refuses_symlink(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_root = os.path.join(tmpdir, "installer")
            os.makedirs(cache_root)
            target = os.path.join(tmpdir, "target.tmp")
            with open(target, "wb") as partial_file:
                partial_file.write(b"partial")
            link = os.path.join(cache_root, "setup.exe.tmp")
            os.symlink(target, link)

            with patch.object(cache, "get_cache_path", return_value=cache_root), self.assertRaises(ValueError):
                cache.delete_incomplete_installer_cache_entries([link])

            self.assertTrue(os.path.islink(link))
            self.assertTrue(os.path.exists(target))
