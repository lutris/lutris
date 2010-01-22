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

__author__="strider"
__date__ ="$28 nov. 2009 06:59:20$"


import gtk
import os

import lutris.constants
from lutris.config import LutrisConfig
from google_image import GoogleImage

class GoogleImageDialog(gtk.Dialog):
    def __init__(self,game):
        gtk.Dialog.__init__(self)
        self.game = game
        self.google_image = GoogleImage()
        self.set_title(game)
        self.set_size_request(800,260)

        self.thumbnails_scroll_window = gtk.ScrolledWindow()
        self.thumbnails_scroll_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.vbox.pack_start(self.thumbnails_scroll_window)
        self.thumbnails_table = gtk.Table(rows=2,columns=21,homogeneous=False)
        self.thumbnails_scroll_window.add_with_viewport(self.thumbnails_table)
        
        lutris_config = LutrisConfig(game=game)

        self.search_entry = gtk.Entry()
        self.search_entry.set_text(lutris_config["realname"]+" cover")
        
        search_button = gtk.Button("Search")
        cancel_button = gtk.Button(None, gtk.STOCK_CANCEL)
        add_button = gtk.Button(None, gtk.STOCK_ADD)
        self.action_area.pack_start(self.search_entry)
        self.action_area.pack_start(search_button)
        self.action_area.pack_start(cancel_button)
        self.action_area.pack_start(add_button)
        search_button.connect("clicked",self.search_images)
        cancel_button.connect("clicked", self.close)
        add_button.connect("clicked", self.add_cover)
        self.show_all()
        self.run()

        

    def close(self,widget=None):
        self.destroy()

    def add_cover(self,widget=None):
        self.destroy()

    def search_images(self,widget=None):
        thumbs_path = os.path.join(lutris.constants.lutris_config_path,"tmp")
        index = 0
        self.google_image.get_google_image_page(self.search_entry.get_text())
        self.google_image.scan_for_images(thumbs_path)
        for file in os.listdir(thumbs_path):
            image = gtk.Image()
            image.set_from_file(os.path.join(thumbs_path,str(index)+".jpg"))
            image_button = gtk.Button()
            image_button.set_image(image)
            image_button.show()
            image_button.connect("clicked",self.select_cover,str(index)+".jpg")
            print index
            image_info = gtk.Label(self.google_image.google_results[index]["size"])
            image_info.show()
            image.show()
            self.thumbnails_table.attach(image_button,index,index+1,0,1,xpadding = 3, ypadding = 3)
            self.thumbnails_table.attach(image_info,index,index+1,1,2,xpadding = 3, ypadding = 3)
            index = index + 1

    def select_cover(self,widget,file):
        print "grabbing %s" % file
        self.google_image.get_pic_at(int(file.split('.')[0]),os.path.join(lutris.constants.cover_path,self.game))
        self.destroy()
        

        
        

