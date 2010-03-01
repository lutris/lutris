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
from lutris.config import LutrisConfig
from lutris.runner_config_vbox import RunnerConfigVBox
from lutris.system_config_vbox import SystemConfigVBox

class RunnerConfigDialog(gtk.Dialog):
    def __init__(self,runner):
        gtk.Dialog.__init__(self)
        self.set_title("Configure %s" % (runner))
        self.set_size_request(500,500)
        self.runner = runner
        self.lutris_config = LutrisConfig(runner = runner)

        #Notebook for choosing between runner and system configuration        
        self.config_notebook = gtk.Notebook()
        self.vbox.pack_start(self.config_notebook,True,True,0)
        
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
