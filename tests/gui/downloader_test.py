#!/usr/bin/env python

from os.path import join, dirname, abspath
import sys
lutris_path = join(dirname(abspath(__file__)),"../..")
sys.path.insert(0, lutris_path)
import gtk
from lutris.gui.common import DownloadDialog

url = "http://localhost/rune.iso"

dest = "/tmp/lutris-testfile.ogv"

if __name__ == "__main__":
    dl = DownloadDialog(url, dest)
    dl.quit_gtk = True
    d= dl.show()
    gtk.gdk.threads_init()
    gtk.gdk.threads_enter()
    gtk.main()
    gtk.gdk.threads_leave()

