from datetime import datetime
from gettext import gettext as _

from gi.repository import Gtk, Pango

from lutris.game import Game
from lutris.gui.widgets.utils import get_link_button, get_pixbuf_for_game
from lutris.util.strings import gtk_safe


class GameBar(Gtk.Fixed):
    def __init__(self, db_game, game_actions):
        """Create the game bar with a database row"""
        super().__init__(visible=True)
        self.game_actions = game_actions
        self.set_size_request(-1, 125)
        self.service = db_game["service"]
        if db_game.get("directory"):  # Any field that isn't in service game. Not ideal
            game_id = db_game["id"]
        else:
            game_id = None
        if game_id:
            self.game = Game(game_id)
        else:
            self.game = None
        self.game_name = db_game["name"]
        self.game_slug = db_game["slug"]
        self.put(self.get_game_name_label(), 16, 8)
        if self.game:
            game_actions.set_game(self.game)
            x_offset = 150
            y_offset = 38
            line_size = 24
            if self.game.is_installed:
                self.put(self.get_runner_label(), x_offset, y_offset)
                y_offset += line_size
            if self.game.playtime:
                self.put(self.get_playtime_label(), x_offset, y_offset)
                y_offset += line_size
            if self.game.lastplayed:
                self.put(self.get_last_played_label(), x_offset, y_offset)
            self.place_buttons()
        else:
            print(db_game)

    def get_icon(self):
        """Return the game icon"""
        icon = Gtk.Image.new_from_pixbuf(get_pixbuf_for_game(self.game_slug, (32, 32)))
        icon.show()
        return icon

    def get_game_name_label(self):
        """Return the label with the game's title"""
        title_label = Gtk.Label()
        title_label.set_markup("<span font_desc='16'><b>%s</b></span>" % gtk_safe(self.game_name))
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
        playtime_label = Gtk.Label(visible=True)
        playtime_label.set_markup(_("Time played: <b>%s</b>") % self.game.formatted_playtime)
        return playtime_label

    def get_last_played_label(self):
        """Return the label containing the last played info"""
        last_played_label = Gtk.Label(visible=True)
        lastplayed = datetime.fromtimestamp(self.game.lastplayed)
        last_played_label.set_markup(_("Last played: <b>%s</b>") % lastplayed.strftime("%x"))
        return last_played_label

    def get_buttons(self):
        """Return a dictionary of buttons to use in the panel"""
        displayed = self.game_actions.get_displayed_entries()
        icon_map = {
            "configure": "preferences-system-symbolic",
            "browse": "system-file-manager-symbolic",
            "show_logs": "utilities-terminal-symbolic",
            "remove": "user-trash-symbolic",
        }
        buttons = {}
        for action in self.game_actions.get_game_actions():
            action_id, label, callback = action
            if action_id in icon_map:
                button = Gtk.Button.new_from_icon_name(icon_map[action_id], Gtk.IconSize.MENU)
                button.set_tooltip_text(label)
                button.props.relief = Gtk.ReliefStyle.NONE
                button.set_size_request(24, 24)
            else:
                if action_id in ("play", "stop", "install"):
                    button = Gtk.Button(label)
                    button.get_style_context().add_class("play-button")
                    button.set_size_request(115, 36)
                else:
                    button = get_link_button(label)
            if displayed.get(action_id):
                button.show()
            else:
                button.hide()
            buttons[action_id] = button
            button.connect("clicked", callback)
        return buttons

    def place_buttons(self):
        """Places all appropriate buttons in the panel"""
        base_height = 12
        buttons = self.get_buttons()
        icon_offset = 6
        icon_width = 24
        icon_x_start = 8
        icons_y_offset = 70

        # buttons_x_offset = 28
        # extra_button_start = 80  # Y position for runner actions
        # extra_button_index = 0
        for action_id, button in buttons.items():
            position = None
            if action_id in ("play", "stop", "install"):
                position = (12, 40)
            if action_id == "configure":
                position = (icon_x_start, base_height + icons_y_offset)
            if action_id == "browse":
                position = (
                    icon_x_start + icon_offset + icon_width,
                    base_height + icons_y_offset,
                )
            if action_id == "show_logs":
                position = (
                    icon_x_start + icon_offset * 2 + icon_width * 2,
                    base_height + icons_y_offset,
                )
            if action_id == "remove":
                position = (
                    icon_x_start + icon_offset * 3 + icon_width * 3,
                    base_height + icons_y_offset,
                )

            if position:
                self.put(button, position[0], position[1])
