# -*- coding:Utf-8 -*-
import os

from gi.repository import Gtk, GObject, Gdk

from lutris import runners
from lutris import settings
from lutris.util.system import open_uri
from lutris.gui.widgets.utils import get_runner_icon
from lutris.gui.dialogs import ErrorDialog
from lutris.gui.config_dialogs import RunnerConfigDialog
from lutris.gui.runnerinstalldialog import RunnerInstallDialog


class RunnersDialog(Gtk.Window):
    """Dialog to manage the runners."""
    __gsignals__ = {
        "runner-installed": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self):
        GObject.GObject.__init__(self)

        self.runner_labels = {}

        self.set_title("Manage runners")
        width = int(settings.read_setting('runners_manager_width') or 700)
        height = int(settings.read_setting('runners_manager_height') or 500)
        self.dialog_size = (width, height)
        self.set_default_size(width, height)
        self.set_border_width(10)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.vbox = Gtk.VBox()
        self.add(self.vbox)

        # Scrolled window
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER,
                                   Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_shadow_type(Gtk.ShadowType.ETCHED_OUT)
        self.vbox.pack_start(scrolled_window, True, True, 0)
        self.show_all()

        # Runner list
        self.runner_list = sorted(runners.__all__)
        self.runner_listbox = Gtk.ListBox(visible=True, selection_mode=Gtk.SelectionMode.NONE)
        self.runner_listbox.set_header_func(self._listbox_header_func)

        self.populate_runners()

        scrolled_window.add(self.runner_listbox)

        # Bottom bar
        buttons_box = Gtk.Box()
        buttons_box.show()
        open_runner_button = Gtk.Button("Open Runners Folder")
        open_runner_button.show()
        open_runner_button.connect('clicked', self.on_runner_open_clicked)
        buttons_box.pack_start(open_runner_button, False, False, 0)

        self.refresh_button = Gtk.Button("Refresh")
        self.refresh_button.show()
        self.refresh_button.connect('clicked', self.on_refresh_clicked)
        buttons_box.pack_start(self.refresh_button, False, False, 10)

        close_button = Gtk.Button("Close")
        close_button.show()
        close_button.connect('clicked', self.on_close_clicked)
        buttons_box.pack_start(close_button, False, False, 0)

        # Signals
        self.connect('destroy', self.on_destroy)
        self.connect('configure-event', self.on_resize)

        self.vbox.pack_start(buttons_box, False, False, 5)

    @staticmethod
    def _listbox_header_func(row, before):
        if not row.get_header() and before is not None:
            row.set_header(Gtk.Separator.new(Gtk.Orientation.HORIZONTAL))

    def get_runner_hbox(self, runner_name):
        # Get runner details
        runner = runners.import_runner(runner_name)()
        platform = ', '.join(sorted(list(set(runner.platforms))))
        description = runner.description

        hbox = Gtk.HBox()
        hbox.show()
        # Icon
        icon = get_runner_icon(runner_name)
        icon.show()
        icon.set_alignment(0.5, 0.1)
        hbox.pack_start(icon, False, False, 10)

        # Label
        runner_label = Gtk.Label()
        runner_label.show()
        if not runner.is_installed():
            runner_label.set_sensitive(False)
        runner_label.set_markup(
            "<b>%s</b>\n%s\n <i>Supported platforms : %s</i>" %
            (runner.human_name, description, platform)
        )
        runner_label.set_width_chars(40)
        runner_label.set_max_width_chars(40)
        runner_label.set_property('wrap', True)
        runner_label.set_line_wrap(True)
        runner_label.set_alignment(0.0, 0.1)
        runner_label.set_padding(5, 0)
        self.runner_labels[runner] = runner_label
        hbox.pack_start(runner_label, True, True, 5)

        # Buttons
        self.versions_button = Gtk.Button("Manage versions")
        self.versions_button.set_size_request(120, 30)
        self.versions_button.set_valign(Gtk.Align.CENTER)
        self.versions_button.connect("clicked", self.on_versions_clicked,
                                     runner, runner_label)
        hbox.pack_start(self.versions_button, False, False, 5)

        self.install_button = Gtk.Button("Install")
        self.install_button.set_size_request(80, 30)
        self.install_button.set_valign(Gtk.Align.CENTER)
        self.install_button.connect("clicked", self.on_install_clicked, runner,
                                    runner_label)
        hbox.pack_start(self.install_button, False, False, 5)

        self.remove_button = Gtk.Button("Remove")
        self.remove_button.set_size_request(90, 30)
        self.remove_button.set_valign(Gtk.Align.CENTER)
        self.remove_button.connect("clicked", self.on_remove_clicked, runner, runner_label)
        hbox.pack_start(self.remove_button, False, False, 5)

        self.configure_button = Gtk.Button("Configure")
        self.configure_button.set_size_request(90, 30)
        self.configure_button.set_valign(Gtk.Align.CENTER)
        self.configure_button.connect("clicked", self.on_configure_clicked,
                                      runner, runner_label)
        hbox.pack_start(self.configure_button, False, False, 5)

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
        versions_dialog = RunnerInstallDialog(dlg_title, self, runner.name)
        versions_dialog.connect('destroy', self.set_install_state,
                                runner, runner_label)

    def on_install_clicked(self, widget, runner, runner_label):
        """Install a runner."""
        if runner.depends_on is not None:
            dependency = runner.depends_on()
            dependency.install()
        try:
            runner.install()
        except (runners.RunnerInstallationError,
                runners.NonInstallableRunnerError) as ex:
            ErrorDialog(ex.message, parent=self)
        if runner.is_installed():
            self.emit('runner-installed')
            self.refresh_button.emit('clicked')

    def on_configure_clicked(self, widget, runner, runner_label):
        config_dialog = RunnerConfigDialog(runner, parent=self)
        config_dialog.connect('destroy', self.set_install_state,
                              runner, runner_label)

    def on_remove_clicked(self, widget, runner, runner_label):
        if runner.is_installed():
            runner.uninstall()
            self.refresh_button.emit('clicked')

    def on_runner_open_clicked(self, widget):
        open_uri('file://' + settings.RUNNER_DIR)

    def on_refresh_clicked(self, widget):
        for child in self.runner_listbox:
            child.destroy()
        self.populate_runners()

    def on_close_clicked(self, widget):
        self.destroy()

    def set_install_state(self, widget, runner, runner_label):
        if runner.is_installed():
            runner_label.set_sensitive(True)
            self.emit('runner-installed')
        else:
            runner_label.set_sensitive(False)

    def on_resize(self, widget, *args):
        """Store the dialog's new size."""
        self.dialog_size = self.get_size()

    def on_destroy(self, widget):
        # Save window size
        width, height = self.dialog_size
        settings.write_setting('runners_manager_width', width)
        settings.write_setting('runners_manager_height', height)
