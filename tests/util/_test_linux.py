from unittest import TestCase
from unittest.mock import patch

from lutris.util import linux


class TestLinuxSystem(TestCase):
    def setUp(self):
        self.linux_system = linux.LinuxSystem.__new__(linux.LinuxSystem)

    def test_get_fs_type_for_path_uses_parent_mount_for_btrfs_subvolume_path(self):
        with patch.object(
            self.linux_system,
            "get_drives",
            return_value=[
                {"target": "/", "source": "/dev/disk0[/@]", "fstype": "btrfs"},
                {"target": "/home/user", "source": "/dev/disk0[/@home]", "fstype": "btrfs"},
            ],
        ):
            fs_type = self.linux_system.get_fs_type_for_path("/home/user/games/wineprefixes/game")

        self.assertEqual(fs_type, "btrfs")

    def test_get_fs_type_for_path_uses_deepest_containing_mount(self):
        with patch.object(
            self.linux_system,
            "get_drives",
            return_value=[
                {"target": "/home/user", "source": "/dev/disk0[/@home]", "fstype": "btrfs"},
                {"target": "/home/user/games", "source": "/dev/disk0[/@games]", "fstype": "btrfs"},
            ],
        ):
            fs_type = self.linux_system.get_fs_type_for_path("/home/user/games/wineprefixes/game")

        self.assertEqual(fs_type, "btrfs")

    def test_get_fs_type_for_path_does_not_match_partial_path_prefixes(self):
        with patch.object(
            self.linux_system,
            "get_drives",
            return_value=[
                {"target": "/mnt/game", "source": "/dev/sda1", "fstype": "ext4"},
                {"target": "/mnt/games", "source": "/dev/sdb1", "fstype": "xfs"},
            ],
        ):
            fs_type = self.linux_system.get_fs_type_for_path("/mnt/games/library")

        self.assertEqual(fs_type, "xfs")

    def test_get_fs_type_for_path_preserves_fuseblk_detection(self):
        with (
            patch.object(
                self.linux_system,
                "get_drives",
                return_value=[{"target": "/media/library", "source": "/dev/sdc1", "fstype": "fuseblk"}],
            ),
            patch.object(linux.system, "read_process_output", return_value="ntfs\n") as read_process_output,
        ):
            fs_type = self.linux_system.get_fs_type_for_path("/media/library/game")

        self.assertEqual(fs_type, "ntfs")
        read_process_output.assert_called_once_with(["blkid", "-o", "value", "-s", "TYPE", "/dev/sdc1"])
