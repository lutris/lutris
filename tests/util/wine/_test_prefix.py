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
        self.temp_dir = temp_dir.name
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

    def test_remove_keeps_a_templates_link_the_user_made_in_a_sandboxed_prefix(self):
        self.write_user_reg(SHELL_FOLDERS)
        templates_folder = os.path.join(self.temp_dir, "Shared/Templates")
        os.makedirs(templates_folder)
        templates_link = os.path.join(self.user_dir, TEMPLATES)
        os.symlink(templates_folder, templates_link)
        manager = WinePrefixManager(self.prefix_path)
        manager._set_desktop_integration_assignment(self.user_dir)

        manager.remove_desktop_integration()
        # Later launches leave a link the user added since alone, as in any sandboxed prefix
        documents = os.path.join(self.user_dir, "Documents")
        os.symlink(os.path.join(self.home, "Documents"), documents)
        manager.remove_desktop_integration()

        self.assertEqual(os.readlink(templates_link), templates_folder)
        self.assertEqual(os.readlink(documents), os.path.join(self.home, "Documents"))
        self.assertEqual(manager._get_desktop_integration_assignment(), self.user_dir)

    def test_remove_keeps_links_the_user_made(self):
        self.write_user_reg(SHELL_FOLDERS)
        self.link_like_wine()
        shared_folder = os.path.join(self.temp_dir, "Shared/Documents")
        os.makedirs(shared_folder)
        documents = os.path.join(self.user_dir, "Documents")
        os.unlink(documents)
        os.symlink("../../../../Shared/Documents", documents)

        with self.assertLogs(prefix.logger, level="DEBUG") as logs:
            WinePrefixManager(self.prefix_path).remove_desktop_integration()

        self.assertIn(f"Keeping {documents}, it links to ../../../../Shared/Documents", logs.output[-1])
        self.assertEqual(os.readlink(documents), "../../../../Shared/Documents")
        self.assertEqual(os.path.realpath(documents), os.path.realpath(shared_folder))
        desktop = os.path.join(self.user_dir, "Desktop")
        self.assertFalse(os.path.islink(desktop))
        self.assertTrue(os.path.isdir(desktop))

    def test_remove_keeps_relative_links_into_home(self):
        # Prefixes live under ~/Games by default; WINE and the integration only make absolute links
        self.write_user_reg(SHELL_FOLDERS)
        self.link_like_wine()
        documents_folder = os.path.join(self.home, "Documents")
        documents = os.path.join(self.user_dir, "Documents")
        os.unlink(documents)
        os.symlink(os.path.relpath(documents_folder, self.user_dir), documents)

        WinePrefixManager(self.prefix_path).remove_desktop_integration()

        self.assertEqual(os.readlink(documents), os.path.relpath(documents_folder, self.user_dir))
        desktop = os.path.join(self.user_dir, "Desktop")
        self.assertFalse(os.path.islink(desktop))
        self.assertTrue(os.path.isdir(desktop))

    def test_remove_keeps_other_links_the_user_made(self):
        self.write_user_reg(SHELL_FOLDERS)
        self.link_like_wine()
        shared_folder = os.path.join(self.temp_dir, "Shared/Documents")
        saves_folder = os.path.join(self.home, "Games/shared/Saved Games")
        os.makedirs(shared_folder)
        os.makedirs(saves_folder)
        os.makedirs(os.path.join(self.home, "GameSaves"))
        links = {
            "Documents": shared_folder,
            "Downloads": saves_folder,
            "Music": "../../../../Unmounted/Music",
            "Pictures": os.path.join(self.home, "GameSaves"),
        }
        for folder, target in links.items():
            os.unlink(os.path.join(self.user_dir, folder))
            os.symlink(target, os.path.join(self.user_dir, folder))
        manager = WinePrefixManager(self.prefix_path)
        # The prefix was seen before at another path, e.g. the drive was mounted elsewhere
        manager._set_desktop_integration_assignment(os.path.join(self.temp_dir, "old/drive_c/users/lutrisuser"))

        manager.remove_desktop_integration()

        for folder, target in links.items():
            self.assertEqual(os.readlink(os.path.join(self.user_dir, folder)), target, folder)

    def test_remove_unlinks_folders_linked_into_home(self):
        # Older WINE versions link to $HOME itself or to folders under '$HOME/My Documents'
        self.write_user_reg(SHELL_FOLDERS)
        my_pictures = os.path.join(self.home, "My Documents/My Pictures")
        os.makedirs(my_pictures)
        os.symlink(self.home, os.path.join(self.user_dir, "Documents"))
        os.symlink(my_pictures, os.path.join(self.user_dir, "Pictures"))

        WinePrefixManager(self.prefix_path).remove_desktop_integration()

        for folder in ("Documents", "Pictures"):
            path = os.path.join(self.user_dir, folder)
            self.assertFalse(os.path.islink(path), folder)
            self.assertTrue(os.path.isdir(path), folder)

    def test_remove_unlinks_xdg_folders_outside_home(self):
        self.write_user_reg(SHELL_FOLDERS)
        documents_dir = os.path.join(self.temp_dir, "data/Documents")
        os.makedirs(documents_dir)
        documents = os.path.join(self.user_dir, "Documents")
        os.symlink(documents_dir, documents)
        xdg_dirs = dict(XDG_DIRS, DOCUMENTS=documents_dir)

        with patch.object(prefix, "get_xdg_entry", lambda name: os.path.join(self.home, xdg_dirs[name])):
            WinePrefixManager(self.prefix_path).remove_desktop_integration()

        self.assertFalse(os.path.islink(documents))
        self.assertTrue(os.path.isdir(documents))

    def test_remove_unlinks_integration_links_to_folders_xdg_moved_from(self):
        self.write_user_reg(SHELL_FOLDERS)
        manager = WinePrefixManager(self.prefix_path)
        old_documents = os.path.join(self.home, "Dokumente")
        os.makedirs(old_documents)
        with patch.object(
            prefix, "get_xdg_entry", lambda name: os.path.join(self.home, dict(XDG_DIRS, DOCUMENTS="Dokumente")[name])
        ):
            manager.install_desktop_integration()
        documents = os.path.join(self.user_dir, "Documents")
        self.assertEqual(os.readlink(documents), old_documents)
        # Links the user made after installing: absolute ones can't be told from ours, relative ones can
        shared_folder = os.path.join(self.temp_dir, "Shared/Pictures")
        os.makedirs(shared_folder)
        pictures = os.path.join(self.user_dir, "Pictures")
        music = os.path.join(self.user_dir, "Music")
        for path, target in ((pictures, shared_folder), (music, "../../../../Shared/Music")):
            os.unlink(path)
            os.symlink(target, path)

        manager.remove_desktop_integration()

        for path in (documents, pictures):
            self.assertFalse(os.path.islink(path), path)
            self.assertTrue(os.path.isdir(path), path)
        self.assertEqual(os.readlink(music), "../../../../Shared/Music")

    def test_remove_unlinks_wine_links_through_a_linked_home(self):
        # e.g. /home -> /var/home on Fedora Atomic
        self.write_user_reg(SHELL_FOLDERS)
        linked_home = os.path.join(self.temp_dir, "linked_home")
        os.symlink(self.home, linked_home)
        os.symlink(os.path.join(linked_home, "Documents"), os.path.join(self.user_dir, "Documents"))
        os.symlink(os.path.join(self.home, "Pictures"), os.path.join(self.user_dir, "Pictures"))

        with patch.dict(os.environ, {"HOME": linked_home}), patch.object(prefix, "get_xdg_entry", lambda name: None):
            WinePrefixManager(self.prefix_path).remove_desktop_integration()

        for folder in ("Documents", "Pictures"):
            path = os.path.join(self.user_dir, folder)
            self.assertFalse(os.path.islink(path), folder)
            self.assertTrue(os.path.isdir(path), folder)

    def test_remove_unlinks_wine_links_that_resolve_elsewhere(self):
        # A prefix copied from another user, and a home folder that is itself a link to another drive
        self.write_user_reg(SHELL_FOLDERS)
        os.symlink(os.path.join(self.temp_dir, "otheruser/Documents"), os.path.join(self.user_dir, "Documents"))
        videos_dir = os.path.join(self.temp_dir, "data/Videos")
        os.makedirs(videos_dir)
        os.rmdir(os.path.join(self.home, "Videos"))
        os.symlink(videos_dir, os.path.join(self.home, "Videos"))
        os.symlink(os.path.join(self.home, "Videos"), os.path.join(self.user_dir, "Videos"))

        with patch.object(prefix, "get_xdg_entry", lambda name: None):
            WinePrefixManager(self.prefix_path).remove_desktop_integration()

        for folder in ("Documents", "Videos"):
            path = os.path.join(self.user_dir, folder)
            self.assertFalse(os.path.islink(path), folder)
            self.assertTrue(os.path.isdir(path), folder)

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
