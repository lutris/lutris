from datetime import datetime
from gettext import gettext as _

from gi.repository import GObject, Gtk, Pango

from lutris import runners, services
from lutris.database.games import get_game_by_field, get_game_for_service
from lutris.game import Game
from lutris.gui.widgets.utils import get_link_button, get_pixbuf_for_game
from lutris.util.strings import gtk_safe


class GameBar(Gtk.Fixed):
    play_button_position = (12, 42)

    def __init__(self, db_game, game_actions, application):
        """Create the game bar with a database row"""
        super().__init__(visible=True)
        GObject.add_emission_hook(Game, "game-start", self.on_game_state_changed)
        GObject.add_emission_hook(Game, "game-started", self.on_game_state_changed)
        GObject.add_emission_hook(Game, "game-stopped", self.on_game_state_changed)
        GObject.add_emission_hook(Game, "game-updated", self.on_game_state_changed)
        GObject.add_emission_hook(Game, "game-removed", self.on_game_state_changed)
        GObject.add_emission_hook(Game, "game-installed", self.on_game_state_changed)

        self.set_margin_bottom(12)
        self.game_actions = game_actions
        self.db_game = db_game
        if db_game.get("service"):
            self.service = services.get_services()[db_game["service"]]()
        else:
            self.service = None
        game_id = None
        if "service_id" in db_game:
            self.appid = db_game["service_id"]
            game_id = db_game["id"]
        elif self.service:
            self.appid = db_game["appid"]
            if self.service.id == "lutris":
                game = get_game_by_field(self.appid, field="slug")
            else:
                game = get_game_for_service(self.service.id, self.appid)
            if game:
                game_id = game["id"]
        if game_id:
            self.game = application.get_game_by_id(game_id) or Game(game_id)
            game_actions.set_game(self.game)
        else:
            self.game = Game()
        self.game_name = db_game["name"]
        self.game_slug = db_game["slug"]
        self.update_view()

    def clear_view(self):
        """Clears all widgets from the container"""
        for child in self.get_children():
            child.destroy()

    def update_view(self):
        """Populate the view with widgets"""
        self.put(self.get_game_name_label(), 16, 8)
        x_offset = 140
        y_offset = 40
        if self.game.is_installed:
            self.put(self.get_runner_button(), x_offset, y_offset + 2)
            x_offset += 80
            self.put(self.get_platform_label(), x_offset, y_offset)
            x_offset += 120
        if self.game.lastplayed:
            self.put(self.get_last_played_label(), x_offset, y_offset)
            x_offset += 95
        if self.game.playtime:
            self.put(self.get_playtime_label(), x_offset, y_offset)

        self.play_button = self.get_play_button()
        self.put(self.play_button, self.play_button_position[0], self.play_button_position[1])

    def get_popover(self, buttons):
        """Return the popover widget containing a list of link buttons"""
        if not buttons:
            return None
        popover = Gtk.Popover()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, visible=True)

        for action in buttons:
            vbox.pack_end(buttons[action], False, False, 1)
        popover.add(vbox)
        popover.set_position(Gtk.PositionType.TOP)
        return popover

    def get_icon(self):
        """Return the game icon"""
        icon = Gtk.Image.new_from_pixbuf(get_pixbuf_for_game(self.game_slug, (32, 32)))
        icon.show()
        return icon

    def get_game_name_label(self):
        """Return the label with the game's title"""
        title_label = Gtk.Label(visible=True)
        title_label.set_markup("<span font_desc='16'><b>%s</b></span>" % gtk_safe(self.game_name))
        return title_label

    def get_runner_button(self):
        icon_name = self.game.runner.name + "-symbolic"
        runner_icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
        runner_icon.show()
        box = Gtk.HBox(visible=True)
        popover = self.get_popover(self.get_runner_buttons())
        if popover:
            runner_button = Gtk.Button(visible=True)
            runner_button.set_image(runner_icon)
            popover_button = Gtk.MenuButton(visible=True)
            popover_button.set_size_request(32, 32)
            popover_button.props.direction = Gtk.ArrowType.UP
            popover_button.set_popover(popover)
            runner_button.connect("clicked", lambda _x: popover_button.emit("clicked"))
            box.add(runner_button)
            box.add(popover_button)
            style_context = box.get_style_context()
            style_context.add_class("linked")
        else:
            runner_icon.set_margin_top(8)
            runner_icon.set_margin_left(48)
            box.add(runner_icon)
        return box

    def get_platform_label(self):
        platform_label = Gtk.Label(visible=True)
        platform_label.set_size_request(120, -1)
        platform_label.set_alignment(0, 0.5)
        platform = gtk_safe(self.game.platform)
        platform_label.set_tooltip_markup(platform)
        platform_label.set_markup("Platform:\n<b>%s</b>" % platform)
        platform_label.set_property("ellipsize", Pango.EllipsizeMode.END)
        return platform_label

    def get_playtime_label(self):
        """Return the label containing the playtime info"""
        playtime_label = Gtk.Label(visible=True)
        playtime_label.set_markup(_("Time played:\n<b>%s</b>") % self.game.formatted_playtime)
        return playtime_label

    def get_last_played_label(self):
        """Return the label containing the last played info"""
        last_played_label = Gtk.Label(visible=True)
        lastplayed = datetime.fromtimestamp(self.game.lastplayed)
        last_played_label.set_markup(_("Last played:\n<b>%s</b>") % lastplayed.strftime("%x"))
        return last_played_label

    def get_play_button(self):
        """Return the widget for install/play/stop and game config"""
        if not self.game.is_installed and self.service:
            button = Gtk.Button(visible=True)
            button.set_size_request(120, 36)
            button.set_label(_("Install"))
            button.connect("clicked", self.on_install_clicked)
            return button
        box = Gtk.HBox(visible=True)
        style_context = box.get_style_context()
        style_context.add_class("linked")
        button = Gtk.Button(visible=True)
        button.set_size_request(84, 32)
        popover_button = Gtk.MenuButton(visible=True)
        popover_button.set_size_request(32, 32)
        popover_button.props.direction = Gtk.ArrowType.UP
        popover_button.set_popover(self.get_popover(self.get_game_buttons()))
        if self.game.is_installed:
            if self.game.state == self.game.STATE_STOPPED:
                button.set_label(_("Play"))
                button.connect("clicked", self.game_actions.on_game_launch)
            elif self.game.state == self.game.STATE_LAUNCHING:
                button.set_label(_("Launching"))
                button.set_sensitive(False)
            else:
                button.set_label(_("Stop"))
                button.connect("clicked", self.game_actions.on_game_stop)
        else:
            button.set_label(_("Install"))
            button.connect("clicked", self.game_actions.on_install_clicked)
        box.add(button)
        box.add(popover_button)
        return box

    def get_game_buttons(self):
        """Return a dictionary of buttons to use in the panel"""
        displayed = self.game_actions.get_displayed_entries()
        buttons = {}
        for action in self.game_actions.get_game_actions():
            action_id, label, callback = action
            if action_id in ("play", "stop", "install"):
                continue
            button = get_link_button(label)
            if displayed.get(action_id):
                button.show()
            else:
                button.hide()
            buttons[action_id] = button
            button.connect("clicked", callback)
        return buttons

    def get_runner_buttons(self):
        buttons = {}
        if self.game.runner_name and self.game.is_installed:
            runner = runners.import_runner(self.game.runner_name)(self.game.config)
            for entry in runner.context_menu_entries:
                name, label, callback = entry
                button = get_link_button(label)
                button.show()
                button.connect("clicked", callback)
                buttons[name] = button
        return buttons

    def on_install_clicked(self, button):
        """Handler for installing service games"""
        self.service.install(self.db_game)

    def on_game_state_changed(self, game):
        """Handler called when the game has changed state"""
        if (
            game.id == self.game.id
            or game.appid == self.appid
        ):
            self.game = game
        else:
            return True
        self.clear_view()
        self.update_view()
        return True
