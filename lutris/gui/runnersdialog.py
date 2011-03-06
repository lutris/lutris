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

from lutris.runners import  import_runner
from lutris.config import LutrisConfig
from lutris.gui.runnerconfigvbox import RunnerConfigVBox
from lutris.gui.systemconfigvbox import SystemConfigVBox

class RunnerConfigDialog(gtk.Dialog):
    """ """
    def __init__(self,runner):
        gtk.Dialog.__init__(self)
        self.set_title("Configure %s" % (runner))
        self.set_size_request(500,500)
        self.runner = runner
        self.lutris_config = LutrisConfig(runner=runner)

        #Notebook for choosing between runner and system configuration
        self.config_notebook = gtk.Notebook()
        self.vbox.pack_start(self.config_notebook, True, True, 0)

        #Runner configuration
        self.runner_config_vbox = RunnerConfigVBox(self.lutris_config,"runner")
        runner_config_scrolled_window = gtk.ScrolledWindow()
        runner_config_scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        runner_config_scrolled_window.add_with_viewport(self.runner_config_vbox)
        self.config_notebook.append_page(runner_config_scrolled_window,gtk.Label("Runner configuration"))

        #System configuration
        self.system_config_vbox = SystemConfigVBox(self.lutris_config,"runner")
        system_config_scrolled_window = gtk.ScrolledWindow()
        system_config_scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,gtk.POLICY_AUTOMATIC)
        system_config_scrolled_window.add_with_viewport(self.system_config_vbox)
        self.config_notebook.append_page(system_config_scrolled_window,gtk.Label("System configuration"))

        #Action buttons
        cancel_button = gtk.Button(None, gtk.STOCK_CANCEL)
        ok_button = gtk.Button(None, gtk.STOCK_OK)
        self.action_area.pack_start(cancel_button)
        self.action_area.pack_start(ok_button)
        cancel_button.connect("clicked", self.close)
        ok_button.connect("clicked", self.ok_clicked)

        self.show_all()
        self.run()

    def close(self,widget):
        self.destroy()

    def ok_clicked(self,wigdet):
        self.system_config_vbox.lutris_config.config_type = "runner"
        self.system_config_vbox.lutris_config.save()
        self.destroy()

class RunnersDialog(gtk.Dialog):
    """Dialog for the runner preferences"""

    def __init__(self):
        gtk.Dialog.__init__(self)
        self.set_title("Configure runners")
        self.set_size_request(450,400)

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.vbox.pack_start(scrolled_window,True,True,0)

        runner_list = lutris.runners.__all__
        runner_vbox = gtk.VBox()

        for runner in runner_list:
            hbox = gtk.HBox()
            #Label
            runner_class = import_runner(runner)
            runner_instance = runner_class()
            machine = runner_instance.machine
            runner_label = gtk.Label()
            runner_label.set_markup("<b>"+runner + "</b> ( " + machine + " ) ")
            runner_label.set_width_chars(33)
            runner_label.set_line_wrap(True)
            hbox.pack_start(runner_label, True, True, 5)
            #Button
            button_alignement = gtk.Alignment(
                    xalign=0.0, yalign=0.0,
                    xscale=0.5, yscale=0.0
                )
            if runner_instance.is_installed():
                button = gtk.Button("Configure")
                button.set_size_request(100,30)
                button.connect("clicked",self.on_configure_clicked,runner)
            else:
                button = gtk.Button("Install")
                button.set_size_request(100,30)
                button.connect("clicked",self.on_install_clicked,runner)
            button_alignement.add(button)
            hbox.pack_start(button_alignement,True,True)

            runner_vbox.pack_start(hbox,True,True,5)
        scrolled_window.add_with_viewport(runner_vbox)
        self.show_all()

    def close(self, widget=None, other=None):
        self.destroy()

    def on_install_clicked(self,widget,runner_classname):
        """Install a runner"""
        #FIXME : this is ugly !
        runner_class = import_runner(runner_classname)
        runner = runner_classname()
        runner.install()

    def on_configure_clicked(self,widget,runner):
        RunnerConfigDialog(runner)

if __name__ == "__main__":
    dialog = RunnersDialog()
    gtk.main()
