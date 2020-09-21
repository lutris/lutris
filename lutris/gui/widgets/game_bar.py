from datetime import datetime
from gettext import gettext as _

from gi.repository import Gtk, Pango

from lutris.game import Game
from lutris.gui.widgets.utils import get_pixbuf_for_game
from lutris.util.strings import gtk_safe


class GameBar(Gtk.Fixed):
    def __init__(self, db_game):
        """Create the game bar with a database row"""
        super().__init__(visible=True)
        self.set_size_request(-1, 64)
        if "service" in db_game:
            self.service = db_game["service"]
            print(db_game)
            game_id = None
        else:
            self.service = None
            game_id = db_game["id"]

        if game_id:
            self.game = Game(game_id)
        else:
            self.game = None
        self.game_name = db_game["name"]
        self.game_slug = db_game["slug"]
        # self.put(self.get_icon(), 12, 30)
        self.put(self.get_game_name_label(), 64, 12)
        if self.game:
            print("bliblibliblbil")
            if self.game.is_installed:
                self.put(self.get_runner_label(), 120, 20)
            if self.game.playtime:
                self.put(self.get_playtime_label(), 120, 40)
            if self.game.lastplayed:
                self.put(self.get_last_played_label(), 230, 20)

    def get_icon(self):
        """Return the game icon"""
        icon = Gtk.Image.new_from_pixbuf(get_pixbuf_for_game(self.game_slug, "icon"))
        icon.show()
        return icon

    def get_game_name_label(self):
        """Return the label with the game's title"""
        title_label = Gtk.Label()
        title_label.set_markup("<span font_desc='12'><b>%s</b></span>" % gtk_safe(self.game_name))
        title_label.set_ellipsize(Pango.EllipsizeMode.END)
        title_label.set_size_request(426, -1)
        title_label.set_alignment(0, 0.5)
        title_label.set_justify(Gtk.Justification.LEFT)
        title_label.show()
        return title_label

    def get_runner_label(self):
        """Return the label containing the runner info"""
        runner_icon = Gtk.Image.new_from_icon_name(
            self.game.runner.name.lower().replace(" ", "") + "-symbolic",
            Gtk.IconSize.MENU,
        )
        runner_icon.show()
        runner_label = Gtk.Label()
        runner_label.show()
        runner_label.set_markup("<b>%s</b>" % gtk_safe(self.game.platform))
        runner_box = Gtk.Box(spacing=6)
        runner_box.add(runner_icon)
        runner_box.add(runner_label)
        runner_box.show()
        return runner_box

    def get_playtime_label(self):
        """Return the label containing the playtime info"""
        playtime_label = Gtk.Label()
        playtime_label.show()
        playtime_label.set_markup(_("Time played: <b>%s</b>") % self.game.formatted_playtime)
        return playtime_label

    def get_last_played_label(self):
        """Return the label containing the last played info"""
        last_played_label = Gtk.Label()
        last_played_label.show()
        lastplayed = datetime.fromtimestamp(self.game.lastplayed)
        last_played_label.set_markup(_("Last played: <b>%s</b>") % lastplayed.strftime("%x"))
        return last_played_label
