"""Dialog used to install versions of a runner"""
# pylint: disable=no-member
import os
import random
from collections import defaultdict

from gi.repository import GLib, Gtk
from lutris.pga import get_games_by_runner
from lutris.game import Game
from lutris import api, settings
from lutris.gui.dialogs import Dialog, ErrorDialog, QuestionDialog
from lutris.util import jobs, system
from lutris.util.downloader import Downloader
from lutris.util.extract import extract_archive
from lutris.util.log import logger


class RunnerInstallDialog(Dialog):
    """Dialog displaying available runner version and downloads them"""
    COL_VER = 0
    COL_ARCH = 1
    COL_URL = 2
    COL_INSTALLED = 3
    COL_PROGRESS = 4
    COL_USAGE = 5

    def __init__(self, title, parent, runner):
        super().__init__(title, parent, 0)
        self.add_buttons("_OK", Gtk.ButtonsType.OK)
        self.runner = runner
        self.runner_info = {}
        self.installing = {}
        self.set_default_size(512, 480)

        self.renderer_progress = Gtk.CellRendererProgress()

        label = Gtk.Label.new("Waiting for response from %s" % (settings.SITE_URL))
        self.vbox.pack_start(label, False, False, 18)

        spinner = Gtk.Spinner(visible=True)
        spinner.start()
        self.vbox.pack_start(spinner, False, False, 18)

        self.show_all()

        self.runner_store = Gtk.ListStore(str, str, str, bool, int, str)
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

        self.populate_store()

        label = Gtk.Label.new("%s version management" % self.runner_info["name"])
        self.vbox.add(label)
        scrolled_window = Gtk.ScrolledWindow()
        treeview = self.get_treeview(self.runner_store)
        self.installing = {}
        self.connect("response", self.on_destroy)

        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_shadow_type(Gtk.ShadowType.ETCHED_OUT)
        scrolled_window.add(treeview)

        self.vbox.pack_start(scrolled_window, True, True, 14)
        self.show_all()

    def get_treeview(self, model):
        """Return TreeeView widget"""
        treeview = Gtk.TreeView(model=model)
        treeview.set_headers_visible(False)

        renderer_toggle = Gtk.CellRendererToggle()
        renderer_text = Gtk.CellRendererText()

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

        usage_column = Gtk.TreeViewColumn(None, renderer_text, text=self.COL_USAGE)
        usage_column.set_property("min-width", 200)
        treeview.append_column(usage_column)

        return treeview

    def get_usage_stats(self):
        """Return the usage for each version"""
        runner_games = get_games_by_runner(self.runner)
        if self.runner == "wine":
            runner_games += get_games_by_runner("winesteam")
        version_usage = defaultdict(list)
        for db_game in runner_games:
            if not db_game["installed"]:
                continue
            game = Game(db_game["id"])
            version = game.config.runner_config["version"]
            version_usage[version].append(db_game["id"])
        return version_usage

    def populate_store(self):
        """Return a ListStore populated with the runner versions"""
        version_usage = self.get_usage_stats()
        for version_info in reversed(self.runner_info["versions"]):
            is_installed = os.path.exists(
                self.get_runner_path(version_info["version"], version_info["architecture"])
            )
            games_using = version_usage.get("%(version)s-%(architecture)s" % version_info)
            usage_summary = "In use by %d game%s" % (
                len(games_using), "s" if len(games_using) > 1 else ""
            ) if games_using else "Not in use"
            self.runner_store.append(
                [
                    version_info["version"],
                    version_info["architecture"],
                    version_info["url"],
                    is_installed,
                    0,
                    usage_summary if is_installed else ""
                ]
            )

    def get_runner_path(self, version, arch):
        """Return the local path where the runner is/will be installed"""
        return os.path.join(
            settings.RUNNER_DIR, self.runner, "{}-{}".format(version, arch)
        )

    def get_dest_path(self, row):
        """Return temporary path where the runners should be downloaded to"""
        return os.path.join(settings.CACHE_DIR, os.path.basename(row[self.COL_URL]))

    def on_installed_toggled(self, _widget, path):
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
        """Cancel the installation of a runner version"""
        self.installing[row[self.COL_VER]].cancel()
        self.uninstall_runner(row)
        row[self.COL_PROGRESS] = 0
        self.installing.pop(row[self.COL_VER])

    def uninstall_runner(self, row):
        """Uninstall a runner version"""
        version = row[self.COL_VER]
        arch = row[self.COL_ARCH]
        system.remove_folder(self.get_runner_path(version, arch))
        row[self.COL_INSTALLED] = False
        if self.runner == "wine":
            logger.debug("Clearing wine version cache")
            from lutris.util.wine.wine import get_wine_versions

            get_wine_versions.cache_clear()

    def install_runner(self, row):
        """Download and install a runner version"""
        dest_path = self.get_dest_path(row)
        downloader = Downloader(row[self.COL_URL], dest_path, overwrite=True)
        GLib.timeout_add(100, self.get_progress, downloader, row)
        self.installing[row[self.COL_VER]] = downloader
        downloader.start()

    def get_progress(self, downloader, row):
        """Update progress bar with download progress"""
        if downloader.state == downloader.CANCELLED:
            return False
        if downloader.state == downloader.ERROR:
            self.cancel_install(row)
            return False
        downloader.check_progress()
        percent_downloaded = downloader.progress_percentage
        if percent_downloaded >= 1:
            row[self.COL_PROGRESS] = percent_downloaded
            self.renderer_progress.props.pulse = -1
            self.renderer_progress.props.text = "%d %%" % int(percent_downloaded)
        else:
            row[self.COL_PROGRESS] = 1
            self.renderer_progress.props.pulse = random.randint(1, 100)
            self.renderer_progress.props.text = "Downloading…"
        if downloader.state == downloader.COMPLETED:
            row[self.COL_PROGRESS] = 99
            self.renderer_progress.props.text = "Extracting…"
            self.on_runner_downloaded(row)
            return False
        return True

    def on_runner_downloaded(self, row):
        """Handler called when a runner version is downloaded"""
        version = row[self.COL_VER]
        architecture = row[self.COL_ARCH]
        logger.debug("Runner %s for %s has finished downloading", version, architecture)
        src = self.get_dest_path(row)
        dst = self.get_runner_path(version, architecture)
        jobs.AsyncCall(self.extract, self.on_extracted, src, dst, row)

    @staticmethod
    def extract(src, dst, row):
        """Extract a runner archive to a destination"""
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
        return True


if __name__ == "__main__":
    import signal

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    RunnerInstallDialog("test", None, "wine")
    Gtk.main()
