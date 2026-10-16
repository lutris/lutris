import sys
from unittest import TestCase
from unittest.mock import patch

import yaml

from lutris.installer.errors import ScriptingError
from lutris.installer.interpreter import ScriptInterpreter
from lutris.util.test_config import setup_test_environment

setup_test_environment()


class TestExecuteCommand(TestCase):
    def setUp(self):
        installer = {
            "script": {"game": {"exe": "test"}},
            "version": "test",
            "game_slug": "test",
            "name": "test",
            "slug": "test",
            "runner": "linux",
        }
        self.interpreter = ScriptInterpreter(installer)
        process_patch = patch("lutris.installer.commands.MonitoredCommand")
        self.process = process_patch.start()
        self.addCleanup(process_patch.stop)
        schedule_patch = patch("lutris.installer.commands.schedule_repeating_at_idle")
        self.schedule = schedule_patch.start()
        self.addCleanup(schedule_patch.stop)

    def assert_invalid_command(self, params):
        step = {"execute": params}
        command_name, command, command_data = self.interpreter._map_command(step)
        self.assertEqual(command_name, "execute")
        with self.assertRaisesRegex(ScriptingError, "command.*string") as error:
            command(command_data)
        self.assertIs(error.exception.faulty_data, params)
        self.process.assert_not_called()
        self.schedule.assert_not_called()

    def test_nested_list_from_yaml_reports_a_scripting_error(self):
        step = yaml.safe_load("execute:\n  command:\n  - - 'pwd'\n")
        self.assert_invalid_command(step["execute"])

    def test_non_string_commands_report_scripting_errors(self):
        for value in ([], {}, None, False, True, 0, 1, 1.5):
            with self.subTest(command=value):
                self.assert_invalid_command({"command": value})

    def test_invalid_command_is_rejected_before_parsing_other_parameters(self):
        params = {"command": [["pwd"]], "args": "'", "return_code": "7"}
        self.assert_invalid_command(params)
        self.assertEqual(params["return_code"], "7")

    def test_string_command_keeps_shell_parsing_and_monitoring(self):
        result = self.interpreter.execute({"command": "  echo Hello World! | cat  ", "disable_runtime": True})

        self.assertEqual(result, "STOP")
        self.assertEqual(self.process.call_args.args[0][1:], ["-c", "echo Hello World! | cat"])
        self.assertEqual(self.process.call_args.kwargs["include_processes"], ["bash"])
        self.assertEqual(self.process.return_value.accepted_return_code, "0")
        self.process.return_value.start.assert_called_once_with()
        self.schedule.assert_called_once_with(
            self.interpreter._monitor_task, self.process.return_value, interval_seconds=1.0
        )

    def test_file_command_keeps_arguments_and_return_code(self):
        params = {
            "file": sys.executable,
            "args": '-c "print(123)"',
            "return_code": "7",
            "disable_runtime": True,
        }
        result = self.interpreter.execute(params)

        self.assertEqual(result, "STOP")
        self.assertEqual(self.process.call_args.args[0], [sys.executable, "-c", "print(123)"])
        self.assertEqual(self.process.call_args.kwargs["include_processes"], [])
        self.assertEqual(self.process.return_value.accepted_return_code, "7")
        self.process.return_value.start.assert_called_once_with()

    def test_file_and_command_remain_mutually_exclusive(self):
        with self.assertRaisesRegex(ScriptingError, "file and command can't be used at the same time"):
            self.interpreter.execute({"file": sys.executable, "command": "echo test"})
        self.process.assert_not_called()
