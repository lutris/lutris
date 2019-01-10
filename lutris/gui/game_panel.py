"""Game panel"""
from datetime import datetime
from gi.repository import Gtk, Pango
from lutris.gui.widgets.utils import get_pixbuf_for_panel, get_pixbuf_for_game


class GamePanel(Gtk.Fixed):
    """Panel allowing users to interact with a game"""
    def __init__(self, game_actions):
        self.game_actions = game_actions
        self.game = game_actions.game

        super().__init__()
        self.set_size_request(320, -1)
        self.show()

        self.put(self.get_background(), 0, 0)
        self.put(self.get_icon(), 12, 16)
        self.put(self.get_title_label(), 50, 20)
        if self.game.is_installed:
            self.put(self.get_runner_label(), 12, 64)
        if self.game.playtime:
            self.put(self.get_playtime_label(), 12, 86)
        if self.game.lastplayed:
            self.put(self.get_last_played_label(), 12, 108)

        self.place_buttons(self.get_buttons(), 145)

    def get_background(self):
        """Return the background image for the panel"""
        image = Gtk.Image.new_from_pixbuf(get_pixbuf_for_panel(self.game.slug))
        image.show()
        return image

    def get_icon(self):
        """Return the game icon"""
        icon = Gtk.Image.new_from_pixbuf(get_pixbuf_for_game(self.game.slug, "icon"))
        icon.show()
        return icon

    def get_title_label(self):
        """Return the label with the game's title"""
        title_label = Gtk.Label()
        title_label.set_markup("<span font_desc='16'>%s</span>" % self.game.name)
        title_label.set_ellipsize(Pango.EllipsizeMode.END)
        title_label.set_size_request(256, -1)
        title_label.set_alignment(0, 0.5)
        title_label.set_justify(Gtk.Justification.LEFT)
        title_label.show()
        return title_label

    def get_runner_label(self):
        """Return the label containing the runner info"""
        runner_label = Gtk.Label()
        runner_label.show()
        runner_label.set_markup("For <b>%s</b>, runs with %s" % (self.game.platform, self.game.runner.name))
        return runner_label

    def get_playtime_label(self):
        """Return the label containing the playtime info"""
        playtime_label = Gtk.Label()
        playtime_label.show()
        playtime_label.set_markup("Time played: <b>%s</b>" % self.game.formatted_playtime)
        return playtime_label

    def get_last_played_label(self):
        """Return the label containing the last played info"""
        last_played_label = Gtk.Label()
        last_played_label.show()
        lastplayed = datetime.fromtimestamp(self.game.lastplayed)
        last_played_label.set_markup("Last played: <b>%s</b>" % lastplayed.strftime("%Y/%m/%d"))
        return last_played_label

    def get_buttons(self):
        displayed = self.game_actions.get_displayed_entries()
        disabled_entries = self.game_actions.get_disabled_entries()
        icon_map = {
            "stop": "media-playback-stop-symbolic",
            "play": "media-playback-start-symbolic",
            "configure": "emblem-system-symbolic",
            "browse": "system-file-manager-symbolic",
        }
        buttons = {}
        for action in self.game_actions.get_game_actions():
            action_id, label, callback = action
            if action_id in icon_map:
                button = Gtk.Button.new_from_icon_name(
                    icon_map[action_id], Gtk.IconSize.MENU
                )
                button.set_tooltip_text(label)
            else:
                button = Gtk.Button(label)
                button.set_size_request(220, 24)
            button.connect("clicked", callback)
            if displayed.get(action_id):
                button.show()
            if disabled_entries.get(action_id):
                button.set_sensitive(False)
            buttons[action_id] = button
        return buttons

    def place_buttons(self, buttons, base_height):
        placed_buttons = set()
        menu_buttons = {}  # Move create and remove desktop and menu shortcuts out of the way
        for action_id, button in buttons.items():
            position = None
            if action_id in ("play", "stop"):
                position = (12, base_height)
            if action_id == "configure":
                position = (56, base_height)
            if action_id == "browse":
                position = (100, base_height)
            if action_id == "show_logs":
                position = (140, base_height)
            if action_id == "execute-script":
                position = (12, base_height + 32)

            current_y = base_height + 100
            if action_id in ("install", "remove"):
                position = (50, current_y)
            if action_id in ("add", "install_more"):
                position = (50, current_y + 40)
            if action_id == "view":
                position = (50, current_y + 80)
            if action_id in ("desktop-shortcut", "rm-desktop-shortcut",
                             "menu-shortcut", "rm-menu-shortcut"):
                menu_buttons[action_id] = button
                placed_buttons.add(action_id)

            if position:
                self.put(button, position[0], position[1])
                placed_buttons.add(action_id)
            # TODO place menu buttons
        for action in set(buttons.keys()).difference(placed_buttons):
            print(action)
