import os
import tempfile
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from lutris.runners.commands import wine as wine_commands
from lutris.util.test_config import setup_test_environment
from lutris.util.wine.cabinstall import CabInstaller

setup_test_environment()


class FakeUmuCommand:
    """Stands in for the MonitoredCommand running 'umu-run createprefix'; it exits after
    being polled a given number of times."""

    def __init__(self, polls_before_exit):
        self.polls_before_exit = polls_before_exit
        self.return_code = None

    def start(self):
        pass

    @property
    def game_process_has_exited(self):
        if self.polls_before_exit > 0:
            self.polls_before_exit -= 1
            return False
        return True


class TestCreateProtonPrefix(TestCase):
    def setUp(self):
        prefix_dir = tempfile.TemporaryDirectory()
        self.addCleanup(prefix_dir.cleanup)
        self.prefix = prefix_dir.name

    def create_prefix(self, umu_command):
        with (
            patch.object(wine_commands, "is_disallowed_fs", return_value=False),
            patch.object(wine_commands.proton, "is_umu_path", return_value=True),
            patch.object(wine_commands.proton, "is_proton_path", return_value=True),
            patch.object(wine_commands.proton, "update_proton_env"),
            patch.object(wine_commands.proton, "get_umu_path", return_value="umu-run"),
            patch.object(wine_commands, "MonitoredCommand", return_value=umu_command),
            patch.object(wine_commands, "WinePrefixManager"),
            patch.object(wine_commands.time, "sleep"),
        ):
            wine_commands.create_prefix(
                self.prefix,
                wine_path="/nonexistent/proton/files/bin/wine",
                arch="win64",
                runner=SimpleNamespace(system_config={"env": {}}),
            )

    def write_registry_files(self):
        for name in ("user.reg", "userdef.reg", "system.reg"):
            with open(os.path.join(self.prefix, name), "w", encoding="utf-8"):
                pass

    def test_waits_for_umu_to_exit_after_registry_files_appear(self):
        self.write_registry_files()
        umu_command = FakeUmuCommand(polls_before_exit=3)
        self.create_prefix(umu_command)
        self.assertEqual(umu_command.polls_before_exit, 0)

    def test_raises_if_umu_exits_without_creating_prefix(self):
        with self.assertRaises(RuntimeError):
            self.create_prefix(FakeUmuCommand(polls_before_exit=0))

    def test_relative_prefix_link_is_followed_from_its_own_directory(self):
        # The registry files are where the link really points, not where its
        # target would be if read relative to the current directory
        os.makedirs(os.path.join(self.prefix, "shared"))
        os.makedirs(os.path.join(self.prefix, "game"))
        os.symlink("../shared", os.path.join(self.prefix, "game", "pfx"))
        link = os.path.join(self.prefix, "game", "pfx")
        for name in ("user.reg", "userdef.reg", "system.reg"):
            with open(os.path.join(self.prefix, "shared", name), "w", encoding="utf-8"):
                pass
        self.prefix = link
        self.create_prefix(FakeUmuCommand(polls_before_exit=0))


class TestSetRegedit(TestCase):
    def get_reg_file(self, value_type):
        contents = []

        def read_reg_file(path, **_kwargs):
            with open(path, encoding="utf-8") as reg_file:
                contents.append(reg_file.read())

        with patch.object(wine_commands, "set_regedit_file", side_effect=read_reg_file):
            wine_commands.set_regedit("HKEY_CURRENT_USER\\\\Software\\\\Test", "Value", "41,00,00,00", type=value_type)
        return contents[0]

    def test_value_types_are_written_with_their_numbers(self):
        # REG_EXPAND_SZ is type 2 and REG_MULTI_SZ is type 7
        self.assertIn('"Value"=hex(2):41,00,00,00', self.get_reg_file("REG_EXPAND_SZ"))
        self.assertIn('"Value"=hex(7):41,00,00,00', self.get_reg_file("REG_MULTI_SZ"))


class TestInstallCabComponent(TestCase):
    """A cab holds manifests for each architecture; their registry files must be applied
    with the prefix's own WINEARCH, since Wine refuses to run with any other."""

    def install(self, prefix_arch, registry_files):
        """Return the regedit, WINEARCH and file of each regedit run."""
        with (
            patch.object(CabInstaller, "extract_from_cab", return_value=[]),
            patch.object(CabInstaller, "get_registry_files", return_value=registry_files),
            patch.object(wine_commands.proton, "is_proton_path", return_value=False),
            patch.object(wine_commands.system, "path_exists", return_value=False),
            patch.object(wine_commands, "wineexec") as wineexec,
        ):
            wine_commands.install_cab_component(
                "/tmp/x.cab", "mfplat", "/opt/wine/bin/wine", prefix="/tmp/prefix", arch=prefix_arch
            )
        return [(call.args[0], call.kwargs["arch"], call.kwargs["args"]) for call in wineexec.call_args_list]

    def test_32_bit_components_use_the_32_bit_regedit_in_a_64_bit_prefix(self):
        runs = self.install("win64", [("/tmp/x86.reg", "win32"), ("/tmp/amd64.reg", "win64")])
        self.assertEqual(
            runs,
            [
                ("C:\\windows\\syswow64\\regedit.exe", "win64", "/S '/tmp/x86.reg'"),
                ("regedit", "win64", "/S '/tmp/amd64.reg'"),
            ],
        )

    def test_a_32_bit_prefix_uses_its_own_regedit(self):
        runs = self.install("win32", [("/tmp/x86.reg", "win32")])
        self.assertEqual(runs, [("regedit", "win32", "/S '/tmp/x86.reg'")])


class TestWineexecArguments(TestCase):
    def run_wineexec(self, executable, args):
        runner = SimpleNamespace(
            system_config={"disable_runtime": True, "prefer_system_libs": True},
            get_env=lambda disable_runtime: {},
            prelaunch=lambda: None,
        )
        with (
            patch.object(wine_commands, "is_prefix_directory", return_value=True),
            patch.object(wine_commands.proton, "is_proton_path", return_value=False),
            patch.object(wine_commands.proton, "is_umu_path", return_value=False),
            patch.object(wine_commands.system, "execute_with_error", return_value=("", "")) as execute,
        ):
            wine_commands.wineexec(
                executable,
                prefix="/tmp/prefix",
                args=args,
                wine_path="/opt/wine/bin/wine",
                runner=runner,
                blocking=True,
            )
        return execute.call_args.args[0]

    def test_msi_keeps_the_scripts_arguments(self):
        command = self.run_wineexec("/games/setup.msi", "/qn")
        self.assertEqual(command, ["/opt/wine/bin/wine", "msiexec", "/i", "/games/setup.msi", "/qn"])

    def test_exe_arguments_are_passed_as_given(self):
        command = self.run_wineexec("/games/setup.exe", "/S /VERYSILENT")
        self.assertEqual(command, ["/opt/wine/bin/wine", "/games/setup.exe", "/S", "/VERYSILENT"])
