from unittest import TestCase
from unittest.mock import patch

from lutris.buildinfo import get_display_version


class TestBuildVersion(TestCase):
    @patch("lutris.buildinfo.get_checkout_commit", return_value="")
    def test_packaged_commit_is_shortened(self, _checkout):
        with patch("lutris.buildinfo.Path.read_text", return_value="ABCDEF1234567890\n"):
            self.assertEqual(get_display_version("0.5.23"), "0.5.23-abcdef1")

    @patch("lutris.buildinfo.get_checkout_commit", return_value="")
    def test_missing_metadata_preserves_version(self, _checkout):
        with patch("lutris.buildinfo.Path.read_text", side_effect=FileNotFoundError):
            self.assertEqual(get_display_version("0.5.23"), "0.5.23")

    @patch("lutris.buildinfo.get_checkout_commit", return_value="")
    def test_invalid_metadata_preserves_version(self, _checkout):
        with patch("lutris.buildinfo.Path.read_text", return_value="unknown revision"):
            self.assertEqual(get_display_version("0.5.23"), "0.5.23")

    def test_checkout_takes_precedence_over_packaged_revision(self):
        with (
            patch("lutris.buildinfo.get_checkout_commit", return_value="abcdef1" + "0" * 33),
            patch("lutris.buildinfo.Path.read_text") as read_metadata,
        ):
            self.assertEqual(get_display_version("0.5.23"), "0.5.23-abcdef1")
            read_metadata.assert_not_called()

    def test_git_failure_falls_back_to_packaged_revision(self):
        with (
            patch("lutris.buildinfo.Path.exists", return_value=True),
            patch("lutris.buildinfo.subprocess.check_output", side_effect=FileNotFoundError),
            patch("lutris.buildinfo.Path.read_text", return_value="1234567"),
        ):
            self.assertEqual(get_display_version("0.5.23"), "0.5.23-1234567")
