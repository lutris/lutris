# -*- coding:Utf-8 -*-
import os
from gi.repository import Gtk, GObject, Gdk

import lutris.runners
from lutris.util import datapath
from lutris.runners import import_runner
from lutris.gui.config_dialogs import RunnerConfigDialog


class RunnersDialog(Gtk.Window):
    """Dialog for the runner preferences"""

    def __init__(self):
        GObject.GObject.__init__(self)
        self.set_title("Configure runners")
        self.set_size_request(700, 600)

        self.vbox = Gtk.VBox()
        self.vbox.set_margin_right(10)
        self.vbox.set_margin_left(10)
        self.vbox.set_margin_bottom(10)
        self.add(self.vbox)

        label = Gtk.Label()
        label.set_markup("<b>Install and configure the game runners</b>")

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                   Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_shadow_type(Gtk.ShadowType.ETCHED_OUT)
        self.vbox.pack_start(label, False, True, 15)
        self.vbox.pack_start(scrolled_window, True, True, 0)

        runner_list = lutris.runners.__all__
        runner_vbox = Gtk.VBox()

        inactive_color = Gdk.Color(35000, 35000, 35000)

        for runner_name in runner_list:
            # Get runner details
            runner = import_runner(runner_name)()
            platform = runner.platform
            description = runner.description

            hbox = Gtk.HBox()
            # Icon
            icon_path = os.path.join(datapath.get(), 'media/runner_icons',
                                     runner_name + '.png')
            icon = Gtk.Image()
            icon.set_from_file(icon_path)
            icon.set_alignment(0.5, 0.1)
            hbox.pack_start(icon, False, False, 10)

            # Label
            runner_label = Gtk.Label()
            if not runner.is_installed():
                runner_label.modify_fg(Gtk.StateType.NORMAL, inactive_color)
            runner_label.set_markup(
                "<b>%s</b>\n%s\n <i>Supported platforms : %s</i>" %
                (runner_name, description, platform)
            )
            runner_label.set_width_chars(40)
            runner_label.set_max_width_chars(40)
            runner_label.set_property('wrap', True)
            runner_label.set_line_wrap(True)
            runner_label.set_alignment(0.0, 0.1)
            runner_label.set_padding(5, 0)
            hbox.pack_start(runner_label, True, True, 5)
            # Button
            button = Gtk.Button()
            button.set_size_request(100, 30)
            button_align = Gtk.Alignment.new(1.0, 0.0, 0.0, 0.0)
            self.configure_button(button, runner)
            button_align.add(button)
            hbox.pack_start(button_align, False, False, 15)

            runner_vbox.pack_start(hbox, True, True, 5)
            separator = Gtk.Separator()
            runner_vbox.pack_start(separator, False, False, 5)
        scrolled_window.add_with_viewport(runner_vbox)
        self.show_all()

    def configure_button(self, widget, runner):
        try:
            widget.disconnect(widget.click_signal)
        except AttributeError:
            pass
        if runner.is_installed():
            self.setup_configure_button(widget, runner)
        else:
            self.setup_install_button(widget, runner)

    def setup_configure_button(self, widget, runner):
        widget.set_label('Configure')
        widget.set_size_request(100, 30)
        handler_id = widget.connect("clicked",
                                    self.on_configure_clicked,
                                    runner)
        widget.click_signal = handler_id

    def setup_install_button(self, widget, runner):
        widget.set_label('Install')
        handler_id = widget.connect("clicked", self.on_install_clicked, runner)
        widget.click_signal = handler_id

    def on_install_clicked(self, widget, runner):
        """Install a runner"""
        runner.install()
        self.configure_button(widget, runner)

    @staticmethod
    def on_configure_clicked(widget, runner):
        RunnerConfigDialog(runner)
