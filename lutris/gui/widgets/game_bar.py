from datetime import datetime
from gettext import gettext as _

from gi.repository import GObject, Gtk, Pango

from lutris import runners, services
from lutris.database.games import get_game_by_field, get_game_for_service
from lutris.game import Game
from lutris.gui.widgets.utils import get_link_button
from lutris.util.strings import gtk_safe


class GameBar(Gtk.Box):
    def __init__(self, db_game, game_actions, application):
        """Create the game bar with a database row"""
        super().__init__(orientation=Gtk.Orientation.VERTICAL, visible=True,
                         margin_top=12,
                         margin_left=12,
                         margin_bottom=12,
                         margin_right=12,
                         spacing=6)
        GObject.add_emission_hook(Game, "game-start", self.on_game_state_changed)
        GObject.add_emission_hook(Game, "game-started", self.on_game_state_changed)
        GObject.add_emission_hook(Game, "game-stopped", self.on_game_state_changed)
        GObject.add_emission_hook(Game, "game-updated", self.on_game_state_changed)
        GObject.add_emission_hook(Game, "game-removed", self.on_game_state_changed)
        GObject.add_emission_hook(Game, "game-installed", self.on_game_state_changed)

        self.set_margin_bottom(12)
        self.game_actions = game_actions
        self.db_game = db_game
        self.service = None
        if db_game.get("service"):
            try:
                self.service = services.SERVICES[db_game["service"]]()
            except KeyError:
                pass

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
        else:
            self.game = Game()
            self.game.name = db_game["name"]
            self.game.slug = db_game["slug"]
            self.game.appid = self.appid
            self.game.service = self.service.id if self.service else None
        game_actions.set_game(self.game)
        self.update_view()

    def clear_view(self):
        """Clears all widgets from the container"""
        for child in self.get_children():
            child.destroy()

    def update_view(self):
        """Populate the view with widgets"""
        game_label = self.get_game_name_label()
        game_label.set_halign(Gtk.Align.START)
        self.pack_start(game_label, False, False, 0)

        hbox = Gtk.Box(Gtk.Orientation.HORIZONTAL, spacing=6)
        self.pack_start(hbox, False, False, 0)

        self.play_button = self.get_play_button()
        hbox.pack_start(self.play_button, False, False, 0)

        if self.game.is_installed:
            hbox.pack_start(self.get_runner_button(), False, False, 0)
            hbox.pack_start(self.get_platform_label(), False, False, 0)
        if self.game.lastplayed:
            hbox.pack_start(self.get_last_played_label(), False, False, 0)
        if self.game.playtime:
            hbox.pack_start(self.get_playtime_label(), False, False, 0)
        hbox.show_all()

    def get_popover(self, buttons, parent):
        """Return the popover widget containing a list of link buttons"""
        if not buttons:
            return None
        popover = Gtk.Popover()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, visible=True)

        for action in buttons:
            vbox.pack_end(buttons[action], False, False, 1)
        popover.add(vbox)
        popover.set_position(Gtk.PositionType.TOP)
        popover.set_constrain_to(Gtk.PopoverConstraint.NONE)
        popover.set_relative_to(parent)
        return popover

    def get_game_name_label(self):
        """Return the label with the game's title"""
        title_label = Gtk.Label(visible=True)
        title_label.set_ellipsize(Pango.EllipsizeMode.END)
        title_label.set_markup("<span font_desc='16'><b>%s</b></span>" % gtk_safe(self.game.name))
        return title_label

    def get_runner_button(self):
        icon_name = self.game.runner.name + "-symbolic"
        runner_icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
        runner_icon.show()
        box = Gtk.HBox(visible=True)
        runner_button = Gtk.Button(visible=True)
        popover = self.get_popover(self.get_runner_buttons(), runner_button)
        if popover:
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
            runner_icon.set_margin_left(49)
            runner_icon.set_margin_right(6)
            box.add(runner_icon)
        return box

    def get_platform_label(self):
        platform_label = Gtk.Label(visible=True)
        platform_label.set_size_request(120, -1)
        platform_label.set_alignment(0, 0.5)
        platform = gtk_safe(self.game.platform)
        platform_label.set_tooltip_markup(platform)
        platform_label.set_markup(_("Platform:\n<b>%s</b>") % platform)
        platform_label.set_property("ellipsize", Pango.EllipsizeMode.END)
        return platform_label

    def get_playtime_label(self):
        """Return the label containing the playtime info"""
        playtime_label = Gtk.Label(visible=True)
        playtime_label.set_size_request(120, -1)
        playtime_label.set_alignment(0, 0.5)
        playtime_label.set_markup(_("Time played:\n<b>%s</b>") % self.game.formatted_playtime)
        return playtime_label

    def get_last_played_label(self):
        """Return the label containing the last played info"""
        last_played_label = Gtk.Label(visible=True)
        last_played_label.set_size_request(120, -1)
        last_played_label.set_alignment(0, 0.5)
        lastplayed = datetime.fromtimestamp(self.game.lastplayed)
        last_played_label.set_markup(_("Last played:\n<b>%s</b>") % lastplayed.strftime("%x"))
        return last_played_label

    def get_popover_button(self):
        """Return the popover button+menu for the Play button"""
        popover_button = Gtk.MenuButton(visible=True)
        popover_button.set_size_request(32, 32)
        popover_button.props.direction = Gtk.ArrowType.UP

        return popover_button

    def get_popover_box(self):
        """Return a container for a button + a popover button attached to it"""
        box = Gtk.HBox(visible=True)
        style_context = box.get_style_context()
        style_context.add_class("linked")
        return box

    def get_locate_installed_game_button(self):
        """Return a button to locate an existing install"""
        button = get_link_button("Locate installed game")
        button.show()
        button.connect("clicked", self.game_actions.on_locate_installed_game, self.game)
        return {"locate": button}

    def get_play_button(self):
        """Return the widget for install/play/stop and game config"""
        button = Gtk.Button(visible=True)
        button.set_size_request(120, 32)
        box = self.get_popover_box()
        popover_button = self.get_popover_button()
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
            if self.service:
                if self.service.local:
                    # Local services don't show an install dialog, they can be launched directly
                    button.set_label(_("Play"))
                if self.service.drm_free:
                    button.set_size_request(84, 32)
                    box.add(button)
                    popover = self.get_popover(self.get_locate_installed_game_button(), popover_button)
                    popover_button.set_popover(popover)
                    box.add(popover_button)
                    return box
                return button
        button.set_size_request(84, 32)
        box.add(button)
        popover = self.get_popover(self.get_game_buttons(), popover_button)
        popover_button.set_popover(popover)
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
            button.connect("clicked", self.on_link_button_clicked, callback)
        return buttons

    def get_runner_buttons(self):
        buttons = {}
        if self.game.runner_name and self.game.is_installed:
            runner = runners.import_runner(self.game.runner_name)(self.game.config)
            for entry in runner.context_menu_entries:
                name, label, callback = entry
                button = get_link_button(label)
                button.show()
                button.connect("clicked", self.on_link_button_clicked, callback)
                buttons[name] = button
        return buttons

    def on_link_button_clicked(self, button, callback):
        """Callback for link buttons. Closes the popover then runs the actual action"""
        popover = button.get_parent().get_parent()
        popover.popdown()
        callback(button)

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
