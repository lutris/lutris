"""Dialog used to install versions of a runner"""
# pylint: disable=no-member
import gettext
import os
import re
from collections import defaultdict
from gettext import gettext as _

from gi.repository import GLib, Gtk

from lutris import api, settings
from lutris.database.games import get_games_by_runner
from lutris.game import Game
from lutris.gui.dialogs import ErrorDialog, ModalDialog, ModelessDialog
from lutris.gui.widgets.utils import has_stock_icon
from lutris.util import jobs, system
from lutris.util.downloader import Downloader
from lutris.util.extract import extract_archive
from lutris.util.log import logger


class ShowAppsDialog(ModalDialog):
    def __init__(self, title, parent, runner_version, apps):
        super().__init__(title, parent, border_width=10)
        self.add_default_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        self.set_default_size(600, 400)

        label = Gtk.Label.new(_("Showing games using %s") % runner_version)
        self.vbox.add(label)
        scrolled_listbox = Gtk.ScrolledWindow()
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled_listbox.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_listbox.set_shadow_type(Gtk.ShadowType.ETCHED_OUT)
        scrolled_listbox.add(listbox)
        self.vbox.pack_start(scrolled_listbox, True, True, 14)

        for app in apps:
            row = Gtk.ListBoxRow()
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

            lbl_game = Gtk.Label(app.name)
            lbl_game.set_halign(Gtk.Align.START)
            hbox.pack_start(lbl_game, True, True, 5)
            row.add(hbox)
            listbox.add(row)

        self.show_all()


