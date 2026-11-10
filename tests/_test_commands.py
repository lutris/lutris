"""
Test to verify that all registered commands contain at least one unit test
"""

import ast
from pathlib import Path
from typing import TypeAlias
from unittest import TestCase

from lutris.util.test_config import setup_test_environment

setup_test_environment()

CommandList: TypeAlias = list[str]
RunnerToCommandDict: TypeAlias = dict[Path, CommandList]

REGISTER_COMMAND_DECORATOR = "register_runner_task"


def get_commands_from_file(path):
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError):
        return []

    commands = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            decorator_ids = [decorator_name.id for decorator_name in node.decorator_list]
            if REGISTER_COMMAND_DECORATOR in decorator_ids:
                commands.append(node.name)

    return sorted(commands)


def find_all_commands() -> RunnerToCommandDict:
    # Get all files under the lutris/runners/command folder except for __init__.py
    paths = sorted([path for path in Path("lutris/runners/commands").rglob("*.py") if path.name != "__init__.py"])

    all_commands = {}
    for path in paths:
        commands = get_commands_from_file(path)
        if path not in all_commands:
            all_commands[path] = commands
        else:
            all_commands[path] += commands

    return all_commands


def get_test_classes_from_file(path):
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError):
        return []

    test_class_nodes = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            base_class_ids = [base_class_name.id for base_class_name in node.bases]
            if "TestCase" in base_class_ids:
                test_class_nodes.append(node)

    return test_class_nodes


class TestCommands(TestCase):
    def test_all_command_scripts_register_at_least_1_command(self):
        runner_command_table = find_all_commands()
        self.assertGreater(len(runner_command_table), 0)
        for runner_file, command_list in runner_command_table.items():
            self.assertGreater(
                len(command_list), 0, "Runner command file '%s' contains no registered commands" % (runner_file,)
            )

    def test_all_commands_have_at_least_1_test(self):
        runner_command_table = find_all_commands()
        for runner_file, command_list in runner_command_table.items():
            with self.subTest(runner=runner_file.stem) as _subtest:
                test_file_path = Path("tests/commands") / f"_test_{runner_file.name}"
                self.assertTrue(
                    test_file_path.exists(),
                    "Test file '%s' for runner command file '%s' does not exist" % (test_file_path, runner_file),
                )

                test_classes = get_test_classes_from_file(test_file_path)
                self.assertGreater(
                    len(test_classes),
                    0,
                    "Test file '%s' contains no test classes for runner command file '%s'"
                    % (test_file_path, runner_file),
                )

                test_class_names = [test_class.name for test_class in test_classes]

                # Now check if the module has a Test class for each register command from that file
                # with the naming scheme of Test_<command_name>
                for command in command_list:
                    try:
                        test_class_index = test_class_names.index(f"Test_{command}")
                        test_class = test_classes[test_class_index]
                    except ValueError:
                        self.fail(
                            "Command '%s' is missing test class 'Test_%s' in file '%s"
                            % (command, command, test_file_path),
                        )

                    # Count the number of methods that start with the "test_"
                    test_methods = [
                        body_node
                        for body_node in test_class.body
                        if isinstance(body_node, ast.FunctionDef) and body_node.name.startswith("test_")
                    ]
                    self.assertGreater(
                        len(test_methods),
                        0,
                        "Command '%s' contains no test in test class `%s`" % (command, test_class.name),
                    )
