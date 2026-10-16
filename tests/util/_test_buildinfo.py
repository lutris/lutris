import os
from unittest import TestCase
from unittest.mock import patch

from lutris.buildinfo import get_display_version


class TestBuildVersion(TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.checkout = patch("lutris.buildinfo.Path.exists", return_value=False)
        self.checkout.start()
        self.addCleanup(self.checkout.stop)

    def test_packaged_commit_is_shortened(self):
        with patch("lutris.buildinfo.Path.read_text", return_value="ABCDEF1234567890\n"):
            self.assertEqual(get_display_version("0.5.23"), "0.5.23-abcdef1")

    def test_missing_metadata_preserves_version(self):
        with patch("lutris.buildinfo.Path.read_text", side_effect=FileNotFoundError):
            self.assertEqual(get_display_version("0.5.23"), "0.5.23")

    def test_invalid_metadata_preserves_version(self):
        with patch("lutris.buildinfo.Path.read_text", return_value="unknown revision"):
            self.assertEqual(get_display_version("0.5.23"), "0.5.23")

    def test_checkout_takes_precedence_over_packaged_revision(self):
        with (
            patch("lutris.buildinfo.Path.exists", return_value=True),
            patch("lutris.buildinfo.subprocess.check_output", return_value="abcdef1" + "0" * 33),
            patch("lutris.buildinfo.Path.read_text", return_value="1234567"),
        ):
            self.assertEqual(get_display_version("0.5.23"), "0.5.23-abcdef1")

    def test_git_failure_falls_back_to_packaged_revision(self):
        with (
            patch("lutris.buildinfo.Path.exists", return_value=True),
            patch("lutris.buildinfo.subprocess.check_output", side_effect=FileNotFoundError),
            patch("lutris.buildinfo.Path.read_text", return_value="1234567"),
        ):
            self.assertEqual(get_display_version("0.5.23"), "0.5.23-1234567")

    def test_build_environment_survives_missing_git_and_metadata(self):
        with (
            patch.dict(os.environ, {"LUTRIS_BUILD_COMMIT": "ABCDEF1234"}),
            patch("lutris.buildinfo.Path.read_text", side_effect=FileNotFoundError),
            patch("lutris.buildinfo.subprocess.check_output") as git,
        ):
            self.assertEqual(get_display_version("0.5.23"), "0.5.23-abcdef1")
            git.assert_not_called()
