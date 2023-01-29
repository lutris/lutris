from copy import deepcopy
from gettext import gettext as _

from gi.repository import Gtk, GLib

from lutris.config import write_game_config
from lutris.database.games import add_game, get_games
from lutris.game import Game
from lutris.gui.dialogs import ModalDialog
from lutris.scanners.default_installers import DEFAULT_INSTALLERS
from lutris.scanners.tosec import clean_rom_name, guess_platform, search_tosec_by_md5
from lutris.services.lutris import download_lutris_media
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
from lutris.util.strings import slugify, gtk_safe
from lutris.util.system import get_md5_hash, get_md5_in_zip


class ImportGameDialog(ModalDialog):
    def __init__(self, files, parent=None) -> None:
        super().__init__(
            _("Import a game"),
            parent=parent,
            border_width=10
        )
        self.files = files
        self.progress_labels = {}
        self.checksum_labels = {}
        self.description_labels = {}
        self.category_labels = {}
        self.error_labels = {}
        self.platform = None
        self.set_size_request(480, 240)
        self.get_content_area().add(Gtk.Frame(
            shadow_type=Gtk.ShadowType.ETCHED_IN,
            child=self.get_file_labels_listbox(files)
        ))
        self.auto_launch_button = Gtk.CheckButton(_("Launch game"), visible=True, active=True)
        self.get_content_area().add(self.auto_launch_button)
        self.show_all()
        AsyncCall(self.search_checksums, self.search_result_finished)

    def get_file_labels_listbox(self, files):
        listbox = Gtk.ListBox(vexpand=True)
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        for file_path in files:
            row = Gtk.ListBoxRow()
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            vbox.set_margin_left(12)
            vbox.set_margin_right(12)

            description_label = Gtk.Label(halign=Gtk.Align.START)
            vbox.pack_start(description_label, True, True, 5)
            self.description_labels[file_path] = description_label

            file_path_label = Gtk.Label(file_path, halign=Gtk.Align.START, xalign=0)
            file_path_label.set_line_wrap(True)
            vbox.pack_start(file_path_label, True, True, 5)

            progress_label = Gtk.Label(halign=Gtk.Align.START)
            vbox.pack_start(progress_label, True, True, 5)
            self.progress_labels[file_path] = progress_label

            checksum_label = Gtk.Label(no_show_all=True, halign=Gtk.Align.START)
            vbox.pack_start(checksum_label, True, True, 5)
            self.checksum_labels[file_path] = checksum_label

            category_label = Gtk.Label(no_show_all=True, halign=Gtk.Align.START)
            vbox.pack_start(category_label, True, True, 5)
            self.category_labels[file_path] = category_label

            error_label = Gtk.Label(no_show_all=True, halign=Gtk.Align.START, xalign=0)
            error_label.set_line_wrap(True)
            vbox.pack_start(error_label, True, True, 5)
            self.error_labels[file_path] = error_label

            row.add(vbox)
            listbox.add(row)
        return listbox

    def game_launch(self, game):
        if self.auto_launch_button.get_active():
            game.emit("game-launch")
            self.destroy()
        else:
            logger.debug('Game not launched')

    def search_checksums(self):
        all_games = get_games()

        def find_game(filepath):
            for db_game in all_games:
                g = Game(db_game["id"])
                if not g.config:
                    continue
                for _key, value in g.config.game_config.items():
                    if value == filepath:
                        logger.debug("Found %s", g)
                        return g

        def show_progress(filepath, message):
            # It's not safe to directly update labels from a worker thread, so
            # this will do it on the GUI main thread instead.
            GLib.idle_add(lambda: self.progress_labels[filepath].set_markup("<i>%s</i>" % gtk_safe(message)))

        results = []
        for filename in self.files:
            try:
                show_progress(filename, _("Looking for installed game..."))
                game = find_game(filename)
                if game:
                    # Found a game to launch instead of installing, but we can't safely
                    # do this on this thread.
                    result = [{"name": game.name, "game": game, "roms": []}]
                else:
                    show_progress(filename, _("Calculating checksum..."))
                    if filename.lower().endswith(".zip"):
                        md5 = get_md5_in_zip(filename)
                    else:
                        md5 = get_md5_hash(filename)
                    show_progress(filename, _("Looking up checksum on Lutris.net..."))
                    result = search_tosec_by_md5(md5)
                    if not result:
                        raise RuntimeError(_("This ROM could not be identified."))
            except Exception as error:
                result = [{"error": error, "roms": []}]
            finally:
                show_progress(filename, "")

            for r in result:
                r["filename"] = filename
            results.append(result)
        return results

    def search_result_finished(self, results, error):
        if error:
            logger.error(error)
            return

        # If any selected game is already installed we will launch it
        # and install nothing
        for result in results:
            for rom_set in result:
                if "game" in rom_set:
                    self.game_launch(rom_set["game"])
                    return

        for result in results:
            for rom_set in result:
                filename = rom_set["filename"]
                try:
                    self.progress_labels[filename].hide()

                    if "error" in rom_set:
                        raise rom_set["error"]

                    for rom in rom_set["roms"]:
                        self.display_game_info(filename, rom_set, rom)
                        game_id = self.add_game(rom_set, filename)
                        game = Game(game_id)
                        game.emit("game-installed")
                        self.game_launch(game)
                        return
                except Exception as ex:
                    logger.exception(_("Failed to import a ROM: %s"), ex)
                    error_label = self.error_labels[filename]
                    error_label.set_markup(
                        "<span style=\"italic\" foreground=\"red\">%s</span>" % gtk_safe(str(ex)))
                    error_label.show()

    def display_game_info(self, filename, rom_set, rom):
        label = self.checksum_labels[filename]
        label.set_text(rom["md5"])
        label.show()
        label = self.description_labels[filename]
        label.set_markup("<b>%s</b>" % rom_set["name"])
        category = rom_set["category"]["name"]
        label = self.category_labels[filename]
        label.set_text(category)
        label.show()
        self.platform = guess_platform(rom_set)

        if not self.platform:
            raise RuntimeError(_("The platform '%s' is unknown to Lutris.") % category)

    def add_game(self, game, filepath):
        name = clean_rom_name(game["name"])
        logger.info("Installing %s", name)

        try:
            installer = deepcopy(DEFAULT_INSTALLERS[self.platform])
        except KeyError as error:
            raise RuntimeError(
                _("Lutris does not have a default installer for the '%s' platform.") % self.platform) from error

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
            configpath=configpath
        )
        download_lutris_media(slug)
        return game_id
