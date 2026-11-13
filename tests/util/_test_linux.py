from unittest import TestCase
from unittest.mock import patch

from lutris.util import linux
from lutris.util.linux import SharedLibrary


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


class TestSystemComponents(TestCase):
    def test_command_lists_have_no_duplicates(self):
        for key in ("COMMANDS", "OPTIONAL_COMMANDS", "TERMINALS"):
            commands = linux.SYSTEM_COMPONENTS[key]
            self.assertEqual(len(commands), len(set(commands)), "Duplicates in %s: %s" % (key, commands))


class TestSharedLibrary(TestCase):
    def test_new_from_ldconfig_parses_valid_line(self):
        with patch.object(linux, "is_exherbo_with_cross_i686", return_value=False):
            lib = SharedLibrary.new_from_ldconfig("libGL.so.1 (libc6,x86-64) => /usr/lib/libGL.so.1")

        self.assertEqual(lib.name, "libGL.so.1")
        self.assertEqual(lib.basename, "libGL")
        self.assertEqual(lib.arch, "x86_64")
        self.assertEqual(lib.dirname, "/usr/lib")

    def test_new_from_ldconfig_defaults_to_i386(self):
        with patch.object(linux, "is_exherbo_with_cross_i686", return_value=False):
            lib = SharedLibrary.new_from_ldconfig("libGL.so.1 (libc6) => /usr/lib32/libGL.so.1")

        self.assertEqual(lib.arch, "i386")

    def test_new_from_ldconfig_rejects_malformed_line(self):
        with self.assertRaises(ValueError):
            SharedLibrary.new_from_ldconfig("this is not a valid ldconfig line")


class TestGetMissingRequirementLibs(TestCase):
    def setUp(self):
        self.linux_system = linux.LinuxSystem.__new__(linux.LinuxSystem)
        self.linux_system.arch = "x86_64"
        # Pretend the libraries were already loaded so the shared_libraries property
        # returns the cache without trying to parse the real system.
        self.linux_system._shared_libraries = {}

    def test_reports_missing_libs_per_architecture(self):
        self.linux_system._cache = {
            "LIBRARIES": {
                "i386": {"VULKAN": []},
                "x86_64": {"VULKAN": ["libvulkan.so.1"]},
            }
        }
        with patch.object(linux, "is_exherbo_with_cross_i686", return_value=False):
            missing = self.linux_system.get_missing_requirement_libs("VULKAN")

        self.assertEqual(missing, [["libvulkan.so.1"], []])


class TestGetMissingLibArch(TestCase):
    def setUp(self):
        self.linux_system = linux.LinuxSystem.__new__(linux.LinuxSystem)
        self.linux_system.arch = "x86_64"

    def test_reports_architectures_with_missing_libs(self):
        with (
            patch.object(linux, "is_exherbo_with_cross_i686", return_value=False),
            patch.object(
                self.linux_system,
                "get_missing_requirement_libs",
                return_value=[["libvulkan.so.1"], []],
            ) as get_missing,
        ):
            missing = self.linux_system.get_missing_lib_arch("VULKAN")

        self.assertEqual(missing, ["i386"])
        # The requirement is computed once, not once per architecture.
        get_missing.assert_called_once_with("VULKAN")

    def test_returns_empty_when_nothing_is_missing(self):
        with (
            patch.object(linux, "is_exherbo_with_cross_i686", return_value=False),
            patch.object(self.linux_system, "get_missing_requirement_libs", return_value=[[], []]),
        ):
            missing = self.linux_system.get_missing_lib_arch("VULKAN")

        self.assertEqual(missing, [])


class TestGetLdconfigLibs(TestCase):
    def setUp(self):
        self.linux_system = linux.LinuxSystem.__new__(linux.LinuxSystem)
        self.linux_system._cache = {"COMMANDS": {"ldconfig": "/sbin/ldconfig"}}

    def test_returns_parsed_library_lines(self):
        output = "libs\n\tlibGL.so.1 (libc6,x86-64) => /usr/lib/libGL.so.1\n"
        with (
            patch.object(linux, "is_exherbo_with_cross_i686", return_value=False),
            patch.object(linux.system, "read_process_output", return_value=output),
        ):
            libs = self.linux_system.get_ldconfig_libs()

        self.assertEqual(libs, ["libGL.so.1 (libc6,x86-64) => /usr/lib/libGL.so.1"])

    def test_returns_empty_list_on_empty_output(self):
        with (
            patch.object(linux, "is_exherbo_with_cross_i686", return_value=False),
            patch.object(linux.system, "read_process_output", return_value=""),
        ):
            self.assertEqual(self.linux_system.get_ldconfig_libs(), [])


class TestGetGlxinfo(TestCase):
    def setUp(self):
        self.linux_system = linux.LinuxSystem.__new__(linux.LinuxSystem)
        self.linux_system._cache = {"COMMANDS": {}}

    def test_returns_none_without_running_glxinfo_when_unavailable(self):
        with patch.object(linux.glxinfo, "GlxInfo") as glxinfo_class:
            self.assertIsNone(self.linux_system.get_glxinfo())
            glxinfo_class.assert_not_called()

    def test_glxinfo_property_caches_negative_result(self):
        with patch.object(self.linux_system, "get_glxinfo", return_value=None) as get_glxinfo:
            self.assertIsNone(self.linux_system.glxinfo)
            self.assertIsNone(self.linux_system.glxinfo)
            get_glxinfo.assert_called_once()


class TestPopulateSoundFonts(TestCase):
    def setUp(self):
        self.linux_system = linux.LinuxSystem.__new__(linux.LinuxSystem)
        self.linux_system._cache = {}
        self.linux_system.soundfont_folders = ["/usr/share/soundfonts"]

    def test_collects_soundfonts(self):
        with patch.object(linux.os, "listdir", return_value=["font.sf2"]):
            self.linux_system.populate_sound_fonts()

        self.assertEqual(self.linux_system.get_soundfonts(), ["font.sf2"])

    def test_tolerates_unreadable_folder(self):
        with patch.object(linux.os, "listdir", side_effect=OSError):
            self.linux_system.populate_sound_fonts()

        self.assertEqual(self.linux_system.get_soundfonts(), [])


class TestGetArch(TestCase):
    def test_known_architectures(self):
        for machine, expected in (
            ("x86_64", "x86_64"),
            ("i686", "i386"),
            ("armv7l", "armv7"),
            ("aarch64", "aarch64"),
        ):
            with patch.object(linux.platform, "machine", return_value=machine):
                self.assertEqual(linux.LinuxSystem.get_arch(), expected)

    def test_unknown_architecture_returns_none(self):
        with patch.object(linux.platform, "machine", return_value="sparc64"):
            self.assertIsNone(linux.LinuxSystem.get_arch())
