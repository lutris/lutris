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

import gobject
import urllib
import threading

class DownloadStoppedException:
    def __init__(self):
        pass

class Downloader(threading.Thread):
    """Downloader class that doesn't block the program"""

    def __init__(self, url, dest):
        """Set up the downloader."""
        threading.Thread.__init__(self)
        self.setDaemon(False)
        self.url = url
        self.dest = dest
        self.progress = 0
        self.kill = None

    def run(self):
        """Start the download."""
        urllib.urlretrieve(self.url, self.dest, self._report_progress)
        return True

    def _report_progress(self, piece, received_bytes, total_size):
        self.progress = ((piece * received_bytes) * 100) / total_size
        try:
            if self.kill is True:
                raise DownloadStoppedException 
        except DownloadStoppedException:
            pass
            
