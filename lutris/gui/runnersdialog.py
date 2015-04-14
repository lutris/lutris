# -*- coding:Utf-8 -*-
from gi.repository import Gtk, GObject

import lutris.runners
from lutris import settings
from lutris.gui.widgets import get_runner_icon
from lutris.util import system
from lutris.runners import import_runner
from lutris.gui.config_dialogs import RunnerConfigDialog
from lutris.gui.runnerinstalldialog import RunnerInstallDialog


class RunnersDialog(Gtk.Window):
    """Dialog for the runner preferences"""

    def __init__(self):
        GObject.GObject.__init__(self)
        self.set_title("Manage runners")
        self.set_size_request(750, 750)
        self.set_border_width(10)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.vbox = Gtk.VBox()
        self.add(self.vbox)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                   Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_shadow_type(Gtk.ShadowType.ETCHED_OUT)
        self.vbox.pack_start(scrolled_window, True, True, 0)
        self.show_all()

        runner_list = lutris.runners.__all__
        runner_vbox = Gtk.VBox()
        runner_vbox.show()

        self.runner_labels = {}
        for runner_name in runner_list:
            hbox = self.get_runner_hbox(runner_name)
            runner_vbox.pack_start(hbox, True, True, 5)
            separator = Gtk.Separator()
            runner_vbox.pack_start(separator, False, False, 5)
        scrolled_window.add_with_viewport(runner_vbox)

        buttons_box = Gtk.Box()
        buttons_box.show()
        open_runner_button = Gtk.Button("Open Runners Folder")
        open_runner_button.show()
        open_runner_button.connect('clicked', self.on_runner_open_clicked)
        buttons_box.add(open_runner_button)

        self.vbox.pack_start(buttons_box, False, False, 5)

    def get_runner_hbox(self, runner_name):
        # Get runner details
        runner = import_runner(runner_name)()
        platform = runner.platform
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
                                     runner)
        hbox.pack_start(self.versions_button, False, False, 5)

        self.install_button = Gtk.Button("Install")
        self.install_button.set_size_request(80, 30)
        self.install_button.set_valign(Gtk.Align.CENTER)
        self.install_button.connect("clicked", self.on_install_clicked, runner)
        hbox.pack_start(self.install_button, False, False, 5)

        self.configure_button = Gtk.Button("Configure")
        self.configure_button.set_size_request(90, 30)
        self.configure_button.set_valign(Gtk.Align.CENTER)
        self.configure_button.connect("clicked", self.on_configure_clicked,
                                      runner)
        hbox.pack_start(self.configure_button, False, False, 5)

        self.set_button_display(runner)

        return hbox

    def set_button_display(self, runner):
        if runner.multiple_versions:
            self.versions_button.show()
            self.install_button.hide()
        else:
            self.versions_button.hide()
            self.install_button.show()

        if runner.is_installed():
            self.install_button.hide()

        self.configure_button.show()

    def on_versions_clicked(self, widget, runner):
        dlg_title = "Manage %s versions" % runner.name
        RunnerInstallDialog(dlg_title, self, runner.name)
        self.set_button_display(runner)

    def on_install_clicked(self, widget, runner):
        """Install a runner"""
        runner.install()
        self.set_button_display(runner)

    @staticmethod
    def on_configure_clicked(widget, runner):
        RunnerConfigDialog(runner)

    def on_runner_open_clicked(self, widget):
        system.xdg_open(settings.RUNNER_DIR)
