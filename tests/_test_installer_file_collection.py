import os
import tempfile
from unittest import TestCase

from lutris.installer.installer_file import InstallerFile
from lutris.installer.installer_file_collection import InstallerFileCollection
from lutris.util.test_config import setup_test_environment

setup_test_environment()


class TestOverrideDestFile(TestCase):
    """A user may point a multi-part download at a copy of its main file they already have."""

    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.users_file = os.path.join(temp_dir.name, "setup.exe")
        with open(self.users_file, "w", encoding="utf-8") as setup_file:
            setup_file.write("installer")

    def get_collection(self, file_id):
        files = [
            InstallerFile("some-game", file_id, {"url": "https://example.com/setup.exe", "filename": "setup.exe"}),
            InstallerFile(
                "some-game", file_id + "_1", {"url": "https://example.com/setup-1.bin", "filename": "setup-1.bin"}
            ),
        ]
        return InstallerFileCollection("some-game", file_id, files)

    def test_main_file_uses_the_users_copy(self):
        # Scripts on lutris.net name this file as they please, not always 'goginstaller'
        collection = self.get_collection("setup")
        collection.override_dest_file(self.users_file)
        self.assertTrue(collection.is_ready("user"))
        self.assertEqual(collection.get_dest_files_by_id()["setup"], self.users_file)

    def test_other_parts_keep_their_own_destination(self):
        collection = self.get_collection("goginstaller")
        collection.override_dest_file(self.users_file)
        dest_files = collection.get_dest_files_by_id()
        self.assertEqual(dest_files["goginstaller"], self.users_file)
        self.assertNotEqual(dest_files["goginstaller_1"], self.users_file)
