# -*- coding:Utf-8 -*-
###############################################################################
## Lutris
##
## Copyright (C) 2009 Mathieu Comandon strycore@gmail.com
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
###############################################################################

import gtk
import os
from os.path import join, abspath

import lutris.runners
from lutris.runners import  import_runner
from lutris.config import LutrisConfig
from lutris.gui.runnerconfigvbox import RunnerConfigVBox
from lutris.gui.systemconfigvbox import SystemConfigVBox


class RunnerConfigDialog(gtk.Dialog):
    """ """
    def __init__(self, runner):
        gtk.Dialog.__init__(self)
        self.set_title("Configure %s" % (runner))
        self.set_size_request(570, 500)
        self.runner = runner
        self.lutris_config = LutrisConfig(runner=runner)

        #Notebook for choosing between runner and system configuration
        self.config_notebook = gtk.Notebook()
        self.vbox.pack_start(self.config_notebook, True, True, 0)

        #Runner configuration
        self.runner_config_vbox = RunnerConfigVBox(self.lutris_config,
                                                   "runner")
        runner_scrollwindow = gtk.ScrolledWindow()
        runner_scrollwindow.set_policy(gtk.POLICY_AUTOMATIC,
                                                 gtk.POLICY_AUTOMATIC)
        runner_scrollwindow.add_with_viewport(self.runner_config_vbox)
        self.config_notebook.append_page(runner_scrollwindow,
                                         gtk.Label("Runner configuration"))

        #System configuration
        self.system_config_vbox = SystemConfigVBox(self.lutris_config,
                                                   "runner")
        system_scrollwindow = gtk.ScrolledWindow()
        system_scrollwindow.set_policy(gtk.POLICY_AUTOMATIC,
                                                 gtk.POLICY_AUTOMATIC)
        system_scrollwindow.add_with_viewport(self.system_config_vbox)
        self.config_notebook.append_page(system_scrollwindow,
                                         gtk.Label("System configuration"))

        #Action buttons
        cancel_button = gtk.Button(None, gtk.STOCK_CANCEL)
        ok_button = gtk.Button(None, gtk.STOCK_OK)
        self.action_area.pack_start(cancel_button)
        self.action_area.pack_start(ok_button)
        cancel_button.connect("clicked", self.close)
        ok_button.connect("clicked", self.ok_clicked)

        self.show_all()
        self.run()

    def close(self, widget):
        self.destroy()

    def ok_clicked(self, wigdet):
        self.system_config_vbox.lutris_config.config_type = "runner"
        self.system_config_vbox.lutris_config.save()
        self.destroy()


class RunnersDialog(gtk.Dialog):
    """Dialog for the runner preferences"""

    def __init__(self):
        gtk.Dialog.__init__(self)
        self.set_title("Configure runners")
        self.set_size_request(570, 400)

        label = gtk.Label()
        label.set_markup("""
        <b>Install and configure the game runners</b>
        """)

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.vbox.pack_start(label, False, True, 20)
        self.vbox.pack_start(scrolled_window, True, True)

        runner_list = lutris.runners.__all__
        runner_vbox = gtk.VBox()

        for runner in runner_list:
            # Get runner details
            runner_class = import_runner(runner)
            runner_instance = runner_class()
            machine = runner_instance.machine
            description = runner_instance.description

            hbox = gtk.HBox()
            #Icon
            icon_path = os.path.join(lutris.constants.DATA_PATH,
                                     'media/runner_icons',
                                     runner + '.png')
            icon = gtk.Image()
            icon.set_from_file(icon_path)
            hbox.pack_start(icon, False, False, 10)

            #Label
            runner_label = gtk.Label()
            runner_label.set_markup(
                "<b>%s</b>\n%s\n <i>Supported platforms : %s</i>" %
                (runner, description, machine)
            )
            runner_label.set_width_chars(38)
            runner_label.set_line_wrap(True)
            runner_label.set_alignment(0.0, 0.0)
            runner_label.set_padding(25, 5)
            hbox.pack_start(runner_label, True, True)
            #Button
            button = gtk.Button("Configure")
            button.set_size_request(100, 30)
            button_align = gtk.Alignment(0.0, 1.0, 0.0, 0.0)
            if runner_instance.is_installed():
                button.set_label('Configure')
                button.set_size_request(100, 30)
                button.connect("clicked", self.on_configure_clicked, runner)
            else:
                button.set_label('Install')
                button.connect("clicked", self.on_install_clicked, runner)
            button_align.add(button)
            hbox.pack_start(button_align, True, False)

            runner_vbox.pack_start(hbox, True, True, 5)
        scrolled_window.add_with_viewport(runner_vbox)
        self.show_all()

    def close(self, widget=None, other=None):
        self.destroy()

    def on_install_clicked(self, widget, runner_classname):
        """Install a runner"""
        runner_class = import_runner(runner_classname)
        runner = runner_class()
        runner.install()

    def on_configure_clicked(self, widget, runner):
        RunnerConfigDialog(runner)
