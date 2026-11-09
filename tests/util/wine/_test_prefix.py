import os
import tempfile
import unittest
from unittest.mock import patch

from lutris.util.wine import prefix
from lutris.util.wine.prefix import WinePrefixManager

# The Shell Folders values wineboot writes for these keys
SHELL_FOLDERS = {
    "Desktop": "Desktop",
    "Personal": "Documents",
    "My Music": "Music",
    "My Videos": "Videos",
    "My Pictures": "Pictures",
    "{374DE290-123F-4565-9164-39C4925E467B}": "Downloads",
    "Templates": "AppData\\\\Roaming\\\\Microsoft\\\\Windows\\\\Templates",
}
XDG_DIRS = {
    "DESKTOP": "Desktop",
    "DOCUMENTS": "Documents",
    "MUSIC": "Music",
    "VIDEOS": "Videos",
    "PICTURES": "Pictures",
    "DOWNLOADS": "Downloads",
    "TEMPLATES": "Templates",
}
TEMPLATES = "AppData/Roaming/Microsoft/Windows/Templates"


class TestDesktopIntegration(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.home = os.path.join(temp_dir.name, "home")
        for name in XDG_DIRS.values():
            os.makedirs(os.path.join(self.home, name))
        self.prefix_path = os.path.join(temp_dir.name, "prefix")
        self.user_dir = os.path.join(self.prefix_path, "drive_c/users/lutrisuser")
        os.makedirs(os.path.join(self.user_dir, "AppData/Roaming/Microsoft/Windows"))

        for patcher in (
            patch.dict(os.environ, {"USER": "lutrisuser", "HOME": self.home}),
            patch.object(prefix, "get_xdg_entry", lambda name: os.path.join(self.home, XDG_DIRS[name])),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_user_reg(self, shell_folders):
        with open(os.path.join(self.prefix_path, "user.reg"), "w", encoding="utf-8") as reg_file:
            reg_file.write("WINE REGISTRY Version 2\n#arch=win64\n\n")
            reg_file.write(
                "[Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Explorer\\\\Shell Folders] 1700000000\n"
            )
            for key, folder in shell_folders.items():
                if ":" not in folder:
                    folder = "C:\\\\users\\\\lutrisuser\\\\" + folder
                reg_file.write('"%s"="%s"\n' % (key, folder))

    def link_like_wine(self):
        for folder in SHELL_FOLDERS.values():
            folder = folder.replace("\\\\", "/")
            os.symlink(os.path.join(self.home, os.path.basename(folder)), os.path.join(self.user_dir, folder))

    def test_remove_unlinks_the_templates_folder(self):
        self.write_user_reg(SHELL_FOLDERS)
        self.link_like_wine()

        WinePrefixManager(self.prefix_path).remove_desktop_integration()

        for folder in ("Desktop", "Documents", "Downloads", TEMPLATES):
            path = os.path.join(self.user_dir, folder)
            self.assertFalse(os.path.islink(path), folder)
            self.assertTrue(os.path.isdir(path), folder)

    def test_install_links_every_folder(self):
        self.write_user_reg(SHELL_FOLDERS)
        for folder in SHELL_FOLDERS.values():
            os.makedirs(os.path.join(self.user_dir, folder.replace("\\\\", "/")), exist_ok=True)

        manager = WinePrefixManager(self.prefix_path)
        manager.install_desktop_integration()

        for folder, xdg_folder in zip(SHELL_FOLDERS.values(), XDG_DIRS.values()):
            path = os.path.join(self.user_dir, folder.replace("\\\\", "/"))
            self.assertEqual(os.readlink(path), os.path.join(self.home, xdg_folder), folder)
        self.assertEqual(manager._get_desktop_integration_assignment(), self.home)

    def test_missing_key_keeps_folders_matched_to_xdg(self):
        shell_folders = dict(SHELL_FOLDERS)
        del shell_folders["My Music"]
        del shell_folders["Templates"]
        self.write_user_reg(shell_folders)

        folders = WinePrefixManager(self.prefix_path).get_desktop_folders()

        self.assertEqual(folders[prefix.DESKTOP_XDG.index("VIDEOS")], "Videos")
        self.assertEqual(folders[prefix.DESKTOP_XDG.index("MUSIC")], "Music")
        self.assertEqual(folders[prefix.DESKTOP_XDG.index("TEMPLATES")], TEMPLATES)

    def test_folder_outside_the_profile_keeps_its_name(self):
        shell_folders = dict(SHELL_FOLDERS)
        shell_folders["My Pictures"] = "Z:\\\\home\\\\lutrisuser\\\\Pictures"
        self.write_user_reg(shell_folders)

        folders = WinePrefixManager(self.prefix_path).get_desktop_folders()

        self.assertEqual(folders[prefix.DESKTOP_XDG.index("PICTURES")], "Pictures")
