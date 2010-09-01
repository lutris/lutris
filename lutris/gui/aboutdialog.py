# -*- coding: utf-8 -*-
### BEGIN LICENSE
# Copyright (C) 2010 Mathieu Comandon <strycore@gmail.com>
# This program is free software: you can redistribute it and/or modify it 
# under the terms of the GNU General Public License version 3, as published 
# by the Free Software Foundation.
# 
# This program is distributed in the hope that it will be useful, but 
# WITHOUT ANY WARRANTY; without even the implied warranties of 
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR 
# PURPOSE.  See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along 
# with this program.  If not, see <http://www.gnu.org/licenses/>.
### END LICENSE

import os
import gtk
import gtk.gdk

import lutris.constants 

class AboutLutrisDialog(gtk.AboutDialog):
    __gtype_name__ = "AboutLutrisDialog"

    def __init__(self):
        """__init__ - This function is typically not called directly.
        Creation of a AboutLutrisDialog requires redeading the associated ui
        file and parsing the ui definition extrenally, 
        and then calling AboutLutrisDialog.finish_initializing().
    
        Use the convenience function NewAboutLutrisDialog to create 
        NewAboutLutrisDialog objects.
    
        """
        pass

    def finish_initializing(self, builder):
        """finish_initalizing should be called after parsing the ui definition
        and creating a AboutLutrisDialog object with it in order to finish
        initializing the start of the new AboutLutrisDialog instance.
    
        """
        #get a reference to the builder and set up the signals
        self.builder = builder
        self.builder.connect_signals(self)

        #code for other initialization actions should be added here
        self.set_position(gtk.WIN_POS_CENTER)
        self.set_icon_from_file(lutris.constants.lutris_icon_path)
        self.set_logo(gtk.gdk.pixbuf_new_from_file(lutris.constants.lutris_icon_path))
        self.set_name(lutris.constants.name)
        self.set_version(lutris.constants.version)
        self.set_copyright(lutris.constants.copyright)
        self.set_license(lutris.constants.license)
        self.set_authors(lutris.constants.authors)
        self.set_artists(lutris.constants.artists)
        self.set_website(lutris.constants.website)
        
def NewAboutLutrisDialog(data_path):
    """NewAboutLutrisDialog - returns a fully instantiated
    AboutLutrisDialog object. Use this function rather than
    creating a AboutLutrisDialog instance directly.
    
    """

    #look for the ui file that describes the ui
    ui_filename = os.path.join(data_path, 'ui', 'AboutLutrisDialog.ui')
    if not os.path.exists(ui_filename):
        ui_filename = None

    builder = gtk.Builder()
    builder.add_from_file(ui_filename)
    dialog = builder.get_object("about_lutris_dialog")
    dialog.finish_initializing(builder)
    return dialog

