import os
from gi.repository import Gtk, GObject, GLib
from lutris.util.log import logger
from lutris.gui.widgets import Dialog
from lutris.util import system
from lutris.util.extract import extract_archive
from lutris import api
from lutris import settings
from lutris.downloader import Downloader


class RunnerInstallDialog(Dialog):
    COL_VER = 0
    COL_ARCH = 1
    COL_URL = 2
    COL_INSTALLED = 3
    COL_PROGRESS = 4

    def __init__(self, title, parent, runner):
        super(RunnerInstallDialog, self).__init__(
            title, parent, 0, ('_OK', Gtk.ResponseType.OK)
        )
        self.runner = runner
        self.runner_info = api.get_runners(self.runner)
        label = Gtk.Label("%s version management" % self.runner_info['name'])
        self.vbox.add(label)
        self.runner_store = self.get_store()
        self.treeview = self.get_treeview(self.runner_store)
        self.installing = {}

        self.vbox.add(self.treeview)
        self.show_all()

    def get_treeview(self, model):
        treeview = Gtk.TreeView(model=model)
        treeview.set_headers_visible(False)

        renderer_toggle = Gtk.CellRendererToggle()
        renderer_text = Gtk.CellRendererText()
        renderer_progress = Gtk.CellRendererProgress()

        installed_column = Gtk.TreeViewColumn(None, renderer_toggle, active=3)
        renderer_toggle.connect("toggled", self.on_installed_toggled)
        treeview.append_column(installed_column)

        version_column = Gtk.TreeViewColumn(None, renderer_text)
        version_column.add_attribute(renderer_text, 'text', self.COL_VER)
        version_column.set_property('min-width', 80)
        treeview.append_column(version_column)

        arch_column = Gtk.TreeViewColumn(None, renderer_text,
                                         text=self.COL_ARCH)
        arch_column.set_property('min-width', 50)
        treeview.append_column(arch_column)

        progress_column = Gtk.TreeViewColumn(None, renderer_progress,
                                             value=self.COL_PROGRESS,
                                             visible=self.COL_PROGRESS)
        progress_column.set_property('fixed-width', 60)
        progress_column.set_property('min-width', 60)
        progress_column.set_property('resizable', False)
        treeview.append_column(progress_column)

        return treeview

    def get_store(self):
        liststore = Gtk.ListStore(str, str, str, bool, int)
        for version_info in reversed(self.get_versions()):
            version = version_info['version']
            architecture = version_info['architecture']
            progress = 0
            is_installed = os.path.exists(
                self.get_runner_path(version, architecture)
            )
            liststore.append(
                [version_info['version'],
                 version_info['architecture'],
                 version_info['url'],
                 is_installed,
                 progress]
            )
        return liststore

    def get_versions(self):
        return self.runner_info['versions']

    def get_runner_path(self, version, arch):
        return os.path.join(settings.RUNNER_DIR, self.runner,
                            "{}-{}".format(version, arch))

    def get_dest_path(self, row):
        url = row[2]
        filename = os.path.basename(url)
        return os.path.join(settings.CACHE_DIR, filename)

    def on_installed_toggled(self, widget, path):
        row = self.runner_store[path]
        if row[self.COL_VER] in self.installing:
            self.cancel_install(row)
        elif row[self.COL_INSTALLED]:
            self.uninstall_runner(row)
        else:
            self.install_runner(row)

    def cancel_install(self, row):
        self.installing[row[self.COL_VER]].cancel()
        self.uninstall_runner(row)
        row[self.COL_PROGRESS] = 0
        self.installing.pop(row[self.COL_VER])

    def uninstall_runner(self, row):
        version = row[self.COL_VER]
        arch = row[self.COL_ARCH]
        system.remove_folder(self.get_runner_path(version, arch))
        row[self.COL_INSTALLED] = False

    def install_runner(self, row):
        url = row[2]
        logger.debug("Downloading %s", url)
        dest_path = self.get_dest_path(row)
        downloader = Downloader(url, dest_path, overwrite=True)
        GLib.timeout_add(100, self.get_progress, downloader, row)
        self.installing[row[self.COL_VER]] = downloader
        downloader.start()

    def get_progress(self, downloader, row):
        if downloader.state == downloader.CANCELLED:
            return False
        if downloader.state == downloader.ERROR:
            self.cancel_install(row)
            return False
        downloader.check_progress()
        row[4] = downloader.progress_percentage
        if downloader.state == downloader.COMPLETED:
            row[4] = 99
            self.on_runner_downloaded(row)
            return False
        return True

    def on_runner_downloaded(self, row):
        version = row[0]
        architecture = row[1]
        src = self.get_dest_path(row)
        dst = self.get_runner_path(version, architecture)
        from lutris.util import jobs
        jobs.AsyncCall(self.extract, self.on_extracted, src, dst, row)

    def extract(self, src, dst, row):
        extract_archive(src, dst)
        return src, row

    def on_extracted(self, (src, row), error):
        os.remove(src)
        row[self.COL_PROGRESS] = 0
        row[self.COL_INSTALLED] = True
        self.installing.pop(row[self.COL_VER])


if __name__ == "__main__":
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    RunnerInstallDialog("test", None, "wine")
    GObject.threads_init()
    Gtk.main()
