from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock

from lutris.gui.installerwindow import InstallerWindow


class TestInstallerProgressPage(TestCase):
    def window(self, page):
        window = SimpleNamespace(stack=MagicMock(), status_label=MagicMock(), load_spinner_page=MagicMock())
        window.stack.get_visible_child_name.return_value = page
        window.status_label.get_text.return_value = "Extracting YUNO.7z"
        for name in (
            "install_spinner",
            "install_progress_status",
            "install_progress_text",
            "install_progress_bar",
        ):
            setattr(window, name, MagicMock())
        return window

    def test_extraction_after_runner_log_reveals_progress_page(self):
        window = self.window("log")
        InstallerWindow._set_progress(window, 0.22, "22 %")
        window.load_spinner_page.assert_called_once_with("Extracting YUNO.7z")
        window.install_progress_bar.set_fraction.assert_called_once_with(0.22)
        window.install_progress_bar.show.assert_called_once()

    def test_progress_updates_do_not_recreate_visible_page(self):
        window = self.window("spinner")
        InstallerWindow._set_progress(window, 0.4, "40 %")
        window.load_spinner_page.assert_not_called()

    def test_reset_does_not_replace_following_command_page(self):
        window = self.window("log")
        InstallerWindow._set_progress(window, None, "")
        window.load_spinner_page.assert_not_called()
        window.install_progress_bar.hide.assert_called_once()
