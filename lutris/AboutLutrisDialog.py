# -*- coding: utf-8 -*-
### BEGIN LICENSE
# This file is in the public domain
### END LICENSE

import sys
import os
import gtk

from lutris.lutrisconfig import getdatapath

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

def NewAboutLutrisDialog():
    """NewAboutLutrisDialog - returns a fully instantiated
    AboutLutrisDialog object. Use this function rather than
    creating a AboutLutrisDialog instance directly.
    
    """

    #look for the ui file that describes the ui
    ui_filename = os.path.join(getdatapath(), 'ui', 'AboutLutrisDialog.ui')
    if not os.path.exists(ui_filename):
        ui_filename = None

    builder = gtk.Builder()
    builder.add_from_file(ui_filename)    
    dialog = builder.get_object("about_lutris_dialog")
    dialog.finish_initializing(builder)
    return dialog

if __name__ == "__main__":
    dialog = NewAboutLutrisDialog()
    dialog.show()
    gtk.main()

