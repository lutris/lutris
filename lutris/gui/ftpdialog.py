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
import logging
#sys.path.append('/home/strider/Devel/lutris')

from lutris.config import LutrisConfig


class FtpDialog(gtk.Dialog):
    def __init__(self):
        gtk.Dialog.__init__(self)
        self.set_title("FTP Manager")
        self.connect("destroy", self.destroy_cb)
        self.main_hbox = gtk.HBox()
        self.vbox.pack_start(self.main_hbox)

        self.ftp_vbox = gtk.VBox()

        destination_label = self.label("FTP settings", bold=True)
        self.ftp_vbox.pack_start(destination_label, False, False, 5)

        #Server
        host_hbox = gtk.HBox()
        host_label = self.label("Server")
        self.host_entry = gtk.Entry()
        self.host_entry.connect("grab-focus", self.focus_entry)
        host_hbox.pack_start(host_label, False, False, 1)
        host_hbox.pack_start(self.host_entry, False, False, 1)
        self.ftp_vbox.pack_start(host_hbox, False, False, 2)

        #login
        login_hbox = gtk.HBox()
        login_label = self.label("Login")
        self.login_entry = gtk.Entry()
        self.login_entry.connect("grab-focus", self.focus_entry)
        login_hbox.pack_start(login_label, False, False, 1)
        login_hbox.pack_start(self.login_entry, False, False, 1)
        self.ftp_vbox.pack_start(login_hbox, False, False, 2)

        #password
        password_hbox = gtk.HBox()
        password_label = self.label("Password")

        self.password_entry = gtk.Entry()
        self.password_entry.set_visibility(False)
        password_hbox.pack_start(password_label, False, False, 1)
        password_hbox.pack_start(self.password_entry, False, False, 1)
        self.ftp_vbox.pack_start(password_hbox, False, False, 2)

        #folder
        folder_hbox = gtk.HBox()
        folder_label = self.label("Folder")
        self.folder_entry = gtk.Entry()
        folder_hbox.pack_start(folder_label, False, False, 1)
        folder_hbox.pack_start(self.folder_entry, False, False, 1)
        self.ftp_vbox.pack_start(folder_hbox, False, False, 2)

        #Runner list
        runner_hbox = gtk.HBox()
        runner_label = self.label("Runner")
        runner_hbox.pack_start(runner_label, False, False, 1)
        self.ftp_vbox.pack_start(runner_hbox, False, False, 2)

        #Destination
        self.destination_entry = gtk.Entry()
        self.ftp_vbox.pack_start(self.destination_entry, False, False, 2)

        #Connect button
        self.connect_button = gtk.Button("Connect")
        self.connect_button.connect("clicked", self.connect_ftp)
        self.ftp_vbox.pack_start(self.connect_button, False, False, 2)

        self.main_hbox.pack_start(self.ftp_vbox, False, False, 2)

        self.show_all()
        self.load_runner_config()

    def label(self, text, bold=False, x=70, y=20):
        label = gtk.Label()
        if bold:
            label.set_markup("<b>%s</b>" % text)
        else:
            label.set_markup("%s" % text)
        label.set_size_request(x, y)
        label.set_alignment(0, 0.5)
        label.set_padding(5, 5)
        return label

    def destroy_cb(self, widget):
        self.destroy()

    def focus_entry(self, widget, data=None):
        widget.modify_base(gtk.STATE_NORMAL, gtk.gdk.Color("#FFFFFF"))

    def connect_ftp(self, widget, data=None):
        validate_widgets = [self.host_entry, self.login_entry]
        valid = True
        for val_widget in validate_widgets:
            print val_widget
            if not val_widget.get_text():
                val_widget.modify_base(gtk.STATE_NORMAL,
                                       gtk.gdk.Color("#FF0000"))
                valid = False
        if valid == False:
            return False
        host = self.host_entry.get_text()
        if not host:
            pass
        else:
            logging.debug("Host : %s" % self.host_entry.get_text())
        self.host_entry.modify_base(gtk.STATE_NORMAL, gtk.gdk.Color("#FF0000"))

    def load_runner_config(self, runner_name="sdlmame"):
        lutris_config = LutrisConfig(runner=runner_name)
        game_path = lutris_config.config["system"]["game_path"]
        self.destination_entry.set_text(game_path)

if __name__ == "__main__":
    FtpDialog()
    gtk.main()
