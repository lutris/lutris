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
import sys
sys.path.append('/home/strider/Devel/lutris')

from lutris.config import LutrisConfig

class FtpDialog(gtk.Dialog):
    def __init__(self):
        gtk.Dialog.__init__(self)
        self.set_title("FTP Manager")
        self.set_size_request(600,500)
        self.connect("destroy", self.destroy_cb)
        self.main_hbox = gtk.HBox()
        self.vbox.pack_start(self.main_hbox)

        self.runner_list = gtk.Label("Runner list go here")
        self.main_hbox.pack_start(self.runner_list)
        
        self.ftp_vbox = gtk.VBox()
        self.ftp_vbox.pack_start(gtk.Label("Ftp"),False,False,5)

        destination_label = gtk.Label()
        destination_label.set_markup("<b>Destination</b>")
        self.ftp_vbox.pack_start(destination_label,False,False,5)

        label_width = 70
        label_height = 20

        #Server
        server_hbox = gtk.HBox()
        server_label = gtk.Label("Server")
        server_label.set_size_request(label_width,label_width)
        self.server_entry = gtk.Entry()
        server_hbox.pack_start(server_label)
        server_hbox.pack_start(self.server_entry)
        self.ftp_vbox.pack_start(server_hbox,False,False,2)

        #login
        login_hbox = gtk.HBox()
        login_label = gtk.Label("login")
        login_label.set_size_request(label_width,label_width)
        self.login_entry = gtk.Entry()
        login_hbox.pack_start(login_label)
        login_hbox.pack_start(self.login_entry)
        self.ftp_vbox.pack_start(login_hbox,False,False,2)

        #password
        password_hbox = gtk.HBox()
        password_label = gtk.Label("password")
        password_label.set_size_request(label_width,label_width)
        self.password_entry = gtk.Entry()
        password_hbox.pack_start(password_label)
        password_hbox.pack_start(self.password_entry)
        self.ftp_vbox.pack_start(password_hbox,False,False,2)
        
        #folder
        folder_hbox = gtk.HBox()
        folder_label = gtk.Label("folder")
        folder_label.set_size_request(label_width,label_width)
        self.folder_entry = gtk.Entry()
        folder_hbox.pack_start(folder_label)
        folder_hbox.pack_start(self.folder_entry)
        self.ftp_vbox.pack_start(folder_hbox,False,False,2)

        #Destination
        self.destination_entry = gtk.Entry()
        self.ftp_vbox.pack_start(self.destination_entry,False,False,5)

        self.main_hbox.pack_start(self.ftp_vbox,False,False,5)
        self.show_all()
        
        self.load_runner_config()

    def destroy_cb(self,widget):
        self.destroy()

    def load_runner_config(self,runner_name = "sdlmame"):
        lutris_config = LutrisConfig(runner=runner_name)
        self.destination_entry.set_text(lutris_config.config["system"]["game_path"])

if __name__ == "__main__":
    FtpDialog()
    gtk.main()
    