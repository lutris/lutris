"""Tests for the file helpers in lutris.util.system."""

import os
import tempfile
import unittest

from lutris.util.system import merge_folders


class TestMergeFolders(unittest.TestCase):
    """Games often ship links, like 'lib -> lib64'; a merge must keep them as links."""

    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.source = os.path.join(temp_dir.name, "source")
        self.destination = os.path.join(temp_dir.name, "destination")
        os.makedirs(os.path.join(self.source, "lib64"))
        os.makedirs(self.destination)
        with open(os.path.join(self.source, "lib64", "libgame.so"), "w", encoding="utf-8") as library:
            library.write("library")
        with open(os.path.join(self.source, "start.sh"), "w", encoding="utf-8") as script:
            script.write("#!/bin/sh")
        os.symlink("lib64", os.path.join(self.source, "lib"))
        os.symlink("start.sh", os.path.join(self.source, "launch.sh"))

    def merged(self, name):
        return os.path.join(self.destination, name)

    def test_link_to_a_folder_stays_a_link(self):
        merge_folders(self.source, self.destination)
        self.assertTrue(os.path.islink(self.merged("lib")))
        self.assertEqual(os.readlink(self.merged("lib")), "lib64")
        self.assertTrue(os.path.isfile(self.merged("lib/libgame.so")))

    def test_link_to_a_file_stays_a_link(self):
        merge_folders(self.source, self.destination)
        self.assertEqual(os.readlink(self.merged("launch.sh")), "start.sh")

    def test_folder_already_in_the_destination_is_kept(self):
        os.makedirs(self.merged("lib"))
        merge_folders(self.source, self.destination)
        self.assertFalse(os.path.islink(self.merged("lib")))
