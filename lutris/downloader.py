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
""" Downloader module """

import urllib
import datetime
import threading

from lutris.util.log import logger


class DownloadStoppedException(Exception):
    """ Dummy exception for download canceled. """
    def __init__(self):
        super(DownloadStoppedException, self).__init__()


class Downloader(threading.Thread):
    """Downloader class that doesn't block the program"""

    start_time = 0
    elapsed_time = datetime.timedelta(seconds=1)
    total_downloaded = 0
    total_size = 0

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
        logger.debug("Download of %s starting" % self.url)
        self.start_time = datetime.datetime.now()
        urllib.urlretrieve(self.url, self.dest, self._report_progress)
        return True

    def _report_progress(self, piece, received_bytes, total_size):
        """ Update download's progress. """
        self.elapsed_time = datetime.datetime.now() - self.start_time
        self.total_downloaded += received_bytes
        self.total_size = total_size
        self.progress = ((piece * received_bytes)) / (total_size * 1.0)
        try:
            if self.kill is True:
                raise DownloadStoppedException
        except DownloadStoppedException:
            logger.debug("stopping download")
