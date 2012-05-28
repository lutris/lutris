# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-
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

"""About dialog"""

# pylint #37300 False positive F0401 on Gtk.gdk import
# pylint: disable=F0401
import os

from lutris import settings
from lutris.constants import LUTRIS_ICON


# pylint: disable=R0904, R0901
class AboutLutrisDialog(Gtk.AboutDialog):
    """About dialog class"""
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


def NewAboutLutrisDialog(data_path):
    """NewAboutLutrisDialog - returns a fully instantiated AboutLutrisDialog
    object.
    """

    #look for the ui file that describes the ui
    return dialog
