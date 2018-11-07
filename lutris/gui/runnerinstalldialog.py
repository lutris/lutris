# pylint: disable=missing-docstring
import os
import random

from gi.repository import GLib, GObject, Gtk
from lutris import api, settings
from lutris.gui.dialogs import ErrorDialog, QuestionDialog
from lutris.gui.widgets.dialogs import Dialog
from lutris.util import jobs, system
from lutris.util.downloader import Downloader
from lutris.util.extract import extract_archive
from lutris.util.log import logger


class RunnerInstallDialog(Dialog):
    COL_VER = 0
    COL_ARCH = 1
    COL_URL = 2
    COL_INSTALLED = 3
    COL_PROGRESS = 4

    def __init__(self, title, parent, runner):
        super().__init__(
            title, parent, 0, ('_OK', Gtk.ResponseType.OK)
        )
        width, height = (460, 380)
        self.dialog_size = (width, height)
        self.set_default_size(width, height)

        self.runner = runner
        self.runner_info = api.get_runners(self.runner)
        if not self.runner_info:
            ErrorDialog('Unable to get runner versions, check your internet connection',
                        parent=parent)
            return
        label = Gtk.Label("%s version management" % self.runner_info['name'])
        self.vbox.add(label)
        self.runner_store = self.get_store()
        scrolled_window = Gtk.ScrolledWindow()
        self.treeview = self.get_treeview(self.runner_store)
        self.installing = {}
        self.connect('response', self.on_response)

        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                   Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_shadow_type(Gtk.ShadowType.ETCHED_OUT)
        scrolled_window.add(self.treeview)

        self.vbox.pack_start(scrolled_window, True, True, 14)
        self.show_all()

    def get_treeview(self, model):
        treeview = Gtk.TreeView(model=model)
        treeview.set_headers_visible(False)

        renderer_toggle = Gtk.CellRendererToggle()
        renderer_text = Gtk.CellRendererText()
        self.renderer_progress = Gtk.CellRendererProgress()

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

        progress_column = Gtk.TreeViewColumn(None, self.renderer_progress,
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

    @staticmethod
    def get_dest_path(row):
        url = row[2]
        filename = os.path.basename(url)
        return os.path.join(settings.CACHE_DIR, filename)

    def on_installed_toggled(self, widget, path):
        row = self.runner_store[path]
        if row[self.COL_VER] in self.installing:
            confirm_dlg = QuestionDialog({
                "question": "Do you want to cancel the download?",
                "title": "Download starting"
            })
            if confirm_dlg.result == confirm_dlg.YES:
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
        percent_downloaded = downloader.progress_percentage
        if percent_downloaded >= 1:
            row[4] = percent_downloaded
            self.renderer_progress.props.pulse = -1
            self.renderer_progress.props.text = "%d %%" % int(percent_downloaded)
        else:
            row[4] = 1
            self.renderer_progress.props.pulse = random.randint(1, 100)
            self.renderer_progress.props.text = "Downloading…"
        if downloader.state == downloader.COMPLETED:
            row[4] = 99
            self.renderer_progress.props.text = "Extracting…"
            self.on_runner_downloaded(row)
            return False
        return True

    def on_runner_downloaded(self, row):
        version = row[0]
        architecture = row[1]
        src = self.get_dest_path(row)
        dst = self.get_runner_path(version, architecture)
        jobs.AsyncCall(self.extract, self.on_extracted, src, dst, row)

    @staticmethod
    def extract(src, dst, row):
        extract_archive(src, dst)
        return src, row

    def on_extracted(self, xxx_todo_changeme, error):
        (src, row) = xxx_todo_changeme
        os.remove(src)
        row[self.COL_PROGRESS] = 0
        row[self.COL_INSTALLED] = True
        self.renderer_progress.props.text = ""
        self.installing.pop(row[self.COL_VER])

    def on_response(self, dialog, response):
        self.destroy()


if __name__ == "__main__":
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    RunnerInstallDialog("test", None, "wine")
    GObject.threads_init()
    Gtk.main()
