import json
from datetime import datetime
from gettext import gettext as _

from gi.repository import Gio, Gtk, Pango

from lutris import services
from lutris.config import LutrisConfig
from lutris.database.games import add_or_update, get_games
from lutris.game import Game
from lutris.gui.widgets.utils import get_link_button, get_pixbuf_for_game
from lutris.util.strings import gtk_safe


class GameBar(Gtk.Fixed):
    play_button_position = (12, 40)

    def __init__(self, db_game, game_actions):
        """Create the game bar with a database row"""
        super().__init__(visible=True)
        self.game_actions = game_actions
        self.db_game = db_game
        self.set_size_request(-1, 125)
        if db_game.get("service"):
            self.service = services.get_services()[db_game["service"]]()
        else:
            self.service = None
        game_id = None
        if "service_id" in db_game:  # Any field that isn't in service game. Not ideal
            game_id = db_game["id"]
        elif self.service:
            existing_games = get_games(filters={"service_id": db_game["appid"], "service": self.service.id})
            if existing_games:
                game_id = existing_games[0]["id"]
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
            if not self.service.online:
                play_button = self.get_play_button("Play")
                play_button.connect("clicked", self.on_play_clicked)
                self.put(play_button, self.play_button_position[0], self.play_button_position[1])

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

    def get_play_button(self, label):
        button = Gtk.Button(label, visible=True)
        button.get_style_context().add_class("play-button")
        button.set_size_request(115, 36)
        return button

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
                    button = self.get_play_button(label)
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
                position = self.play_button_position
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

    def on_play_clicked(self, button):
        """Handler for service games"""
        config_id = self.game_slug + "-" + self.service.id
        if self.service.id == "xdg":
            print(self.db_game)
            details = json.loads(self.db_game["details"])
            game_id = add_or_update(
                name=self.game_name,
                runner="linux",
                slug=self.game_slug,
                installed=1,
                configpath=config_id,
                installer_slug="desktopapp",
                service=self.service.id,
                service_id=self.db_game["appid"],
            )
            self.create_xdg_config(details, config_id)
            game = Game(game_id)
            application = Gio.Application.get_default()
            application.launch(game)

    def create_xdg_config(self, details, config_id):
        config = LutrisConfig(runner_slug="linux", game_config_id=config_id)
        config.raw_game_config.update(
            {
                "exe": details["exe"],
                "args": details["args"],
            }
        )
        config.raw_system_config.update({"disable_runtime": True})
        config.save()
