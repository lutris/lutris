import os
import tempfile
import unittest
from pathlib import PureWindowsPath
from unittest.mock import patch

from lutris.util.wine import prefix
from lutris.util.wine.prefix import WinePrefixManager

# The Shell Folders values wineboot writes for these keys
SHELL_FOLDERS = {
    "Desktop": PureWindowsPath("Desktop"),
    "Personal": PureWindowsPath("Documents"),
    "My Music": PureWindowsPath("Music"),
    "My Videos": PureWindowsPath("Videos"),
    "My Pictures": PureWindowsPath("Pictures"),
    "{374DE290-123F-4565-9164-39C4925E467B}": PureWindowsPath("Downloads"),
    "Templates": PureWindowsPath("AppData/Roaming/Microsoft/Windows/Templates"),
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
TEMPLATES = SHELL_FOLDERS["Templates"].as_posix()


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
            reg_file.write(r"[Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Shell Folders] 1700000000" + "\n")
            for key, folder in shell_folders.items():
                if not folder.drive:
                    folder = PureWindowsPath("C:/users/lutrisuser") / folder
                # user.reg escapes backslashes
                reg_file.write('"%s"="%s"\n' % (key, str(folder).replace("\\", "\\\\")))

    def link_like_wine(self):
        for folder in SHELL_FOLDERS.values():
            os.symlink(os.path.join(self.home, folder.name), os.path.join(self.user_dir, folder.as_posix()))

    def test_remove_unlinks_the_templates_folder(self):
        self.write_user_reg(SHELL_FOLDERS)
        self.link_like_wine()

        WinePrefixManager(self.prefix_path).remove_desktop_integration()

        for folder in ("Desktop", "Documents", "Downloads", TEMPLATES):
            path = os.path.join(self.user_dir, folder)
            self.assertFalse(os.path.islink(path), folder)
            self.assertTrue(os.path.isdir(path), folder)

    def test_remove_unlinks_templates_missing_from_the_registry(self):
        # A fresh prefix has no Templates value in Shell Folders, but Wine has linked it
        shell_folders = dict(SHELL_FOLDERS)
        del shell_folders["Templates"]
        self.write_user_reg(shell_folders)
        self.link_like_wine()

        WinePrefixManager(self.prefix_path).remove_desktop_integration()

        path = os.path.join(self.user_dir, TEMPLATES)
        self.assertFalse(os.path.islink(path))
        self.assertTrue(os.path.isdir(path))

    def test_remove_unlinks_templates_in_an_already_sandboxed_prefix(self):
        # Lutris sandboxed this prefix before it handled Templates, leaving Wine's link
        self.write_user_reg(SHELL_FOLDERS)
        templates_link = os.path.join(self.user_dir, TEMPLATES)
        os.symlink(os.path.join(self.home, "Templates"), templates_link)
        manager = WinePrefixManager(self.prefix_path)
        manager._set_desktop_integration_assignment(self.user_dir)

        manager.remove_desktop_integration()

        self.assertFalse(os.path.islink(templates_link))
        self.assertTrue(os.path.isdir(templates_link))
        self.assertEqual(manager._get_desktop_integration_assignment(), self.user_dir)

    def test_install_links_every_folder(self):
        self.write_user_reg(SHELL_FOLDERS)
        for folder in SHELL_FOLDERS.values():
            os.makedirs(os.path.join(self.user_dir, folder.as_posix()), exist_ok=True)

        manager = WinePrefixManager(self.prefix_path)
        manager.install_desktop_integration()

        for folder, xdg_folder in zip(SHELL_FOLDERS.values(), XDG_DIRS.values()):
            path = os.path.join(self.user_dir, folder.as_posix())
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
        shell_folders["My Pictures"] = PureWindowsPath("Z:/home/lutrisuser/Pictures")
        self.write_user_reg(shell_folders)

        folders = WinePrefixManager(self.prefix_path).get_desktop_folders()

        self.assertEqual(folders[prefix.DESKTOP_XDG.index("PICTURES")], "Pictures")
