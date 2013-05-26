""" Non-blocking Gio Downloader  """
import time
from gi.repository import Gio, GLib, Gtk


class Downloader():
    downloaded_bytes = 0
    total_bytes = 0
    time_elapsed = 0
    time_remaining = 0
    speed = 0
    cancelled = False

    def __init__(self, url, dest):
        self.remote = Gio.File.new_for_uri(url)
        self.local = Gio.File.new_for_path(dest)
        self.cancellable = Gio.Cancellable()
        self.progress = 0
        self.start_time = None

    def progress_callback(self, downloaded_bytes, total_bytes, _user_data):
        self.downloaded_bytes = downloaded_bytes
        self.total_bytes = total_bytes
        self.time_elapsed = time.time() - self.start_time
        self.speed = self.downloaded_bytes / self.time_elapsed or 1
        self.time_remaining = (total_bytes - downloaded_bytes) / self.speed
        self.progress = float(downloaded_bytes) / float(total_bytes)

    def cancel(self):
        self.cancellable.cancel()
        self.cancelled = True

    def download(self, job, cancellable, _data):
        flags = Gio.FileCopyFlags.OVERWRITE
        try:
            self.remote.copy(self.local, flags, self.cancellable,
                             self.progress_callback, None)
        except GLib.GError as ex:
            print "transfer error:", ex.message
            if ex.code == Gio.IOErrorEnum.TIMED_OUT:
                # For unknown reasons, FTP transfers times out at 25 seconds
                # Hint: 25 seconds is the default timeout of GDusProxy
                # https://developer.gnome.org/gio/2.26/GDBusProxy.html#GDBusProxy--g-default-timeout
                print "FTP tranfers not supported yet"

    def mount_cb(self, fileobj, result, _data):
        try:
            mount_success = fileobj.mount_enclosing_volume_finish(result)
            if mount_success:
                GLib.idle_add(self.schedule_download)
        except GLib.GError as ex:
            if(ex.code != Gio.IOErrorEnum.ALREADY_MOUNTED and
               ex.code != Gio.IOErrorEnum.NOT_SUPPORTED):
                print ex.message

    def schedule_download(self):
        Gio.io_scheduler_push_job(self.download, None,
                                  GLib.PRIORITY_DEFAULT_IDLE,
                                  Gio.Cancellable())

    def start(self):
        self.start_time = time.time()
        if not self.remote.query_exists(Gio.Cancellable()):
            self.remote.mount_enclosing_volume(Gio.MountMountFlags.NONE,
                                               Gtk.MountOperation(),
                                               Gio.Cancellable(),
                                               self.mount_cb,
                                               None)

        else:
            GLib.idle_add(self.schedule_download)
