import os
from lutris.util.http import Request
from gi.repository import Gtk, GObject, GLib
from lutris.gui.widgets import Dialog
from lutris.util import system
from lutris.util.extract import extract_archive
from lutris import settings
from lutris.downloader import Downloader


class RunnerInstallDialog(Dialog):
    BASE_API_URL = "https://lutris.net/api/runners/"
    COL_VER = 0
    COL_ARCH = 1
    COL_URL = 2
    COL_INSTALLED = 3
    COL_PROGRESS = 4

    def __init__(self, title, parent, runner):
        super(RunnerInstallDialog, self).__init__(title, parent)
        self.runner = runner
        self.runner_info = self.get_runner_info()
        label = Gtk.Label("%s version management" % self.runner_info['name'])
        self.vbox.add(label)
        self.runner_store = self.get_store()
        self.treeview = self.get_treeview(self.runner_store)

        self.vbox.add(self.treeview)
        self.show_all()

    def get_runner_info(self):
        api_url = self.BASE_API_URL + self.runner
        response = Request(api_url).get()
        return response.json

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

    def get_dest_path(self, path):
        row = self.runner_store[path]
        url = row[2]
        filename = os.path.basename(url)
        return os.path.join(settings.CACHE_DIR, filename)

    def on_installed_toggled(self, widget, path):
        row = self.runner_store[path]
        if row[self.COL_INSTALLED]:
            self.uninstall_runner(path)
        else:
            self.install_runner(path)

    def uninstall_runner(self, path):
        row = self.runner_store[path]
        version = row[self.COL_VER]
        arch = row[self.COL_ARCH]
        system.remove_folder(self.get_runner_path(version, arch))
        row[self.COL_INSTALLED] = False

    def install_runner(self, path):
        row = self.runner_store[path]
        url = row[2]
        dest_path = self.get_dest_path(path)
        downloader = Downloader(url, dest_path)
        self.download_timer = GLib.timeout_add(100, self.get_progress,
                                               downloader, path)
        downloader.start()

    def get_progress(self, downloader, path):
        row = self.runner_store[path]
        row[4] = downloader.progress * 100
        if downloader.progress >= 1.0:
            self.on_installer_downloaded(path)
            return False
        return True

    def on_installer_downloaded(self, path):
        row = self.runner_store[path]
        version = row[0]
        architecture = row[1]
        archive_path = self.get_dest_path(path)
        dest_path = self.get_runner_path(version, architecture)
        extract_archive(archive_path, dest_path)
        row[self.COL_PROGRESS] = 0
        row[self.COL_INSTALLED] = True


if __name__ == "__main__":
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    RunnerInstallDialog("test", None, "wine")
    GObject.threads_init()
    Gtk.main()
