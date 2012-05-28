#!/usr/bin/env python

from os.path import join, dirname, abspath
import sys
lutris_path = join(dirname(abspath(__file__)), "../..")
sys.path.insert(0, lutris_path)
from gi.repository import Gtk
from lutris.gui.common import DownloadDialog

url = "http://localhost/rune.iso"
dest = "/tmp/lutris-testfile.ogv"

if __name__ == "__main__":
    dl = DownloadDialog(url, dest)
    dl.quit_gtk = True
    dl.show()
    Gdk.threads_init()
    Gdk.threads_enter()
    Gtk.main()
    Gdk.threads_leave()
