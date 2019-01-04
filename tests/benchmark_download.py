import time
import urllib
import sys
import os
import gi
gi.require_version('Gdk', '3.0')
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GObject


sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from lutris.gui.dialogs import DownloadDialog

TEST_URL = "https://lutris.net/releases/lutris_0.3.0.tar.gz"
TEST_FILE_SIZE = 4582508


def timed(function):
    def _wrapped(*args, **kwargs):
        start_time = time.time()
        retval = function(*args, **kwargs)
        total = time.time() - start_time
        print(function.__name__, (TEST_FILE_SIZE / total) / 1048576)
        return retval
    return _wrapped


@timed
def test_urlretrieve():
    urllib.urlretrieve(TEST_URL, "/tmp/test-dl")


class DownloadDialogBenchmark(DownloadDialog):
    def download_complete(self, _widget, _data):
        print("Complete")
        self.destroy()
        Gtk.main_quit()


@timed
def test_download_dialog():
    DownloadDialogBenchmark(TEST_URL, "/tmp/test-downloader")
    Gtk.main()


test_download_dialog()
# test_urlretrieve()
