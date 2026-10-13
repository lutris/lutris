import gzip
import io
import itertools
import os
import tarfile
import tempfile
from unittest import TestCase
from unittest.mock import MagicMock, patch

from lutris.util import extract


class TestSevenZipProgress(TestCase):
    def run_extraction(self, output, return_code=0):
        process = MagicMock()
        process.__enter__.return_value = process
        process.stdout = io.BytesIO(output)
        process.wait.return_value = return_code
        progress = []
        with (
            patch.object(extract, "_get_7zip_path", return_value="/usr/bin/7z"),
            patch.object(extract.time, "monotonic", side_effect=itertools.count()),
            patch.object(extract.subprocess, "Popen", return_value=process) as popen,
        ):
            extract._extract_7zip("archive with spaces.zip", "target with spaces", progress_callback=progress.append)
        return progress, popen.call_args.args[0]

    def test_progress_with_carriage_returns_and_backspaces(self):
        output = b"7-Zip header\n  0%\r 25%\b\b\b\b 25%\r 75%\r100%"
        progress, command = self.run_extraction(output)
        self.assertEqual(progress, [0, 25, 75, 99, 100])
        self.assertIn("-bsp1", command)
        self.assertIn("-o" + "target with spaces", command)
        self.assertIn("archive with spaces.zip", command)

    def test_diagnostics_are_not_progress(self):
        progress, _ = self.run_extraction(b"file 42% complete\n101%\r 80%\r")
        self.assertEqual(progress, [0, 80, 100])

    def test_failure_does_not_report_completion(self):
        process = MagicMock()
        process.__enter__.return_value = process
        process.stdout = io.BytesIO(b" 50%\r100%")
        process.wait.return_value = 2
        progress = []
        with (
            patch.object(extract, "_get_7zip_path", return_value="/usr/bin/7z"),
            patch.object(extract.time, "monotonic", side_effect=itertools.count()),
            patch.object(extract.subprocess, "Popen", return_value=process),
            self.assertRaises(extract.ExtractError),
        ):
            extract._extract_7zip("bad.iso", "target", progress_callback=progress.append)
        self.assertNotIn(100, progress)

    def test_terminal_progress_uses_one_dynamic_line(self):
        terminal = io.StringIO()
        terminal.isatty = lambda: True
        with patch.object(extract.sys, "stdout", terminal):
            progress, _ = self.run_extraction(b" 25%\r 75%\r100%")
        output = terminal.getvalue()
        self.assertEqual(output.count("\n"), 1)
        self.assertIn("\rExtracting archive with spaces.zip:", output)
        self.assertIn("100%", output)
        self.assertEqual(progress[-1], 100)


