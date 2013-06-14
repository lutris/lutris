import time
import urllib
import sys
import os
from gi.repository import Gtk, Gdk, GObject

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from lutris.util import http
from lutris.gui.dialogs import DownloadDialog

#TEST_URL = "file:///usr/bin/gvim"
#TEST_URL = "http://strycore.com/documents/serious.sam.tfe_1.05beta3-english-2.run"
TEST_FILE_SIZE = 11034817
#TEST_URL = "ftp://ftp.3drealms.com/share/3dsw12.zip"
#TEST_URL = "ftp://ftp.idsoftware.com/idstuff/wolf/linux/wolf-linux-1.41b.x86.run"
TEST_URL = "ftp://download.nvidia.com/XFree86/Linux-x86/319.23/NVIDIA-Linux-x86-319.23.run"
#TEST_URL = "http://strycore.com/documents/normality-en.7z"
#TEST_URL = "smb://newport/games/linux/aquaria/aquaria-lnx-humble-bundle.mojo.run"
Gdk.threads_init()
GObject.threads_init()


def timed(function):
    def _wrapped(*args, **kwargs):
        print ">",
        start_time = time.time()
        retval = function(*args, **kwargs)
        total = time.time() - start_time
        print function.__name__, (TEST_FILE_SIZE / total) / 1048576
        return retval
    return _wrapped


@timed
def test_urlretrieve():
    urllib.urlretrieve(TEST_URL, "/tmp/test-dl")


@timed
def test_download_asset():
    http.download_asset(TEST_URL, "/tmp/test-asset", overwrite=True)


class DownloadDialogBenchmark(DownloadDialog):
    def download_complete(self, _widget, _data):
        print "Complete"
        self.destroy()
        Gtk.main_quit()


@timed
def test_download_dialog():
    DownloadDialogBenchmark(TEST_URL, "/tmp/test-downloader")
    Gtk.main()


test_download_dialog()
#test_urlretrieve()
#test_download_asset()
