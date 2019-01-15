"""Add, remove and configure runners"""
# pylint: disable=too-many-instance-attributes,attribute-defined-outside-init
import os

from gi.repository import Gtk, GObject
from lutris.util import datapath

from lutris import runners
from lutris import settings
from lutris.util.log import logger
from lutris.gui.util import open_uri
from lutris.gui.dialogs import ErrorDialog, GtkBuilderDialog, DownloadDialog
from lutris.gui.config.runner import RunnerConfigDialog
from lutris.gui.runnerinstalldialog import RunnerInstallDialog
from lutris.gui.widgets.utils import get_icon, ICON_SIZE, get_builder_from_file


def simple_downloader(url, destination, callback, callback_args=None):
    """Default downloader used for runners"""
    if not callback_args:
        callback_args = {}
    dialog = DownloadDialog(url, destination)
    dialog.run()
    return callback(**callback_args)


class RunnersDialog(GtkBuilderDialog):
    """Dialog to manage the runners."""
    glade_file = "runners-dialog.ui"
    dialog_object = "runners_dialog"
    runner_entry_ui = os.path.join(datapath.get(), "ui", 'runner-entry.ui')

    __gsignals__ = {
        "runner-installed": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "runner-removed": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def initialize(self, **kwargs):
        width = int(settings.read_setting("runners_manager_width") or 800)
        height = int(settings.read_setting("runners_manager_height") or 800)
        self.dialog_size = (width, height)
        self.dialog.resize(width, height)

        self.runner_listbox = self.builder.get_object('runners_listbox')
        self.runner_listbox.set_header_func(self._listbox_header_func)

        self.refresh_button = self.builder.get_object('refresh_button')

        self.runner_list = sorted(runners.__all__)
        # Run this after show_all, else all hidden buttons gets shown
        self.populate_runners()

    @staticmethod
    def _listbox_header_func(row, before):
        if not row.get_header() and before is not None:
            row.set_header(Gtk.Separator.new(Gtk.Orientation.HORIZONTAL))

    def get_runner_hbox(self, runner_name):
        # Get runner details
        runner = runners.import_runner(runner_name)()
        platform = ", ".join(sorted(list(set(runner.platforms))))

        builder = Gtk.Builder()
        builder.add_from_file(self.runner_entry_ui)
        hbox = builder.get_object('runner_entry')
        hbox.show()

        # Icon
        runner_icon = builder.get_object('runner_icon')
        runner_icon.set_from_pixbuf(get_icon(runner_name, format='pixbuf', size=ICON_SIZE))

        # Label
        runner_name = builder.get_object('runner_name')
        runner_name.set_text(runner.human_name)
        runner_description = builder.get_object('runner_description')
        runner_description.set_text(runner.description)
        runner_platform = builder.get_object('runner_platform')
        runner_platform.set_text(platform)
        runner_label = builder.get_object('runner_label')
        if not runner.is_installed():
            runner_label.set_sensitive(False)

        # Buttons
        self.versions_button = builder.get_object('manage_versions')
        self.versions_button.connect("clicked", self.on_versions_clicked, runner, runner_label)
        self.install_button = builder.get_object('install_runner')
        self.install_button.connect("clicked", self.on_install_clicked, runner, runner_label)
        self.remove_button = builder.get_object('remove_runner')
        self.remove_button.connect("clicked", self.on_remove_clicked, runner, runner_label)
        self.configure_button = builder.get_object('configure_runner')
        self.configure_button.connect("clicked", self.on_configure_clicked, runner, runner_label)
        self.set_button_display(runner)

        return hbox

    def populate_runners(self):
        for runner_name in self.runner_list:
            hbox = self.get_runner_hbox(runner_name)
            self.runner_listbox.add(hbox)

    def set_button_display(self, runner):
        if runner.multiple_versions:
            self.versions_button.show()
            self.install_button.hide()
            if runner.can_uninstall():
                self.remove_button.show()
            else:
                self.remove_button.hide()
        else:
            self.versions_button.hide()
            self.remove_button.hide()
            self.install_button.show()

        if runner.is_installed():
            self.install_button.hide()
            if runner.can_uninstall():
                self.remove_button.show()
            else:
                self.remove_button.hide()

        self.configure_button.show()

    def on_versions_clicked(self, widget, runner, runner_label):
        dlg_title = "Manage %s versions" % runner.name
        versions_dialog = RunnerInstallDialog(dlg_title, self.dialog, runner.name)
        versions_dialog.connect("destroy", self.set_install_state, runner, runner_label)

    def on_install_clicked(self, widget, runner, runner_label):
        """Install a runner."""
        if runner.depends_on:
            dependency = runner.depends_on()
            dependency.install(downloader=simple_downloader)
        try:
            runner.install(downloader=simple_downloader)
        except (
                runners.RunnerInstallationError,
                runners.NonInstallableRunnerError,
        ) as ex:
            ErrorDialog(ex.message, parent=self)
        if runner.is_installed():
            self.emit("runner-installed")
            self.refresh_button.emit("clicked")

    def on_configure_clicked(self, widget, runner, runner_label):
        config_dialog = RunnerConfigDialog(runner, parent=self.dialog)
        config_dialog.connect("destroy", self.set_install_state, runner, runner_label)

    def on_remove_clicked(self, widget, runner, runner_label):
        if not runner.is_installed():
            logger.warning("Runner %s is not installed", runner)
            return

        if runner.multiple_versions:
            logger.info("Removing multiple versions")
            builder = get_builder_from_file('runner-remove-all-versions-dialog.ui')
            builder.connect_signals(self)
            remove_confirm_button = builder.get_object('remove_confirm_button')
            remove_confirm_button.connect(
                "clicked",
                self.on_remove_all_clicked,
                runner,
                runner_label
            )
            all_versions_label = builder.get_object('runner_all_versions_label')
            all_versions_label.set_markup(all_versions_label.get_label() % runner.human_name)
            self.all_versions_dialog = builder.get_object('runner_remove_all_versions_dialog')
            self.all_versions_dialog.set_parent(self.dialog)
            self.all_versions_dialog.show()
        else:
            builder = get_builder_from_file('runner-remove-confirm-dialog.ui')
            builder.connect_signals(self)
            remove_confirm_button = builder.get_object('remove_confirm_button')
            remove_confirm_button.connect(
                "clicked",
                self.on_remove_confirm_clicked,
                runner,
                runner_label
            )
            runner_remove_label = builder.get_object('runner_remove_label')
            runner_remove_label.set_markup(runner_remove_label.get_label() % runner.human_name)
            self.remove_confirm_dialog = builder.get_object('runner_remove_confirm_dialog')
            self.remove_confirm_dialog.show()

    def on_remove_confirm_clicked(self, widget, runner, runner_label):
        runner.uninstall()
        self.refresh_button.emit("clicked")
        self.emit("runner-removed")
        self.remove_confirm_dialog.destroy()

    def on_remove_all_clicked(self, _widget, runner, _runner_label):
        runner.uninstall()
        self.refresh_button.emit("clicked")
        self.emit("runner-removed")
        self.all_versions_dialog.destroy()

    def on_cancel_confirm_clicked(self, _widget):
        self.remove_confirm_dialog.destroy()

    def on_cancel_all_clicked(self, _widget):
        self.all_versions_dialog.destroy()

    @staticmethod
    def on_folder_clicked(_widget):
        open_uri("file://" + settings.RUNNER_DIR)

    def on_refresh_clicked(self, _widget):
        for child in self.runner_listbox:
            child.destroy()
        self.populate_runners()

    def on_close_clicked(self, _widget):
        self.destroy()

    def set_install_state(self, _widget, runner, runner_label):
        if runner.is_installed():
            runner_label.set_sensitive(True)
            self.emit("runner-installed")
        else:
            runner_label.set_sensitive(False)

    def on_resize(self, _widget, *args):
        """Store the dialog's new size."""
        self.dialog_size = self.dialog.get_size()

    def on_destroy(self, _widget):
        # Save window size
        width, height = self.dialog_size
        settings.write_setting("runners_manager_width", width)
        settings.write_setting("runners_manager_height", height)
