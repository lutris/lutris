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

"""Downloader class that doesn't block the program"""

import gobject
import urllib

class Downloader(gobject.GObject):

    __gsignals__ = {
            'report-progress': (gobject.RUN_LAST, gocject.TYPE_NONE,
                (gobject.TYPE_INT,))
            }

    def __init__(self, url, dest):
        """"""
        gobject.GObject.__init__(self)
        self.url = url
        self.dest = path

    def start(self):
        """Start the download"""
        urllib.urlretrieve(self.url, self.dest, self.report_progress)

    def report_progress(self, piece, received_bytes, total_size):
        progress = ((piece * received_bytes) * 100) / total_size
        self.emit('report-progress', progress)

