from copy import deepcopy
from gettext import gettext as _

from gi.repository import Gtk

from lutris.config import write_game_config
from lutris.database.games import add_game, get_games
from lutris.game import Game
from lutris.gui.dialogs import ModalDialog
from lutris.scanners.default_installers import DEFAULT_INSTALLERS
from lutris.scanners.tosec import clean_rom_name, guess_platform, search_tosec_by_md5
from lutris.services.lutris import download_lutris_media
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
from lutris.util.strings import slugify
from lutris.util.system import get_md5_hash, get_md5_in_zip


class ImportGameDialog(ModalDialog):
    def __init__(self, files, parent=None) -> None:
        super().__init__(
            _("Import a game"),
            parent=parent,
            border_width=10
        )
        self.files = files
        self.checksum_labels = {}
        self.description_labels = {}
        self.category_labels = {}
        self.file_hashes = {}
        self.files_by_hash = {}
        self.platform = None
        self.set_size_request(480, 220)
        self.get_content_area().add(self.add_file_labels(files))
        self.auto_launch_button = Gtk.CheckButton(_("Launch game"), visible=True, active=True)
        self.get_content_area().add(self.auto_launch_button)
        self.show_all()
        AsyncCall(self.search_checksums, self.search_result_finished)

    def add_file_labels(self, files):
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        for file_path in files:
            row = Gtk.ListBoxRow()
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            vbox.set_margin_left(12)

            description_label = Gtk.Label("")
            description_label.set_halign(Gtk.Align.START)
            vbox.pack_start(description_label, True, True, 5)
            self.description_labels[file_path] = description_label

            label = Gtk.Label(file_path)
            label.set_halign(Gtk.Align.START)
            vbox.pack_start(label, True, True, 5)

            checksum_label = Gtk.Label("")
            checksum_label.set_markup("<i>%s</i>" % _("Looking for installed game..."))
            checksum_label.set_halign(Gtk.Align.START)
            vbox.pack_start(checksum_label, True, True, 5)
            self.checksum_labels[file_path] = checksum_label

            category_label = Gtk.Label("")
            category_label.set_halign(Gtk.Align.START)
            vbox.pack_start(category_label, True, True, 5)
            self.category_labels[file_path] = category_label

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
        game_id = self.find_game(self.files[0])
        if game_id:
            self.game_launch(Game(game_id))
            return []

        results = []
        for filename in self.files:
            self.checksum_labels[filename].set_markup("<i>%s</i>" % _("Calculating checksum..."))
            if filename.lower().endswith(".zip"):
                md5 = get_md5_in_zip(filename)
            else:
                md5 = get_md5_hash(filename)
            self.file_hashes[filename] = md5
            self.files_by_hash[md5] = filename
            self.checksum_labels[filename].set_markup("<i>%s</i>" % _("Looking up checkum on Lutris.net..."))
            result = search_tosec_by_md5(md5)
            if not result:
                result = [{"name": "Not found", "category": {"name": ""}, "roms": [{"md5": md5}]}]
            results.append(result)
        return results

    def search_result_finished(self, results, error):
        if error:
            logger.error(error)
            return
        for result in results:
            for game in result:
                for rom in game["roms"]:
                    if rom["md5"] in self.files_by_hash:
                        self.display_game_info(game, rom)
                        if self.platform:
                            filename = self.files_by_hash[rom["md5"]]
                            game_id = self.add_game(game, filename)
                            game = Game(game_id)
                            game.emit("game-installed")
                            self.game_launch(game)
                        else:
                            logger.warning("Platform not found")
                        return

    def display_game_info(self, game, rom):
        filename = self.files_by_hash[rom["md5"]]
        label = self.checksum_labels[filename]
        label.set_text(rom["md5"])
        label = self.description_labels[filename]
        label.set_markup("<b>%s</b>" % game["name"])
        category = game["category"]["name"]
        label = self.category_labels[filename]
        label.set_text(category)
        self.platform = guess_platform(game)

    def add_game(self, game, filepath):
        name = clean_rom_name(game["name"])
        logger.info("Installing %s", name)
        installer = deepcopy(DEFAULT_INSTALLERS[self.platform])
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

    def find_game(self, filepath):
        for game in get_games():
            g = Game(game["id"])
            if not g.config:
                continue
            for _key, value in g.config.game_config.items():
                if value == filepath:
                    logger.debug("Found %s", g)
                    return g.id
