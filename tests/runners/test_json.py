import unittest

from lutris.runners import json
from lutris.runners.model import (
    ModelRunner,
)


class TestJsonRunner(unittest.TestCase):
    def setUp(self):
        self.runners = [runner_class() for runner_class in json.load_json_runners().values()]

    def test_validate_installed_runners(self):
        for runner in self.runners:
            with self.subTest(runner.name):
                runner_messages = ModelRunner.validate(runner.to_dict())
                error_messages = list(runner_messages.get_errors())
                self.assertEqual(
                    len(error_messages),
                    0,
                    f"Validation failed for runner at path '{runner.file_path}':\nErrors:\n"
                    f"{
                        '\n'.join(
                            [
                                f'{runner_message.key_path}: {runner_message.message}'
                                for runner_message in error_messages
                            ]
                        )
                    }",
                )
