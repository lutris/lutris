import os
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

import yaml

from lutris.installer import commands
from lutris.installer.errors import FlatpakSetupError
from lutris.runners.commands import flatpak as tasks
from lutris.util import flatpak
from lutris.util import flatpak_install as install

APPID = "io.github.shonebinu.Brief"
REF = f"app/{APPID}/x86_64/stable"


def result(stdout="", code=0, stderr=""):
    return subprocess.CompletedProcess([], code, stdout, stderr)


class TestFlatpakInstall(TestCase):
    def host(self, args, timeout=30):
        self.calls.append(args)
        if args[0] == "--version":
            return result("Flatpak 1.16.0")
        if args[0] == "info":
            return result(code=1)
        if args[0] == "remotes":
            return result(self.remotes)
        if args[0] == "remote-info":
            return result(REF)
        return result()

    def setUp(self):
        self.calls = []
        self.remotes = "flathub\n"
        self.host_patch = patch.object(install, "run_host", side_effect=self.host)
        self.command_patch = patch.object(flatpak, "get_command", return_value=["/usr/bin/flatpak"])
        self.executable_patch = patch.object(flatpak, "get_executable", return_value="/usr/bin/flatpak")
        self.executable_patch.start()
        self.addCleanup(self.executable_patch.stop)
        self.host_patch.start()
        self.command_patch.start()
        self.addCleanup(self.host_patch.stop)
        self.addCleanup(self.command_patch.stop)

    def test_flathub_install_uses_exact_ref_and_user_scope(self):
        plan = install.prepare_install(APPID)
        self.assertEqual(plan.command[-2:], ["flathub", REF])
        self.assertIn("--user", plan.command)
        self.assertIn("--noninteractive", plan.command)
        self.assertFalse(plan.was_installed)
        self.assertTrue(all("--user" in args for args in self.calls if args[0] != "--version"))

    def test_system_only_app_does_not_skip_user_install(self):
        plan = install.prepare_install(APPID)
        self.assertTrue(plan.command)
        self.assertIn(["info", "--user", "--show-ref", APPID], self.calls)

    def test_existing_user_app_is_not_installed_again(self):
        with patch.object(install, "get_user_ref", return_value=REF):
            plan = install.prepare_install(APPID)
        self.assertEqual(plan.command, [])
        self.assertTrue(plan.was_installed)
        self.assertEqual(self.calls, [["--version"]])

    def test_adds_missing_flathub_only_after_confirmation(self):
        self.remotes = ""
        confirm = MagicMock(return_value=False)
        with self.assertRaises(install.FlatpakInstallError):
            install.prepare_install(APPID, confirm=confirm)
        self.assertFalse(any(args[0] == "remote-add" for args in self.calls))
        self.calls.clear()
        confirm.return_value = True
        install.prepare_install(APPID, confirm=confirm)
        self.assertIn(["remote-add", "--user", "--if-not-exists", "flathub", install.FLATHUB_URL], self.calls)

    def test_missing_host_or_denied_access_is_not_a_missing_app(self):
        with patch.object(install, "run_host", return_value=result(code=1, stderr="Access denied")):
            with self.assertRaises(install.FlatpakPrerequisiteError) as caught:
                install.prepare_install(APPID)
            self.assertEqual(caught.exception.reason, "access")

    def test_rejects_option_injection(self):
        for appid in ("--system", "io.github.Brief --system", "io.github.Brief/stable"):
            with self.subTest(appid=appid), self.assertRaises(install.FlatpakInstallError):
                install.prepare_install(appid)
        self.assertEqual(self.calls, [])

    def test_remote_lookup_failure_stops_before_installation(self):
        def unavailable(args, timeout=30):
            if args[0] == "remote-info":
                return result(code=1, stderr="No such application")
            return self.host(args, timeout)

        with patch.object(install, "run_host", side_effect=unavailable):
            with self.assertRaisesRegex(install.FlatpakInstallError, "No such application"):
                install.prepare_install(APPID)

    def test_native_and_sandbox_probes_use_argument_lists(self):
        self.host_patch.stop()
        for prefix in (["flatpak"], ["flatpak-spawn", "--host", "flatpak"]):
            with (
                patch.object(flatpak, "get_command", return_value=list(prefix)),
                patch.object(install.subprocess, "run", return_value=result("Flatpak 1.16")) as run,
            ):
                install.check_host()
                self.assertEqual(run.call_args.args[0], prefix + ["--version"])
                self.assertFalse(run.call_args.kwargs.get("shell", False))

    def test_downloaded_bundle_does_not_require_flathub(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "app with spaces.flatpak"
            path.write_bytes(b"bundle")
            with patch.object(flatpak, "is_sandboxed", return_value=False):
                plan = install.prepare_install(APPID, file=str(path))
            self.assertEqual(plan.command[-2:], ["--bundle", str(path)])
            self.assertFalse(any(args[0] == "remotes" for args in self.calls))

    def test_reference_checks_id_and_requests_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "app.flatpakref"
            path.write_text(f"[Flatpak Ref]\nName={APPID}\nUrl=https://example.org/repo\n")
            with patch.object(flatpak, "is_sandboxed", return_value=False):
                with self.assertRaises(install.FlatpakInstallError):
                    install.prepare_install(APPID, file=str(path))
                plan = install.prepare_install(APPID, file=str(path), confirm=lambda _question: True)
            self.assertIn("--from", plan.command)
            path.write_text("[Flatpak Ref]\nName=org.example.Other\n")
            with self.assertRaises(install.FlatpakInstallError):
                install.prepare_install(APPID, file=str(path), confirm=lambda _question: True)

    def test_sandbox_stages_private_download_for_host(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "download.flatpak"
            path.write_bytes(b"contents")
            with (
                patch.object(flatpak, "is_sandboxed", return_value=True),
                patch.object(Path, "home", return_value=Path(directory)),
                patch.dict(os.environ, {"FLATPAK_ID": "net.lutris.Lutris"}),
                patch.object(flatpak, "get_command", return_value=["flatpak-spawn", "--host", "flatpak"]),
            ):
                plan = install.prepare_install(APPID, file=str(path))
            self.assertEqual(plan.command[:3], ["flatpak-spawn", "--host", "flatpak"])
            self.assertIn("/.var/app/net.lutris.Lutris/cache/", plan.command[-1])
            self.assertEqual(Path(plan.command[-1]).read_bytes(), b"contents")
            plan.cleanup()
            self.assertFalse(Path(plan.command[-1]).exists())

    def test_uninstall_is_user_only_and_preserves_data(self):
        with patch.object(install, "get_user_ref", return_value=REF):
            install.uninstall_user(APPID)
        self.assertEqual(self.calls[-1], ["uninstall", "--user", "--noninteractive", "--assumeyes", REF])
        self.assertNotIn("--delete-data", self.calls[-1])
        self.assertNotIn("--unused", self.calls[-1])

    def test_uninstall_failure_is_reported(self):
        with (
            patch.object(install, "check_host"),
            patch.object(install, "get_user_ref", return_value=REF),
            patch.object(install, "run_host", return_value=result(code=1, stderr="Failure")),
            self.assertRaisesRegex(install.FlatpakInstallError, "Failure"),
        ):
            install.uninstall_user(APPID)

    def test_user_launch_supports_native_and_host_bridge(self):
        for prefix in (["flatpak"], ["flatpak-spawn", "--host", "flatpak"]):
            with patch.object(flatpak, "get_command", return_value=list(prefix)):
                self.assertEqual(flatpak.get_bare_run_command(installation="user"), prefix + ["run", "--user"])

    def test_post_installation_records_ownership_only_on_success(self):
        for was_installed in (False, True):
            config = {}
            plan = install.InstallPlan(APPID, [], was_installed)
            with patch.object(tasks, "get_user_ref", return_value=REF):
                tasks.save_installation(plan, config)
            self.assertEqual(config["install_type"], "user")
            self.assertEqual(config["branch"], "stable")
            self.assertEqual(config["flatpak_installed_by_lutris"], not was_installed)
        config = {}
        with patch.object(tasks, "get_user_ref", return_value=""):
            with self.assertRaises(tasks.ScriptingError):
                tasks.save_installation(plan, config)
        self.assertEqual(config, {})

    def test_nonzero_exit_never_marks_installation_complete(self):
        command = object.__new__(tasks.FlatpakInstallCommand)
        command.return_code = "1"
        command.plan = install.InstallPlan(APPID, [], False)
        command.game_config = {}
        with self.assertRaises(tasks.ScriptingError):
            command.finish_installation()
        self.assertEqual(command.game_config, {})


class TestFlatpakInstallerTaskFlow(TestCase):
    def test_task_keeps_installer_script_serializable(self):
        interpreter = MagicMock()
        task_data = {"name": "install_flatpak", "file": "package"}
        script = {"game": {"appid": APPID}, "installer": [{"task": task_data}]}
        interpreter.installer = SimpleNamespace(runner="flatpak", script=script)
        interpreter._get_task_runner_and_name.return_value = ("flatpak", "install_flatpak")
        interpreter._substitute.side_effect = lambda value: value
        with patch.object(commands, "import_task", return_value=MagicMock(return_value=None)) as import_task:
            commands.CommandsMixin.task(interpreter, task_data)
            self.assertIs(import_task.return_value.call_args.kwargs["game_config"], script["game"])
            self.assertTrue(callable(import_task.return_value.call_args.kwargs["confirm"]))
        self.assertEqual(task_data, {"name": "install_flatpak", "file": "package"})
        self.assertEqual(yaml.safe_load(yaml.safe_dump(script)), script)

    def test_task_resolves_download_alias_and_default_application_id(self):
        interpreter = MagicMock()
        game_config = {"appid": APPID}
        interpreter.installer = SimpleNamespace(runner="flatpak", script={"game": game_config})
        interpreter._get_task_runner_and_name.return_value = ("flatpak", "install_flatpak")
        interpreter._substitute.side_effect = lambda value: "/cache/package.flatpak" if value == "package" else value
        with patch.object(commands, "import_task", return_value=MagicMock(return_value=None)) as import_task:
            commands.CommandsMixin.task(interpreter, {"name": "install_flatpak", "file": "package"})
            task = import_task.return_value
            self.assertEqual(task.call_args.kwargs["appid"], APPID)
            self.assertEqual(task.call_args.kwargs["file"], "/cache/package.flatpak")
            self.assertIs(task.call_args.kwargs["game_config"], game_config)

    def test_yuno_task_dispatch_uses_downloaded_bundle_for_native_and_sandbox(self):
        """YUNO's published task must resolve its file alias in either environment."""
        for prefix in (["flatpak"], ["flatpak-spawn", "--host", "flatpak"]):
            with self.subTest(prefix=prefix):
                interpreter = MagicMock()
                script = {
                    "game": {"appid": "technology.haniwa.ai5-sdl2"},
                    "files": [{"engine": "https://example.org/ai5-sdl2.flatpak"}],
                    "installer": [
                        {"task": {"name": "install_flatpak", "file": "engine"}},
                        {"extract": {"file": "data", "dst": "$GAMEDIR"}},
                        {"copy": {"src": "font", "dst": "$GAMEDIR"}},
                    ],
                }
                interpreter.installer = SimpleNamespace(runner="flatpak", script=script)
                interpreter._get_task_runner_and_name.return_value = ("flatpak", "install_flatpak")
                interpreter._substitute.side_effect = (
                    lambda value: "/cache/ai5-sdl2.flatpak" if value == "engine" else value
                )
                with (
                    patch.object(commands, "import_task", return_value=MagicMock(return_value=None)) as task,
                    patch.object(flatpak, "get_command", return_value=list(prefix)),
                ):
                    commands.CommandsMixin.task(interpreter, script["installer"][0]["task"])
                    kwargs = task.return_value.call_args.kwargs
                    self.assertEqual(kwargs["appid"], "technology.haniwa.ai5-sdl2")
                    self.assertEqual(kwargs["file"], "/cache/ai5-sdl2.flatpak")
                    self.assertEqual(flatpak.get_command(), prefix)
                self.assertEqual(script["installer"][0]["task"]["file"], "engine")
                self.assertEqual(
                    [next(iter(step)) for step in script["installer"]],
                    ["task", "extract", "copy"],
                )
                self.assertEqual(yaml.safe_load(yaml.safe_dump(script)), script)

    def test_monitor_records_success_before_advancing_installer(self):
        interpreter = MagicMock()
        command = object.__new__(tasks.FlatpakInstallCommand)
        command.is_running = False
        command.return_code = "0"
        command.accepted_return_code = "0"
        command.plan = install.InstallPlan(APPID, [], False)
        command.game_config = {}
        with patch.object(tasks, "get_user_ref", return_value=REF):
            commands.CommandsMixin._monitor_task(interpreter, command)
        self.assertTrue(command.game_config["flatpak_installed_by_lutris"])
        interpreter._iter_commands.assert_called_once()

    def test_monitor_keeps_configuration_unchanged_after_failure(self):
        interpreter = MagicMock()
        command = object.__new__(tasks.FlatpakInstallCommand)
        command.is_running = False
        command.return_code = "1"
        command.accepted_return_code = "0"
        command.plan = install.InstallPlan(APPID, [], False)
        command.game_config = {}
        with self.assertRaises(tasks.ScriptingError):
            commands.CommandsMixin._monitor_task(interpreter, command)
        self.assertEqual(command.game_config, {})
        interpreter._iter_commands.assert_not_called()


class TestFlatpakPrerequisiteMessages(TestCase):
    def test_missing_native_flatpak_has_its_own_reason(self):
        with (
            patch.object(flatpak, "get_executable", return_value=None),
            patch.object(flatpak, "is_sandboxed", return_value=False),
            self.assertRaises(install.FlatpakPrerequisiteError) as caught,
        ):
            install.check_host()
        self.assertEqual(caught.exception.reason, "missing")

    def test_missing_sandbox_bridge_is_not_reported_as_missing_host_flatpak(self):
        with (
            patch.object(flatpak, "get_executable", return_value=None),
            patch.object(flatpak, "is_sandboxed", return_value=True),
            self.assertRaises(install.FlatpakPrerequisiteError) as caught,
        ):
            install.check_host()
        self.assertEqual(caught.exception.reason, "access")

    def test_install_task_produces_expected_dialog_error(self):
        for reason in ("missing", "access"):
            with (
                self.subTest(reason=reason),
                patch.object(tasks, "prepare_install", side_effect=install.FlatpakPrerequisiteError(reason)),
                self.assertRaises(FlatpakSetupError) as caught,
            ):
                tasks.install_flatpak(APPID)
            self.assertTrue(caught.exception.is_expected)
            self.assertTrue(caught.exception.title)
            self.assertNotIn("Traceback", str(caught.exception))
