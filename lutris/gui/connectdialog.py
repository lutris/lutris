#!/usr/bin/python
# -*- coding:Utf-8 -*-
###############################################################################
## Lutris
##
## Copyright (C) 2011 Mathieu Comandon strider@strycore.com
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

from gi.repository import Gtk
#from lutris.platform import Connect

class Connect(object):
    def __init__(self, username, password):
        print "connecting %s" % username

class ConnectDialog(Gtk.Window):
    def __init__(self, parent=None):
        Gtk.Window.__init__(self, title="Connect to lutris.net")
        self.set_border_width(25)
        self.connect("delete-event", Gtk.main_quit) # FIXME
        
        logo_box = Gtk.Box()
        # TODO  Add Lutris Logo and descriptive text
        
        # Username field
        username_box = Gtk.Box()
        username_label = Gtk.Label(label="Username :", halign=Gtk.Align.START)
        username_box.pack_start(child=username_label, 
                                expand=True, 
                                fill=True,
                                padding=5)
        self.username_entry = Gtk.Entry()
        self.username_entry.connect('key-release-event', self.on_text_typed)
        username_box.pack_start(child=self.username_entry,
                                expand=True,
                                fill=True,
                                padding=5)
        
        # Password field
        password_box = Gtk.Box()
        password_label = Gtk.Label(label="Password :", halign=Gtk.Align.START)
        password_box.pack_start(child=password_label,
                                expand=True,
                                fill=True,
                                padding=5)

        self.password_entry = Gtk.Entry()
        self.password_entry.set_visibility(False)
        self.password_entry.connect('key-release-event', self.on_text_typed)
        password_box.pack_start(child=self.password_entry,
                                expand=True,
                                fill=True,
                                padding=5)

        
        connect_box = Gtk.Box()
        autoconnect_checkbutton = Gtk.CheckButton("Autoconnect at startup")
        autoconnect_checkbutton.connect('toggled', self.on_autoconnect_toggled)
        connect_box.pack_start(child=autoconnect_checkbutton,
                               expand=True, fill=True, padding=5)
        self.connect_button = Gtk.Button(label="Connect")
        self.connect_button.set_sensitive(False)
        self.connect_button.connect("clicked", self.on_connect_clicked)
        connect_box.pack_start(child=self.connect_button,
                               expand=False,
                               fill=False,
                               padding=5)

        account_box = Gtk.Box()
        create_account_link = Gtk.LinkButton("http://lutris.net/accounts/create", "Create an account")
        forgot_password_link = Gtk.LinkButton("http://lutris.net/accounts/password-retrieve", "Forgot your password?")
        account_box.pack_start(child=create_account_link, expand=False, 
                               fill=False, padding=5)
        account_box.pack_start(child=forgot_password_link, expand=False, 
                               fill=False, padding=5)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_box.pack_start(child=logo_box,
                            expand=True,
                            fill=True,
                            padding=10)
        main_box.pack_start(child=username_box,
                            expand=True,
                            fill=True,
                            padding=10)
        main_box.pack_start(child=password_box,
                            expand=True,
                            fill=True,
                            padding=10)
        main_box.pack_start(child=connect_box,
                            expand=False,
                            fill=False,
                            padding=5)
        main_box.pack_start(child=account_box,
                            expand=False,
                            fill=False,
                            padding=5)
        self.add(main_box)
        self.show_all()
    
    def on_text_typed(self, widget, string):
        # TODO : check if username and password had been entered,
        #        if true , set sensitive connect button
        if self.username_entry.get_text() and self.password_entry.get_text() != "":
            self.connect_button.set_sensitive(True)
        else:
            self.connect_button.set_sensitive(False)
    
    def on_autoconnect_toggled(self, checkbutton):
        # TODO : Write value to preferences
        if checkbutton.get_active():
            autoconnect = "true"
        else:
            autoconnect = "false"

        print "Set autoconnect to %s" % autoconnect
    
    def on_connect_clicked(self, widget):
        username = self.username_entry.get_text()
        password = self.password_entry.get_text()
        Connect(username, password)
        # connect user to Lutris.net

if __name__ == "__main__":
    c = ConnectDialog()
    Gtk.main()
