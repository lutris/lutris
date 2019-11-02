# pylint: disable=missing-docstring,no-member
import os
import random

from gi.repository import GLib, Gtk
from lutris import api, settings
from lutris.gui.dialogs import Dialog, ErrorDialog, QuestionDialog
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
        super().__init__(title, parent, 0, ("_OK", Gtk.ResponseType.OK))
        width, height = (512, 480)
        self.dialog_size = (width, height)
        self.set_default_size(width, height)

        self.runner = runner

        self.label = Gtk.Label("Waiting for response from %s" % (settings.SITE_URL))
        self.vbox.pack_start(self.label, False, False, 18)

        # Display a wait icon.
        self.spinner = Gtk.Spinner()
        self.vbox.pack_start(self.spinner, False, False, 18)
        self.spinner.show()
        self.spinner.start()

        self.show_all()

        jobs.AsyncCall(api.get_runners, self.display_all_versions, self.runner)

    def display_all_versions(self, runner_info, error):
        """Clear the box and display versions from runner_info"""
        if error:
            logger.error(error)

        self.runner_info = runner_info
        if not self.runner_info:
            ErrorDialog(
                "Unable to get runner versions. Check your internet connection."
            )
            return

        for child_widget in self.vbox.get_children():
            if child_widget.get_name() not in "GtkBox":
                child_widget.destroy()

        label = Gtk.Label("%s version management" % self.runner_info["name"])
        self.vbox.add(label)
        self.runner_store = self.get_store()
        scrolled_window = Gtk.ScrolledWindow()
        self.treeview = self.get_treeview(self.runner_store)
        self.installing = {}
        self.connect("response", self.on_destroy)

        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
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
        version_column.add_attribute(renderer_text, "text", self.COL_VER)
        version_column.set_property("min-width", 80)
        treeview.append_column(version_column)

        arch_column = Gtk.TreeViewColumn(None, renderer_text, text=self.COL_ARCH)
        arch_column.set_property("min-width", 50)
        treeview.append_column(arch_column)

        progress_column = Gtk.TreeViewColumn(
            None,
            self.renderer_progress,
            value=self.COL_PROGRESS,
            visible=self.COL_PROGRESS,
        )
        progress_column.set_property("fixed-width", 60)
        progress_column.set_property("min-width", 60)
        progress_column.set_property("resizable", False)
        treeview.append_column(progress_column)

        return treeview

    def get_store(self):
        liststore = Gtk.ListStore(str, str, str, bool, int)
        for version_info in reversed(self.get_versions()):
            version = version_info["version"]
            architecture = version_info["architecture"]
            progress = 0
            is_installed = os.path.exists(self.get_runner_path(version, architecture))
            liststore.append(
                [
                    version_info["version"],
                    version_info["architecture"],
                    version_info["url"],
                    is_installed,
                    progress,
                ]
            )
        return liststore

    def get_versions(self):
        return self.runner_info["versions"]

    def get_runner_path(self, version, arch):
        return os.path.join(
            settings.RUNNER_DIR, self.runner, "{}-{}".format(version, arch)
        )

    @staticmethod
    def get_dest_path(row):
        url = row[2]
        filename = os.path.basename(url)
        return os.path.join(settings.CACHE_DIR, filename)

    def on_installed_toggled(self, widget, path):
        row = self.runner_store[path]
        if row[self.COL_VER] in self.installing:
            confirm_dlg = QuestionDialog(
                {
                    "question": "Do you want to cancel the download?",
                    "title": "Download starting",
                }
            )
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
        if self.runner == "wine":
            logger.debug("Clearing wine version cache")
            from lutris.util.wine.wine import get_wine_versions

            get_wine_versions.cache_clear()

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
        logger.debug("Runner %s for %s has finished downloading", version, architecture)
        src = self.get_dest_path(row)
        dst = self.get_runner_path(version, architecture)
        jobs.AsyncCall(self.extract, self.on_extracted, src, dst, row)

    @staticmethod
    def extract(src, dst, row):
        extract_archive(src, dst)
        return src, row

    def on_extracted(self, row_info, error):
        """Called when a runner archive is extracted"""
        if error or not row_info:
            ErrorDialog("Failed to retrieve the runner archive", parent=self)
            return
        src, row = row_info
        os.remove(src)
        row[self.COL_PROGRESS] = 0
        row[self.COL_INSTALLED] = True
        self.renderer_progress.props.text = ""
        self.installing.pop(row[self.COL_VER])
        if self.runner == "wine":
            logger.debug("Clearing wine version cache")
            from lutris.util.wine.wine import get_wine_versions

            get_wine_versions.cache_clear()

    def on_destroy(self, _dialog, _data=None):
        """Override delete handler to prevent closing while downloads are active"""
        if self.installing:
            return True
        self.destroy()


if __name__ == "__main__":
    import signal

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    RunnerInstallDialog("test", None, "wine")
    Gtk.main()
