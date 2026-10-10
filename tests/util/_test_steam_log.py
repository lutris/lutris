import os
import tempfile
from unittest import TestCase

from lutris.util.steam import log

# Steam writes content_log.txt with CRLF line endings and separates each run
# from the previous one with an empty line.
RUN_SEPARATOR = "\r\n\r\n"
OLD_RUN = (
    "[2024-01-01 10:00:00] AppID 440 state changed : Fully Installed,\r\n"
    "[2024-01-01 10:00:01] AppID 570 state changed : Fully Installed,\r\n"
)
NEW_RUN = (
    "[2024-01-02 11:00:00] AppID 440 state changed : Fully Installed,Update Queued,\r\n"
    "[2024-01-02 11:00:01] AppID 440 state changed : Running,\r\n"
)


def _lines(content):
    """Return content as the list of lines _get_last_content_log should produce."""
    return [line + "\n" for line in content.split("\r\n") if line]


class TestGetLastContentLog(TestCase):
    def _steam_dir(self, content):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        logs_dir = os.path.join(temp_dir.name, "logs")
        os.makedirs(logs_dir)
        # newline="" keeps the CRLF line endings Steam actually writes
        with open(os.path.join(logs_dir, "content_log.txt"), "w", encoding="utf-8", newline="") as log_file:
            log_file.write(content)
        return temp_dir.name

    def test_returns_only_the_latest_run(self):
        steam_dir = self._steam_dir(OLD_RUN + RUN_SEPARATOR + NEW_RUN)

        self.assertEqual(log._get_last_content_log(steam_dir), _lines(NEW_RUN))

    def test_returns_latest_run_when_the_file_ends_with_a_separator(self):
        steam_dir = self._steam_dir(OLD_RUN + RUN_SEPARATOR + NEW_RUN + RUN_SEPARATOR)

        self.assertEqual(log._get_last_content_log(steam_dir), _lines(NEW_RUN))

    def test_returns_whole_file_when_there_is_no_separator(self):
        steam_dir = self._steam_dir(OLD_RUN)

        self.assertEqual(log._get_last_content_log(steam_dir), _lines(OLD_RUN))

    def test_a_single_empty_line_does_not_start_a_new_block(self):
        steam_dir = self._steam_dir(OLD_RUN + "\r\n" + NEW_RUN)

        self.assertEqual(log._get_last_content_log(steam_dir), _lines(OLD_RUN + NEW_RUN))

    def test_handles_unix_line_endings(self):
        steam_dir = self._steam_dir("first line\n\n\nnew block\n")

        self.assertEqual(log._get_last_content_log(steam_dir), ["new block\n"])

    def test_empty_log_file_returns_no_lines(self):
        steam_dir = self._steam_dir("")

        self.assertEqual(log._get_last_content_log(steam_dir), [])

    def test_missing_log_file_returns_no_lines(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        self.assertEqual(log._get_last_content_log(temp_dir.name), [])

    def test_missing_steam_data_dir_returns_no_lines(self):
        self.assertEqual(log._get_last_content_log(""), [])


class TestGetAppStateLog(TestCase):
    def _steam_dir(self, content):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        logs_dir = os.path.join(temp_dir.name, "logs")
        os.makedirs(logs_dir)
        with open(os.path.join(logs_dir, "content_log.txt"), "w", encoding="utf-8", newline="") as log_file:
            log_file.write(content)
        return temp_dir.name

    def test_app_log_only_contains_entries_of_the_latest_run(self):
        steam_dir = self._steam_dir(OLD_RUN + RUN_SEPARATOR + NEW_RUN)

        self.assertEqual(log.get_app_log(steam_dir, "440"), _lines(NEW_RUN))

    def test_state_log_only_contains_states_of_the_latest_run(self):
        steam_dir = self._steam_dir(OLD_RUN + RUN_SEPARATOR + NEW_RUN)

        self.assertEqual(log.get_app_state_log(steam_dir, "440"), ["Fully Installed,Update Queued", "Running"])
