from unittest import TestCase
from unittest.mock import MagicMock, patch

from lutris.gui.dialogs.delegates import CommandLineUIDelegate
from lutris.gui.installerwindow import InstallerWindow
from lutris.util.test_config import setup_test_environment

setup_test_environment()


class TestInstallerWindowLaunch(TestCase):
    def launch_with(self, window, launch_ui_delegate):
        application = MagicMock(window=window, launch_ui_delegate=launch_ui_delegate)
        installer_window = MagicMock()
        with (
            patch("lutris.gui.installerwindow.Gio.Application.get_default", return_value=application),
            patch("lutris.gui.installerwindow.Game") as game_class,
        ):
            InstallerWindow.on_launch_clicked(installer_window, MagicMock())
        return game_class.return_value.launch.call_args.args[0]

    def test_launch_after_uri_install_uses_main_window(self):
        # After 'lutris lutris:install/...' or 'lutris -i', the application's
        # delegate never shows the launch config dialog.
        window = MagicMock()
        self.assertIs(self.launch_with(window, CommandLineUIDelegate(None)), window)

    def test_launch_config_named_on_command_line_is_kept(self):
        delegate = CommandLineUIDelegate("Second config")
        self.assertIs(self.launch_with(MagicMock(), delegate), delegate)

    def test_launch_without_main_window_uses_application_delegate(self):
        delegate = CommandLineUIDelegate(None)
        self.assertIs(self.launch_with(None, delegate), delegate)

    def test_launch_with_main_window_as_delegate(self):
        window = MagicMock()
        self.assertIs(self.launch_with(MagicMock(), window), window)
