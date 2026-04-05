from collections import OrderedDict
from copy import deepcopy
from gettext import gettext as _

from gi.repository import Gio, GLib, Gtk

from lutris.config import write_game_config
from lutris.database.games import add_game
from lutris.game import GAME_INSTALLED, GAME_UPDATED, Game
from lutris.gui.dialogs import ModelessDialog
from lutris.scanners.default_installers import DEFAULT_INSTALLERS
from lutris.scanners.tosec import clean_rom_name, guess_platform, search_tosec_by_md5
from lutris.services.lutris import download_lutris_media
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
from lutris.util.path_cache import get_path_cache
from lutris.util.strings import gtk_safe, slugify
from lutris.util.system import get_md5_hash, get_md5_in_zip


class ImportGameDialog(ModelessDialog):
    def __init__(self, files, parent=None) -> None:
        super().__init__(_("Import a game"), parent=parent, border_width=10)
        self.files = files
        self.progress_labels = {}
        self.checksum_labels = {}
        self.description_labels = {}
        self.category_labels = {}
        self.error_labels = {}
        self.launch_buttons = {}
        self.platform = None
        self.search_call = None
        self.set_size_request(500, 560)

        scrolledwindow = Gtk.ScrolledWindow(child=self.get_file_labels_listbox(files))
        scrolledwindow.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        frame = Gtk.Frame(child=scrolledwindow)
        frame.set_hexpand(True)
        frame.set_vexpand(True)
        frame.set_margin_top(6)
        frame.set_margin_bottom(6)
        self.get_content_area().append(frame)

        self.close_button = self.add_button(_("_Stop"), Gtk.ResponseType.CANCEL)
        self.search_call = AsyncCall(self.search_checksums, self.search_result_finished)

    def on_response(self, dialog, response: Gtk.ResponseType) -> None:
        if response in (Gtk.ResponseType.CLOSE, Gtk.ResponseType.CANCEL, Gtk.ResponseType.DELETE_EVENT):
            if self.search_call:
                self.search_call.stop_request.set()
                return  # don't actually close the dialog

        super().on_response(dialog, response)

    def get_file_labels_listbox(self, files):
        listbox = Gtk.ListBox(vexpand=True)
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        for file_path in files:
            row = Gtk.ListBoxRow()
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            hbox.set_margin_start(12)
            hbox.set_margin_end(12)

            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

            description_label = Gtk.Label(halign=Gtk.Align.START)
            description_label.set_hexpand(True)
            description_label.set_vexpand(True)
            description_label.set_margin_top(5)
            description_label.set_margin_bottom(5)
            vbox.append(description_label)
            self.description_labels[file_path] = description_label

            file_path_label = Gtk.Label(label=file_path, halign=Gtk.Align.START, xalign=0)
            file_path_label.set_wrap(True)
            file_path_label.set_hexpand(True)
            file_path_label.set_vexpand(True)
            file_path_label.set_margin_top(5)
            file_path_label.set_margin_bottom(5)
            vbox.append(file_path_label)

            progress_label = Gtk.Label(halign=Gtk.Align.START)
            progress_label.set_hexpand(True)
            progress_label.set_vexpand(True)
            progress_label.set_margin_top(5)
            progress_label.set_margin_bottom(5)
            vbox.append(progress_label)
            self.progress_labels[file_path] = progress_label

            checksum_label = Gtk.Label(halign=Gtk.Align.START, visible=False)
            checksum_label.set_hexpand(True)
            checksum_label.set_vexpand(True)
            checksum_label.set_margin_top(5)
            checksum_label.set_margin_bottom(5)
            vbox.append(checksum_label)
            self.checksum_labels[file_path] = checksum_label

            category_label = Gtk.Label(halign=Gtk.Align.START, visible=False)
            category_label.set_hexpand(True)
            category_label.set_vexpand(True)
            category_label.set_margin_top(5)
            category_label.set_margin_bottom(5)
            vbox.append(category_label)
            self.category_labels[file_path] = category_label

            error_label = Gtk.Label(halign=Gtk.Align.START, xalign=0, visible=False)
            error_label.set_wrap(True)
            error_label.set_hexpand(True)
            error_label.set_vexpand(True)
            error_label.set_margin_top(5)
            error_label.set_margin_bottom(5)
            vbox.append(error_label)
            self.error_labels[file_path] = error_label

            vbox.set_hexpand(True)
            vbox.set_vexpand(True)
            hbox.append(vbox)

            launch_button = Gtk.Button(label=_("Launch"), valign=Gtk.Align.CENTER, sensitive=False)
            hbox.append(launch_button)
            self.launch_buttons[file_path] = launch_button

            row.set_child(hbox)
            listbox.append(row)
        return listbox

    @property
    def search_stopping(self):
        return self.search_call and self.search_call.stop_request.is_set()

    def search_checksums(self):
        game_path_cache = get_path_cache()

        def show_progress(filepath, message):
            # It's not safe to directly update labels from a worker thread, so
            # this will do it on the GUI main thread instead.
            GLib.idle_add(lambda: self.progress_labels[filepath].set_markup("<i>%s</i>" % gtk_safe(message)))

        def get_existing_game(filepath):
            for game_id, game_path in game_path_cache.items():
                if game_path == filepath:
                    return Game(game_id)

            return None

        def search_single(filepath):
            existing_game = get_existing_game(filepath)
            if existing_game:
                # Found a game to launch instead of installing, but we can't safely
                # do this on this thread, so we return the game and handle it later.
                return [{"name": existing_game.name, "game": existing_game, "roms": []}]
            show_progress(filepath, _("Calculating checksum..."))
            if filepath.lower().endswith(".zip"):
                md5 = get_md5_in_zip(filepath)
            else:
                md5 = get_md5_hash(filepath)

            if self.search_stopping:
                return None

            show_progress(filename, _("Looking up checksum on Lutris.net..."))
            result = search_tosec_by_md5(md5)
            if not result:
                raise RuntimeError(_("This ROM could not be identified."))
            return result

        results = OrderedDict()  # must preserve order, on any Python version
        for filename in self.files:
            if self.search_stopping:
                break

            try:
                show_progress(filename, _("Looking for installed game..."))
                result = search_single(filename)
            except Exception as error:
                result = [{"error": error, "roms": []}]
            finally:
                show_progress(filename, "")

            if result:
                results[filename] = result

        return results

    def search_result_finished(self, results, error):
        self.search_call = None
        self.close_button.set_label(_("_Close"))

        if error:
            logger.error(error)
            return

        for filename, result in results.items():
            for rom_set in result:
                if self.import_rom(rom_set, filename):
                    break

    def import_rom(self, rom_set, filename):
        """Tries to install a specific ROM, or reports failure. Returns True if
        successful, False if not."""
        try:
            self.progress_labels[filename].set_visible(False)

            if "error" in rom_set:
                raise rom_set["error"]

            if "game" in rom_set:
                game = rom_set["game"]
                self.display_existing_game_info(filename, game)
                self.enable_game_launch(filename, game)
                return True

            for rom in rom_set["roms"]:
                self.display_new_game_info(filename, rom_set, rom["md5"])
                game_id = self.add_game(rom_set, filename)
                game = Game(game_id)
                GAME_INSTALLED.fire(game)
                GAME_UPDATED.fire(game)
                self.enable_game_launch(filename, game)
                return True
        except Exception as ex:
            logger.exception(_("Failed to import a ROM: %s"), ex)
            error_label = self.error_labels[filename]
            error_label.set_markup('<span style="italic" foreground="red">%s</span>' % gtk_safe(str(ex)))
            error_label.set_visible(True)

        return False

    def enable_game_launch(self, filename, game):
        launch_button = self.launch_buttons[filename]
        launch_button.set_sensitive(True)
        launch_button.connect("clicked", self.on_launch_clicked, game)

    def on_launch_clicked(self, _button, game):
        # We can't use this window as the delegate because we
        # are destroying it.
        application = Gio.Application.get_default()
        game.launch(application.launch_ui_delegate)
        self.destroy()

    def display_existing_game_info(self, filename, game):
        label = self.checksum_labels[filename]
        label.set_markup("<i>%s</i>" % _("Game already installed in Lutris"))
        label.set_visible(True)
        label = self.description_labels[filename]
        label.set_markup("<b>%s</b>" % game.name)
        category = game.platform
        label = self.category_labels[filename]
        label.set_text(category)
        label.set_visible(True)

    def display_new_game_info(self, filename, rom_set, checksum):
        label = self.checksum_labels[filename]
        label.set_text(checksum)
        label.set_visible(True)
        label = self.description_labels[filename]
        label.set_markup("<b>%s</b>" % rom_set["name"])
        category = rom_set["category"]["name"]
        label = self.category_labels[filename]
        label.set_text(category)
        label.set_visible(True)
        self.platform = guess_platform(rom_set)

        if not self.platform:
            raise RuntimeError(_("The platform '%s' is unknown to Lutris.") % category)

    def add_game(self, rom_set, filepath):
        name = clean_rom_name(rom_set["name"])
        logger.info("Installing %s", name)

        try:
            installer = deepcopy(DEFAULT_INSTALLERS[self.platform])
        except KeyError as error:
            raise RuntimeError(
                _("Lutris does not have a default installer for the '%s' platform.") % self.platform
            ) from error

        for key, value in installer["game"].items():
            if value == "rom":
                installer["game"][key] = filepath
        slug = slugify(name)
        configpath = write_game_config(slug, installer)
        game_id = add_game(
            name=name,
            runner=installer["runner"],
            slug=slug,
            directory="",
            installed=1,
            installer_slug="%s-%s" % (slug, installer["runner"]),
            configpath=configpath,
        )
        download_lutris_media(slug)
        return game_id
