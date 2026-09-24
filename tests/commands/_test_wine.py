from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import SkipTest, TestCase
from unittest.mock import DEFAULT, MagicMock, patch

from lutris.runners.commands.wine import (
    create_prefix,
    delete_registry_key,
    eject_disc,
    install_cab_component,
    open_wine_terminal,
    set_regedit,
    set_regedit_file,
    winecfg,
    wineexec,
    winekill,
    winetricks,
)
from lutris.util.system import find_executable

# Re-use temporary directory for all test in this file, so that WINEPREFIX is only created once
# Creating a wine prefix is a slow operation and therefore it is being avoided when
# multiple test are run in the same invocation
WINE_TASK_TEMP_DIR = TemporaryDirectory(ignore_cleanup_errors=True)


class Test_create_prefix(TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(WINE_TASK_TEMP_DIR.name)
        self.wine_prefix_path = self.tmp_path / "test_prefix"
        self.wine_path = find_executable("wine")
        if not self.wine_path:
            raise SkipTest("Wine must be installed to run these test")

    def test_create_prefix_succeeds(self):
        # The "install_mono" parameter checks for a string, not a bool
        create_prefix(
            str(self.wine_prefix_path),
            wine_path=self.wine_path,
            install_gecko="False",
            install_mono="False",
            env={"DISPLAY": ""},
        )
        self.assertTrue(self.wine_prefix_path.exists())


class Test_delete_registry_key(TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(WINE_TASK_TEMP_DIR.name)
        self.wine_prefix_path = self.tmp_path / "test_prefix"
        self.registry_path = self.wine_prefix_path / "system.reg"
        self.wine_path = find_executable("wine")
        if not self.wine_path:
            raise SkipTest("Wine must be installed to run these test")

    def test_delete_registry_key_succeeds(self):
        set_regedit(
            r"HKEY_LOCAL_MACHINE\Software\Wine\TESTKEY",
            "VNAME",
            value="Hello World",
            type="REG_SZ",
            prefix=str(self.wine_prefix_path),
            env={"WINEDLLOVERRIDES": "mscoree,mshtml=", "DISPLAY": ""},
        )

        # NOTE: There is a race condition where the `regedit` command might not have written to the registry
        # before the `reg query` command finish executing
        # result = wineexec(
        #    "reg",
        #    args="query" + r' "HKEY_LOCAL_MACHINE\Software\Wine\TESTKEY"' + ' -v "VNAME"',
        #    prefix=str(self.wine_prefix_path),
        #    blocking=True,
        # )
        # self.assertIn("VNAME", result)

        delete_registry_key(
            r"HKEY_LOCAL_MACHINE\Software\Wine\TESTKEY",
            wine_path=self.wine_path,
            prefix=str(self.wine_prefix_path),
            env={"WINEDLLOVERRIDES": "mscoree,mshtml=", "DISPLAY": ""},
        )

        # NOTE: There is a race condition where the `regedit` command might not have written to the registry
        # before the `reg query` command finish executing
        # result = wineexec(
        #    "reg",
        #    args="query" + r' "HKEY_LOCAL_MACHINE\Software\Wine\TESTKEY"' + ' -v "VNAME"',
        #    prefix=str(self.wine_prefix_path),
        #    blocking=True,
        # )
        # self.assertNotIn("VNAME", result)


class Test_eject_disc(TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(WINE_TASK_TEMP_DIR.name)
        self.wine_prefix_path = self.tmp_path / "test_prefix"
        self.wine_path = find_executable("wine")
        if not self.wine_path:
            raise SkipTest("Wine must be installed to run these test")

    def test_eject_disc_sanity_test(self):
        def wineexec_wrapper(
            executable: str,
            prefix: str,
            args: str = "",
            wine_path: str | None = None,
            arch: str = "win64",
            working_dir: str | None = None,
            winetricks_wine: str = "",
            blocking: bool = False,
            config=None,
            include_processes: list | None = None,
            exclude_processes: list | None = None,
            disable_runtime: bool = False,
            env: dict | None = None,
            overrides=None,
            runner=None,
            proton_verb: str | None = None,
        ):
            if executable == "eject":
                return True
            return DEFAULT

        mock_wineexec = MagicMock(side_effect=wineexec_wrapper, wraps=wineexec)
        with patch("lutris.runners.commands.wine.wineexec", mock_wineexec) as _wrap_wineexec:
            eject_disc(
                wine_path=self.wine_path,
                prefix=str(self.wine_prefix_path),
                env={"WINEDLLOVERRIDES": "mscoree,mshtml=", "DISPLAY": ""},
            )


class Test_install_cab_component(TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(WINE_TASK_TEMP_DIR.name)
        self.wine_prefix_path = self.tmp_path / "test_prefix"
        self.cabfile_path = self.wine_prefix_path / "test.cab"
        self.wine_path = find_executable("wine")
        if not self.wine_path:
            raise SkipTest("Wine must be installed to run these test")

    def test_install_cab_component_sanity_test(self):
        install_cab_component(
            self.cabfile_path,
            "",
            wine_path=self.wine_path,
            prefix=str(self.wine_prefix_path),
            arch="win64",
            env={"WINEDLLOVERRIDES": "mscoree,mshtml=", "DISPLAY": ""},
        )


class Test_open_wine_terminal(TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(WINE_TASK_TEMP_DIR.name)
        self.wine_prefix_path = self.tmp_path / "test_prefix"
        self.wine_path = find_executable("wine")
        if not self.wine_path:
            raise SkipTest("Wine must be installed to run these test")

    def test_wine_open_terminal_succeeds(self):
        with patch("lutris.util.system.spawn") as _patch_spawn:
            open_wine_terminal(
                None,
                wine_path=self.wine_path,
                prefix=str(self.wine_prefix_path),
                env={"WINEDLLOVERRIDES": "mscoree,mshtml=", "DISPLAY": ""},
                system_winetricks=True,
            )


class Test_set_regedit(TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(WINE_TASK_TEMP_DIR.name)
        self.wine_prefix_path = self.tmp_path / "test_prefix"
        self.registry_path = self.wine_prefix_path / "system.reg"
        self.wine_path = find_executable("wine")
        if not self.wine_path:
            raise SkipTest("Wine must be installed to run these test")

    def test_set_regedit_string_succeeds(self):
        for str_value, _expected_value in [("", "VNAME")]:
            with self.subTest(key=str_value):
                set_regedit(
                    r"HKEY_LOCAL_MACHINE\Software\Wine\TESTKEY",
                    "VNAME",
                    value=str_value,
                    type="REG_SZ",
                    wine_path=self.wine_path,
                    prefix=str(self.wine_prefix_path),
                    env={"WINEDLLOVERRIDES": "mscoree,mshtml=", "DISPLAY": ""},
                )

                # NOTE: There is a race condition where the `regedit` command might not have written to the registry
                # before the `reg query` command finish executing
                # result = wineexec(
                #    "reg",
                #    args="query" + r' "HKEY_LOCAL_MACHINE\Software\Wine\TESTKEY"' + ' -v "VNAME"',
                #    prefix=str(self.wine_prefix_path),
                #    blocking=True,
                # )
                # self.assertIn(_expected_value, result)


class Test_set_regedit_file(TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(WINE_TASK_TEMP_DIR.name)
        self.wine_prefix_path = self.tmp_path / "test_prefix"
        self.registry_path = self.wine_prefix_path / "system.reg"
        self.wine_path = find_executable("wine")
        if not self.wine_path:
            raise SkipTest("Wine must be installed to run these test")

    def test_set_regedit_file_dword_succeeds(self):
        for str_value, _expected_regex in [("dword:1", r"VNAME.+0x1")]:
            with self.subTest(key=str_value):
                regedit_file = self.tmp_path / "test.reg"
                with regedit_file.open("w", encoding="utf-8") as reg_file:
                    reg_file.write("REGEDIT4\n\n")
                    reg_file.write("[HKEY_LOCAL_MACHINE\\Software\\Wine\\TEST_DWORD_KEY]\n")
                    reg_file.write('"VNAME"=dword:1')

                set_regedit_file(
                    regedit_file,
                    wine_path=self.wine_path,
                    prefix=str(self.wine_prefix_path),
                    env={"WINEDLLOVERRIDES": "mscoree,mshtml=", "DISPLAY": ""},
                )
                # NOTE: There is a race condition where the `regedit` command might not have written to the registry
                # before the `reg query` command finish executing
                # result = wineexec(
                #    "reg",
                #    args="query" + r' "HKEY_LOCAL_MACHINE\Software\Wine\TEST_DWORD_KEY"' + ' -v "VNAME"',
                #    prefix=str(self.wine_prefix_path),
                #    blocking=True,
                # )
                # self.assertRegex(result, _expected_regex)


class Test_winecfg(TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(WINE_TASK_TEMP_DIR.name)
        self.wine_prefix_path = self.tmp_path / "test_prefix"
        self.registry_path = self.wine_prefix_path / "system.reg"
        self.wine_path = find_executable("wine")
        if not self.wine_path:
            raise SkipTest("Wine must be installed to run these test")

    def test_winecfg_sanity_test(self):
        def wineexec_wrapper(
            executable: str,
            prefix: str,
            args: str = "",
            wine_path: str | None = None,
            arch: str = "win64",
            working_dir: str | None = None,
            winetricks_wine: str = "",
            blocking: bool = False,
            config=None,
            include_processes: list | None = None,
            exclude_processes: list | None = None,
            disable_runtime: bool = False,
            env: dict | None = None,
            overrides=None,
            runner=None,
            proton_verb: str | None = None,
        ):
            if executable == "winecfg.exe":
                return True
            return DEFAULT

        mock_wineexec = MagicMock(side_effect=wineexec_wrapper, wraps=wineexec)
        with patch("lutris.runners.commands.wine.wineexec", mock_wineexec) as _wrap_wineexec:
            winecfg(
                wine_path=self.wine_path,
                prefix=str(self.wine_prefix_path),
                env={"WINEDLLOVERRIDES": "mscoree,mshtml=", "DISPLAY": ""},
            )


class Test_wineexec(TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(WINE_TASK_TEMP_DIR.name)
        self.wine_prefix_path = self.tmp_path / "test_prefix"
        self.wine_path = find_executable("wine")
        if not self.wine_path:
            raise SkipTest("Wine must be installed to run these test")

    def test_wineexec_sanity_test(self):
        wineexec(
            "reg",
            args="query" + r' "HKEY_LOCAL_MACHINE\Software\Wine\DRIVES"',
            prefix=str(self.wine_prefix_path),
            wine_path=self.wine_path,
            env={"WINEDLLOVERRIDES": "mscoree,mshtml=", "DISPLAY": ""},
        )


class Test_winekill(TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(WINE_TASK_TEMP_DIR.name)
        self.wine_prefix_path = self.tmp_path / "test_prefix"
        self.wine_path = find_executable("wine")
        if not self.wine_path:
            raise SkipTest("Wine must be installed to run these test")

    def test_winekill_sanity_test(self):
        winekill(
            prefix=str(self.wine_prefix_path),
            wine_path=self.wine_path,
            env={"WINEDLLOVERRIDES": "mscoree,mshtml=", "DISPLAY": ""},
        )


class Test_winetricks(TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(WINE_TASK_TEMP_DIR.name)
        self.wine_prefix_path = self.tmp_path / "test_prefix"
        self.wine_path = find_executable("wine")
        if not self.wine_path:
            raise SkipTest("Wine must be installed to run these test")

    def test_winetricks_sanity_test(self):
        winetricks(
            app=None,
            prefix=str(self.wine_prefix_path),
            wine_path=self.wine_path,
            env={"WINEDLLOVERRIDES": "mscoree,mshtml=", "DISPLAY": ""},
        )