class TestPythonExtractionProgress(TestCase):
    def test_tar_codecs_preserve_contents_links_and_metadata(self):
        for mode in ("", "gz", "bz2", "xz"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                path = os.path.join(directory, "archive.tar")
                data = b"archive payload" * 100000
                with tarfile.open(path, "w:" + mode) as archive:
                    folder = tarfile.TarInfo("folder")
                    folder.type = tarfile.DIRTYPE
                    folder.mode = 0o755
                    folder.mtime = 123456789
                    archive.addfile(folder)
                    info = tarfile.TarInfo("folder/payload")
                    info.size = len(data)
                    info.mode = 0o755
                    archive.addfile(info, io.BytesIO(data))
                    link = tarfile.TarInfo("folder/link")
                    link.type = tarfile.LNKTYPE
                    link.mode = 0o755
                    link.linkname = "folder/payload"
                    archive.addfile(link)
                progress = []
                dest = os.path.join(directory, "dest")
                with patch.object(extract.time, "monotonic", side_effect=itertools.count()):
                    extract._extract_tar(path, dest, "r:" + mode, progress.append)
                with open(os.path.join(dest, "folder/payload"), "rb") as result:
                    self.assertEqual(result.read(), data)
                self.assertEqual(os.stat(os.path.join(dest, "folder")).st_mtime, 123456789)
                self.assertTrue(os.stat(os.path.join(dest, "folder/payload")).st_mode & 0o100)
                self.assertEqual(
                    os.stat(os.path.join(dest, "folder/link")).st_ino,
                    os.stat(os.path.join(dest, "folder/payload")).st_ino,
                )
                self.assertEqual(progress[0], 0)
                self.assertEqual(progress[-1], 100)
                self.assertTrue(any(0 < value < 99 for value in progress))
                self.assertEqual(progress, sorted(set(progress)))

    def test_gzip_streams_and_checks_crc_before_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "payload.gz")
            data = os.urandom(3 * 1024 * 1024)
            with gzip.open(path, "wb") as archive:
                archive.write(data)
            progress = []
            with patch.object(extract.time, "monotonic", side_effect=itertools.count()):
                extract._decompress_gz(path, os.path.join(directory, "dest"), progress.append)
            with open(os.path.join(directory, "dest/payload"), "rb") as result:
                self.assertEqual(result.read(), data)
            self.assertEqual(progress[-1], 100)
            with open(path, "r+b") as archive:
                archive.seek(-8, 2)
                archive.write(b"bad!")
            progress.clear()
            with self.assertRaises(gzip.BadGzipFile):
                extract._decompress_gz(path, os.path.join(directory, "dest"), progress.append)
            self.assertNotIn(100, progress)

    def test_truncated_tar_never_reports_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "broken.tar")
            with tarfile.open(path, "w") as archive:
                info = tarfile.TarInfo("payload")
                info.size = 10000
                archive.addfile(info, io.BytesIO(b"x" * info.size))
            with open(path, "r+b") as archive:
                archive.truncate(1000)
            progress = []
            with self.assertRaises(tarfile.ReadError):
                extract._extract_tar(path, os.path.join(directory, "dest"), "r:", progress.append)
            self.assertNotIn(100, progress)

    def test_appimage_copy_keeps_executable_permission(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "game.AppImage")
            data = b"x" * (2 * 1024 * 1024)
            with open(path, "wb") as source:
                source.write(data)
            os.chmod(path, 0o755)
            dest = os.path.join(directory, "dest")
            os.mkdir(dest)
            progress = []
            with (
                patch.object(extract.system, "create_folder", create=True),
                patch.object(extract.time, "monotonic", side_effect=itertools.count()),
            ):
                extract._extract_AppImage(path, dest, progress.append)
            with open(os.path.join(dest, "game.AppImage"), "rb") as copied:
                self.assertEqual(copied.read(), data)
            self.assertTrue(os.stat(os.path.join(dest, "game.AppImage")).st_mode & 0o100)
            self.assertEqual(progress, [0, 50, 99, 100])

    def test_throttles_updates_but_never_delays_completion(self):
        progress = []
        with patch.object(extract.time, "monotonic", side_effect=[0, 0.1, 0.5, 0.6]):
            reporter = extract._ExtractionProgress("archive", progress.append)
            for percent in (0, 10, 20, 100):
                reporter.report(percent)
        self.assertEqual(progress, [0, 20, 100])

    def test_empty_tar_completes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "empty.tar")
            with tarfile.open(path, "w"):
                pass
            progress = []
            extract._extract_tar(path, os.path.join(directory, "dest"), "r:", progress.append)
            self.assertEqual(progress, [0, 100])


class TestInnoExtractionProgress(TestCase):
    def test_counts_previous_file_and_finishes_only_on_success(self):
        for return_code in (0, 2):
            with self.subTest(return_code=return_code):
                process = MagicMock()
                process.__enter__.return_value = process
                process.stdout = io.StringIO("a file\nb\nb\nc\n")
                process.wait.return_value = return_code
                listing = MagicMock(returncode=0, stdout="a file\nb\nc\n")
                progress = []
                with (
                    patch.object(extract, "_get_innoextract_path", return_value="innoextract"),
                    patch.object(extract.system, "create_folder", create=True),
                    patch.object(extract.subprocess, "run", return_value=listing),
                    patch.object(extract.subprocess, "Popen", return_value=process),
                    patch.object(extract.time, "monotonic", side_effect=itertools.count()),
                ):
                    if return_code:
                        with self.assertRaises(extract.ExtractError):
                            extract._decompress_gog("setup.exe", "dest", progress.append)
                        self.assertNotIn(100, progress)
                    else:
                        extract._decompress_gog("setup.exe", "dest", progress.append)
                        self.assertEqual(progress, [0, 33, 66, 100])
