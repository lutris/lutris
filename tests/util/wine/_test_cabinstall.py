"""Tests for installing DLLs from a Windows cab file into a prefix."""

import os
import tempfile
from unittest import TestCase
from unittest.mock import patch

from lutris.util.wine.cabinstall import CabInstaller


class TestInstallDll(TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.prefix = os.path.join(temp_dir.name, "prefix")
        self.system32 = os.path.join(self.prefix, "drive_c", "windows", "system32")
        os.makedirs(self.system32)
        self.cab_dll = os.path.join(temp_dir.name, "mf.dll")
        with open(self.cab_dll, "w", encoding="utf-8") as dll:
            dll.write("from the cab")
        # Proton links a new prefix's DLLs to its own
        self.proton_dll = os.path.join(temp_dir.name, "proton", "mf.dll")
        os.makedirs(os.path.dirname(self.proton_dll))
        with open(self.proton_dll, "w", encoding="utf-8") as dll:
            dll.write("Proton's own")

        os.symlink(self.proton_dll, os.path.join(self.system32, "mf.dll"))

    def install_dll(self):
        cab_installer = CabInstaller(self.prefix, arch="win64")
        self.addCleanup(cab_installer.cleanup)
        with patch.object(CabInstaller, "get_arch_from_dll", return_value="win64"):
            cab_installer.install_dll(self.cab_dll)

    def read(self, path):
        with open(path, encoding="utf-8") as dll:
            return dll.read()

    def test_link_to_protons_dll_is_replaced_and_protons_copy_kept(self):
        self.install_dll()
        installed = os.path.join(self.system32, "mf.dll")
        self.assertFalse(os.path.islink(installed))
        self.assertEqual(self.read(installed), "from the cab")
        self.assertEqual(self.read(self.proton_dll), "Proton's own")
