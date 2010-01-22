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

import gtk, gobject
import os, threading
import logging
import lutris.constants
from lutris.config import LutrisConfig
from google_image import GoogleImage

class GoogleImageDialog(gtk.Dialog):
    def __init__(self,game):
        self.game = game
        lutris_config = LutrisConfig(game=game)

        gtk.Dialog.__init__(self)
        self.set_title(game)
        self.set_size_request(800,260)
        
        self.thumbnails_scroll_window = gtk.ScrolledWindow()
        self.thumbnails_scroll_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.vbox.pack_start(self.thumbnails_scroll_window)

        self.progress_bar = None
        self.thumbnails_table = None

        #Search Field
        self.search_entry = gtk.Entry()
        self.search_entry.set_text(lutris_config["realname"]+" cover")
        self.search_entry.set_size_request(250,30)
        self.action_area.pack_start(self.search_entry)
        #Search
        search_button = gtk.Button("Search")
        search_button.connect("clicked",self.search_images)
        self.action_area.pack_start(search_button)
        #Cancel
        cancel_button = gtk.Button(None, gtk.STOCK_CANCEL)
        cancel_button.connect("clicked", self.close)
        self.action_area.pack_start(cancel_button)
        
        self.show_all()

    def close(self,widget=None):
        self.destroy()

    def search_images(self,widget=None):
        try:
            self.thumbnails_table.destroy()
        except AttributeError:
            pass
        finally:
            self.thumbnails_table = None
        self.progress_bar = gtk.ProgressBar()
        self.progress_bar.set_text("Getting Images ...")
        self.progress_bar.show()
        self.thumbnails_scroll_window.add_with_viewport(self.progress_bar)
        
        self.google_image = GoogleImage()
        self.thumbs_path = lutris.constants.tmp_path
        self.google_image.get_google_image_page(self.search_entry.get_text())
        google_fetcher = GoogleFetcher(self.google_image,self.thumbs_path)
        timer_id = gobject.timeout_add(25, self.refresh_status)
        google_fetcher.start()

    def show_images(self):
        self.progress_bar.destroy()
        self.progress_bar=None
        
        self.thumbnails_table = gtk.Table(rows=2,columns=20,homogeneous=False)
        self.thumbnails_table.show()
        self.thumbnails_scroll_window.add_with_viewport(self.thumbnails_table)
        index = 0
        for i in range(0,20):
            image = gtk.Image()
            image.set_from_file(os.path.join(self.thumbs_path,str(index)+".jpg"))
            image_button = gtk.Button()
            image_button.set_image(image)
            image_button.show()
            image_button.connect("clicked",self.select_cover,str(index)+".jpg")
            image_info = gtk.Label(self.google_image.google_results[index]["size"])
            image_info.show()
            image.show()
            self.thumbnails_table.attach(image_button,index,index+1,0,1,xpadding = 3, ypadding = 3)
            self.thumbnails_table.attach(image_info,index,index+1,1,2,xpadding = 3, ypadding = 3)
            index = index + 1
            
    def refresh_status(self):
        fraction = self.google_image.fetch_count / 20.0
        self.progress_bar.set_fraction(fraction)
        if self.google_image.fetch_count < 20:
            return True
        else:
            self.show_images()
            return False

    def select_cover(self,widget,file):
        logging.debug("grabbing %s" % file)
        self.google_image.get_pic_at(int(file.split('.')[0]),os.path.join(lutris.constants.cover_path,self.game))
        self.destroy()
        
class GoogleFetcher(threading.Thread):
    def __init__(self,google_image,thumbs_path):
        threading.Thread.__init__(self) 
        self.google_image = google_image
        self.thumbs_path = thumbs_path
    def run(self):
        self.google_image.scan_for_images(self.thumbs_path)
        
if __name__ == "__main__":
    google_img_dlg = GoogleImageDialog()

