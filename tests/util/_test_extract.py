"""Tests for archive extraction."""

import io
import os
import tarfile
import zipfile
from tempfile import TemporaryDirectory
from unittest import TestCase

from lutris.util.extract import extract_archive


def make_zip(path, files):
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)


def make_tgz(path, name, data):
    with tarfile.open(path, "w:gz") as archive:
        info = tarfile.TarInfo(name)
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))


def zip_bytes(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


class TestNestedArchives(TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.tmp = self._tmp.name
        self.dest = os.path.join(self.tmp, "dest")
        os.mkdir(self.dest)

    def tearDown(self):
        self._tmp.cleanup()

    def test_inner_archive_is_kept_by_default(self):
        """A Humble zip holding a MojoSetup installer must leave the installer for a later step."""
        # MojoSetup installers are a shell script with a zip appended; zipfile still detects them
        installer = b"#!/bin/sh\nexit 0\n" + zip_bytes({"data/game.bin": b"game"})
        outer = os.path.join(self.tmp, "Game-Installer_Humble_Linux.zip")
        make_zip(outer, {"Game-Installer": installer})

        extract_archive(outer, self.dest)

        self.assertEqual(os.listdir(self.dest), ["Game-Installer"])
        with open(os.path.join(self.dest, "Game-Installer"), "rb") as inner:
            self.assertEqual(inner.read(), installer)

    def test_inner_archive_is_extracted_when_nested(self):
        """GameJolt wraps its builds in a tar.gz around the real archive."""
        outer = os.path.join(self.tmp, "gamejoltbuild.tar.gz")
        make_tgz(outer, "build.zip", zip_bytes({"game/run.sh": b"#!/bin/sh\n"}))

        extract_archive(outer, self.dest, extract_nested=True)

        self.assertEqual(os.listdir(self.dest), ["run.sh"])