class RunnerInstallDialog(ModelessDialog):
    """Dialog displaying available runner version and downloads them"""
    COL_VER = 0
    COL_ARCH = 1
    COL_URL = 2
    COL_INSTALLED = 3
    COL_PROGRESS = 4
    COL_USAGE = 5

    INSTALLED_ICON_NAME = "software-installed-symbolic" \
        if has_stock_icon("software-installed-symbolic") else "wine-symbolic"

    def __init__(self, title, parent, runner):
        super().__init__(title, parent, 0, border_width=10)
        self.add_default_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        self.runner_name = runner.name
        self.runner_directory = runner.directory
        self.runner_info = {}
        self.installing = {}
        self.set_default_size(640, 480)
        self.runners = []
        self.listbox = None

        label = Gtk.Label.new(_("Waiting for response from %s") % settings.SITE_URL)
        self.vbox.pack_start(label, False, False, 18)

        spinner = Gtk.Spinner(visible=True)
        spinner.start()
        self.vbox.pack_start(spinner, False, False, 18)

        self.show_all()

        self.runner_store = Gtk.ListStore(str, str, str, bool, int, int)
        jobs.AsyncCall(api.get_runners, self.runner_fetch_cb, self.runner_name)

    def runner_fetch_cb(self, runner_info, error):
        """Clear the box and display versions from runner_info"""
        if error:
            logger.error(error)
            ErrorDialog(_("Unable to get runner versions: %s") % error)
            return

        self.runner_info = runner_info
        remote_versions = {(v["version"], v["architecture"]) for v in self.runner_info["versions"]}
        local_versions = self.get_installed_versions()
        for local_version in local_versions - remote_versions:
            self.runner_info["versions"].append({
                "version": local_version[0],
                "architecture": local_version[1],
                "url": "",
            })

        if not self.runner_info:
            ErrorDialog(_("Unable to get runner versions from lutris.net"))
            return

        for child_widget in self.vbox.get_children():
            if child_widget.get_name() not in "GtkBox":
                child_widget.destroy()

        label = Gtk.Label.new(_("%s version management") % self.runner_info["name"])
        self.vbox.add(label)
        self.installing = {}
        self.connect("response", self.on_destroy)

        scrolled_listbox = Gtk.ScrolledWindow()
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled_listbox.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_listbox.set_shadow_type(Gtk.ShadowType.ETCHED_OUT)
        scrolled_listbox.add(self.listbox)
        self.vbox.pack_start(scrolled_listbox, True, True, 14)

        self.populate_store()
        self.show_all()
        self.populate_listboxrows(self.runner_store)

    def populate_listboxrows(self, store):
        for runner in store:
            row = Gtk.ListBoxRow()
            row.runner = runner
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            row.hbox = hbox

            icon = Gtk.Image.new_from_icon_name(self.INSTALLED_ICON_NAME, Gtk.IconSize.MENU)
            icon.set_visible(runner[self.COL_INSTALLED])
            icon_container = Gtk.Box()
            icon_container.set_size_request(16, 16)
            icon_container.pack_start(icon, False, False, 0)

            hbox.pack_start(icon_container, False, True, 0)
            row.icon = icon

            lbl_version = Gtk.Label(runner[self.COL_VER])
            lbl_version.set_max_width_chars(20)
            lbl_version.set_property("width-chars", 20)
            lbl_version.set_halign(Gtk.Align.START)
            hbox.pack_start(lbl_version, False, False, 5)

            arch_label = Gtk.Label(runner[self.COL_ARCH])
            arch_label.set_max_width_chars(8)
            arch_label.set_halign(Gtk.Align.START)
            hbox.pack_start(arch_label, False, True, 5)

            install_progress = Gtk.ProgressBar()
            install_progress.set_show_text(True)
            hbox.pack_end(install_progress, True, True, 5)
            row.install_progress = install_progress

            if runner[self.COL_INSTALLED]:
                # Check if there are apps installed, if so, show the view apps button
                app_count = runner[self.COL_USAGE] or 0
                if app_count > 0:
                    usage_button_text = gettext.ngettext(
                        "View %d game",
                        "View %d games",
                        app_count
                    ) % app_count

                    usage_button = Gtk.LinkButton.new_with_label(usage_button_text)
                    usage_button.set_valign(Gtk.Align.CENTER)
                    usage_button.connect("clicked", self.on_show_apps_usage, row)
                    hbox.pack_end(usage_button, False, True, 2)

            button = Gtk.Button()
            button.set_size_request(100, -1)
            hbox.pack_end(button, False, True, 0)
            hbox.reorder_child(button, 0)
            row.install_uninstall_cancel_button = button
            row.handler_id = None

            row.add(hbox)
            self.listbox.add(row)
            row.show_all()
            self.update_listboxrow(row)

    def update_listboxrow(self, row):
        row.install_progress.set_visible(False)

        runner = row.runner
        icon = row.icon
        icon.set_visible(runner[self.COL_INSTALLED])

        button = row.install_uninstall_cancel_button
        style_context = button.get_style_context()
        if row.handler_id is not None:
            button.disconnect(row.handler_id)
            row.handler_id = None
        if runner[self.COL_VER] in self.installing:
            style_context.remove_class("destructive-action")
            button.set_label(_("Cancel"))
            handler_id = button.connect("clicked", self.on_cancel_install, row)
        else:
            if runner[self.COL_INSTALLED]:
                style_context.add_class("destructive-action")
                button.set_label(_("Uninstall"))
                handler_id = button.connect("clicked", self.on_uninstall_runner, row)
            else:
                style_context.remove_class("destructive-action")
                button.set_label(_("Install"))
                handler_id = button.connect("clicked", self.on_install_runner, row)

        row.install_uninstall_cancel_button = button
        row.handler_id = handler_id

    def on_show_apps_usage(self, _button, row):
        """Return grid with games that uses this wine version"""
        runner = row.runner
        runner_version = "%s-%s" % (runner[self.COL_VER], runner[self.COL_ARCH])
        runner_games = get_games_by_runner(self.runner_name)
        apps = []
        for db_game in runner_games:
            if not db_game["installed"]:
                continue
            game = Game(db_game["id"])
            version = game.config.runner_config["version"]
            if version != runner_version:
                continue
            apps.append(game)

        dialog = ShowAppsDialog(_("Wine version usage"), self.get_toplevel(), runner_version, apps)
        dialog.run()

        dialog.destroy()

    def populate_store(self):
        """Return a ListStore populated with the runner versions"""
        version_usage = self.get_usage_stats()
        ordered = sorted(self.runner_info["versions"], key=RunnerInstallDialog.get_version_sort_key)
        for version_info in reversed(ordered):
            is_installed = os.path.exists(self.get_runner_path(version_info["version"], version_info["architecture"]))
            games_using = version_usage.get("%(version)s-%(architecture)s" % version_info)
            self.runner_store.append(
                [
                    version_info["version"], version_info["architecture"], version_info["url"], is_installed, 0,
                    len(games_using) if games_using else 0
                ]
            )

    @staticmethod
    def get_version_sort_key(version):
        """Generate a sorting key that sorts first on the version number part of the version,
        and which breaks the version number into its components, which are parsed as integers"""
        raw_version = version["version"]
        # Extract version numbers from the end of the version string.
        # We look for things like xx-7.2 or xxx-4.3-2. A leading period
        # will be part of the version, but a leading hyphen will not.
        match = re.search(r"^(.*?)\-?(\d[.\-\d]*)$", raw_version)
        if match:
            version_parts = [int(p) for p in match.group(2).replace("-", ".").split(".") if p]
            return version_parts, raw_version, version["architecture"]

        # If we fail to extract the version, we'll wind up sorting this one to the end.
        return [], raw_version, version["architecture"]

    def get_installed_versions(self):
        """List versions available locally"""
        if not os.path.exists(self.runner_directory):
            return set()
        return {
            tuple(p.rsplit("-", 1))
            for p in os.listdir(self.runner_directory)
            if "-" in p
        }

    def get_runner_path(self, version, arch):
        """Return the local path where the runner is/will be installed"""
        return os.path.join(self.runner_directory, "{}-{}".format(version, arch))

    def get_dest_path(self, row):
        """Return temporary path where the runners should be downloaded to"""
        return os.path.join(settings.CACHE_DIR, os.path.basename(row[self.COL_URL]))

    def on_cancel_install(self, widget, row):
        self.cancel_install(row)

    def cancel_install(self, row):
        """Cancel the installation of a runner version"""
        runner = row.runner
        self.installing[runner[self.COL_VER]].cancel()
        self.uninstall_runner(row)
        runner[self.COL_PROGRESS] = 0
        self.installing.pop(runner[self.COL_VER])
        self.update_listboxrow(row)
        row.install_progress.set_visible(False)

    def on_uninstall_runner(self, widget, row):
        self.uninstall_runner(row)

    def uninstall_runner(self, row):
        """Uninstall a runner version"""
        runner = row.runner
        version = runner[self.COL_VER]
        arch = runner[self.COL_ARCH]
        system.remove_folder(self.get_runner_path(version, arch))
        runner[self.COL_INSTALLED] = False
        if self.runner_name == "wine":
            logger.debug("Clearing wine version cache")
            from lutris.util.wine.wine import get_wine_versions

            get_wine_versions.cache_clear()
        self.update_listboxrow(row)

    def on_install_runner(self, _widget, row):
        self.install_runner(row)

    def install_runner(self, row):
        """Download and install a runner version"""
        runner = row.runner
        row.install_progress.set_fraction(0.0)
        dest_path = self.get_dest_path(runner)
        url = runner[self.COL_URL]
        if not url:
            ErrorDialog(_("Version %s is not longer available") % runner[self.COL_VER])
            return
        downloader = Downloader(url, dest_path, overwrite=True)
        GLib.timeout_add(100, self.get_progress, downloader, row)
        self.installing[runner[self.COL_VER]] = downloader
        downloader.start()
        self.update_listboxrow(row)

    def get_progress(self, downloader, row):
        """Update progress bar with download progress"""
        runner = row.runner
        if downloader.state == downloader.CANCELLED:
            return False
        if downloader.state == downloader.ERROR:
            self.cancel_install(row)
            return False
        row.install_progress.show()
        downloader.check_progress()
        percent_downloaded = downloader.progress_percentage
        if percent_downloaded >= 1:
            runner[self.COL_PROGRESS] = percent_downloaded
            row.install_progress.set_fraction(percent_downloaded / 100)
        else:
            runner[self.COL_PROGRESS] = 1
            row.install_progress.pulse()
            row.install_progress.set_text = _("Downloading…")
        if downloader.state == downloader.COMPLETED:
            runner[self.COL_PROGRESS] = 99
            row.install_progress.set_text = _("Extracting…")
            self.on_runner_downloaded(row)
            return False
        return True

    def progress_pulse(self, row):
        runner = row.runner
        row.install_progress.pulse()
        return not runner[self.COL_INSTALLED]

    def get_usage_stats(self):
        """Return the usage for each version"""
        runner_games = get_games_by_runner(self.runner_name)
        version_usage = defaultdict(list)
        for db_game in runner_games:
            if not db_game["installed"]:
                continue
            game = Game(db_game["id"])
            version = game.config.runner_config["version"]
            version_usage[version].append(db_game["id"])
        return version_usage

    def on_runner_downloaded(self, row):
        """Handler called when a runner version is downloaded"""
        runner = row.runner
        version = runner[self.COL_VER]
        architecture = runner[self.COL_ARCH]
        logger.debug("Runner %s for %s has finished downloading", version, architecture)
        src = self.get_dest_path(runner)
        dst = self.get_runner_path(version, architecture)
        GLib.timeout_add(100, self.progress_pulse, row)
        jobs.AsyncCall(self.extract, self.on_extracted, src, dst, row)

    @staticmethod
    def extract(src, dst, row):
        """Extract a runner archive to a destination"""
        extract_archive(src, dst)
        return src, row

    def on_extracted(self, row_info, error):
        """Called when a runner archive is extracted"""
        if error or not row_info:
            ErrorDialog(_("Failed to retrieve the runner archive"), parent=self)
            return
        src, row = row_info
        runner = row.runner
        os.remove(src)
        runner[self.COL_PROGRESS] = 0
        runner[self.COL_INSTALLED] = True
        self.installing.pop(runner[self.COL_VER])
        row.install_progress.set_text = ""
        row.install_progress.set_fraction(0.0)
        row.install_progress.hide()
        self.update_listboxrow(row)
        if self.runner_name == "wine":
            logger.debug("Clearing wine version cache")
            from lutris.util.wine.wine import get_wine_versions
            get_wine_versions.cache_clear()

    def on_destroy(self, _dialog, _data=None):
        """Override delete handler to prevent closing while downloads are active"""
        if self.installing:
            return True
        self.destroy()
        return True
