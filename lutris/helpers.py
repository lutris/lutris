#!/usr/bin/python
# -*- coding:Utf-8 -*-
#
#  Copyright (C) 2010 Mathieu Comandon <strider@strycore.com>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License version 3 as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

"""Helpers for an Ubuntu application."""

__all__ = ['make_window',]

import os
import gtk
import gettext

from lutris.lutrisconfig import get_data_file

from gettext import gettext as _
gettext.textdomain('lutris')

def get_builder(builder_file_name):
    """Return a fully-instantiated gtk.Builder instance from specified ui
    file

    :param builder_file_name: The name of the builder file, without extension.
        Assumed to be in the 'ui' directory under the data path.
    """
    # Look for the ui file that describes the user interface.
    ui_filename = get_data_file('ui', '%s.ui' % (builder_file_name,))
    if not os.path.exists(ui_filename):
        ui_filename = None

    builder = gtk.Builder()
    builder.set_translation_domain('lutris')
    builder.add_from_file(ui_filename)
    return builder
