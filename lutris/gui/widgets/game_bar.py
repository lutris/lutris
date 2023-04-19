from datetime import datetime
from gettext import gettext as _

from gi.repository import GObject, Gtk, Pango

from lutris import runners, services
from lutris.database.games import get_game_for_service
from lutris.game import Game
from lutris.game_actions import GameActions
from lutris.util.strings import gtk_safe


class GameBar(Gtk.Box):
    def __init__(self, db_game, application, window):
        """Create the game bar with a database row"""
        super().__init__(orientation=Gtk.Orientation.VERTICAL, visible=True,
                         margin_top=12,
                         margin_left=12,
                         margin_bottom=12,
                         margin_right=12,
                         spacing=6)

        self.application = application
        self.window = window

        self.game_start_hook_id = GObject.add_emission_hook(Game, "game-start", self.on_game_state_changed)
        self.game_started_hook_id = GObject.add_emission_hook(Game, "game-started", self.on_game_state_changed)
        self.game_stopped_hook_id = GObject.add_emission_hook(Game, "game-stopped", self.on_game_state_changed)
        self.game_updated_hook_id = GObject.add_emission_hook(Game, "game-updated", self.on_game_state_changed)
        self.game_removed_hook_id = GObject.add_emission_hook(Game, "game-removed", self.on_game_state_changed)
        self.game_installed_hook_id = GObject.add_emission_hook(Game, "game-installed", self.on_game_state_changed)
        self.connect("destroy", self.on_destroy)

        self.set_margin_bottom(12)
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
            game = get_game_for_service(self.service.id, self.appid)
            if game:
                game_id = game["id"]
        if game_id:
            self.game = application.get_running_game_by_id(game_id) or Game(game_id)
        else:
            self.game = Game.create_empty_service_game(db_game, self.service)
        self.update_view()

    def on_destroy(self, widget):
        GObject.remove_emission_hook(Game, "game-start", self.game_start_hook_id)
        GObject.remove_emission_hook(Game, "game-started", self.game_started_hook_id)
        GObject.remove_emission_hook(Game, "game-stopped", self.game_stopped_hook_id)
        GObject.remove_emission_hook(Game, "game-updated", self.game_updated_hook_id)
        GObject.remove_emission_hook(Game, "game-removed", self.game_removed_hook_id)
        GObject.remove_emission_hook(Game, "game-installed", self.game_installed_hook_id)
        return True

    def clear_view(self):
        """Clears all widgets from the container"""
        for child in self.get_children():
            child.destroy()

    def update_view(self):
        """Populate the view with widgets"""
        game_actions = GameActions(self.game, window=self.window, application=self.application)

        game_label = self.get_game_name_label()
        game_label.set_halign(Gtk.Align.START)
        self.pack_start(game_label, False, False, 0)

        hbox = Gtk.Box(Gtk.Orientation.HORIZONTAL, spacing=6)
        self.pack_start(hbox, False, False, 0)

        self.play_button = self.get_play_button(game_actions)
        hbox.pack_start(self.play_button, False, False, 0)

        if self.game.is_installed:
            hbox.pack_start(self.get_runner_button(), False, False, 0)
            hbox.pack_start(self.get_platform_label(), False, False, 0)
        if self.game.lastplayed:
            hbox.pack_start(self.get_last_played_label(), False, False, 0)
        if self.game.playtime:
            hbox.pack_start(self.get_playtime_label(), False, False, 0)
        hbox.show_all()

    @staticmethod
    def get_popover_box(primary_button, popover_buttons, primary_opens_popover=False):
        """Creates a box that contains a primary button and a second button that
        opens a popover with the popover_buttons in it; these have a linked
        style so this looks like a single button.

        If primary_opens_popover is true, this method also handled the 'clicked' signal
        of the primary button to trigger the popover as well."""

        def get_popover(parent):
            # Creates the popover widget containing the list of link buttons
            pop = Gtk.Popover()
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, visible=True)
            vbox.set_border_width(9)
            vbox.set_spacing(3)

            for button in popover_buttons.values():
                vbox.pack_end(button, False, False, 0)

            pop.add(vbox)
            pop.set_position(Gtk.PositionType.TOP)
            pop.set_constrain_to(Gtk.PopoverConstraint.NONE)
            pop.set_relative_to(parent)
            return pop

        box = Gtk.HBox(visible=True)
        style_context = box.get_style_context()
        style_context.add_class("linked")

        box.pack_start(primary_button, False, False, 0)

        if popover_buttons:
            popover_button = Gtk.MenuButton(direction=Gtk.ArrowType.UP, visible=True)
            popover_button.set_size_request(32, 32)
            popover = get_popover(popover_button)
            popover_button.set_popover(popover)
            box.pack_start(popover_button, False, False, 0)

            if primary_opens_popover:
                primary_button.connect("clicked", lambda _x: popover_button.emit("clicked"))

        return box

    @staticmethod
    def get_link_button(text):
        """Return a suitable button for a menu popover; this must be
        a ModelButton to be styled correctly."""
        button = Gtk.ModelButton(text, visible=True, xalign=0.0)
        return button

    def get_game_name_label(self):
        """Return the label with the game's title"""
        title_label = Gtk.Label(visible=True)
        title_label.set_ellipsize(Pango.EllipsizeMode.END)
        title_label.set_markup("<span font_desc='16'><b>%s</b></span>" % gtk_safe(self.game.name))
        return title_label

    def get_runner_button(self):
        icon_name = self.game.runner.name + "-symbolic"
        runner_icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
        runner_popover_buttons = self.get_runner_buttons()
        if runner_popover_buttons:
            runner_button = Gtk.Button(image=runner_icon, visible=True)
            return GameBar.get_popover_box(runner_button, runner_popover_buttons, primary_opens_popover=True)

        runner_icon.set_margin_left(49)
        runner_icon.set_margin_right(6)
        return runner_icon

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
        last_played_label.set_markup(_("Last played:\n<b>%s</b>") % lastplayed.strftime("%b %-d %Y"))
        return last_played_label

    def get_locate_installed_game_button(self, game_actions):
        """Return a button to locate an existing install"""
        button = GameBar.get_link_button(_("Locate installed game"))
        button.connect("clicked", game_actions.on_locate_installed_game, self.game)
        return {"locate": button}

    def get_play_button(self, game_actions):
        """Return the widget for install/play/stop and game config"""
        button = Gtk.Button(visible=True)
        button.set_size_request(120, 32)
        game_buttons = None

        if self.game.is_installed:
            game_buttons = self.get_game_buttons(game_actions)
            if self.game.state == self.game.STATE_STOPPED:
                button.set_label(_("Play"))
                button.connect("clicked", game_actions.on_game_launch)
            elif self.game.state == self.game.STATE_LAUNCHING:
                button.set_label(_("Launching"))
                button.set_sensitive(False)
            else:
                button.set_label(_("Stop"))
                button.connect("clicked", game_actions.on_game_stop)
        else:
            button.set_label(_("Install"))
            button.connect("clicked", game_actions.on_install_clicked)
            if self.service:
                if self.service.local:
                    # Local services don't show an install dialog, they can be launched directly
                    button.set_label(_("Play"))
                if self.service.drm_free:
                    game_buttons = self.get_locate_installed_game_button(game_actions)

        if game_buttons:
            button.set_size_request(84, 32)
            box = GameBar.get_popover_box(button, game_buttons)
            return box
        return button

    def get_game_buttons(self, game_actions):
        """Return a dictionary of buttons to use in the panel"""
        displayed = game_actions.get_displayed_entries()
        buttons = {}
        for action in game_actions.get_game_actions():
            action_id, label, callback = action
            if action_id in ("play", "stop", "install"):
                continue
            button = GameBar.get_link_button(label)
            button.set_visible(displayed.get(action_id))
            buttons[action_id] = button
            button.connect("clicked", self.on_link_button_clicked, callback)
        return buttons

    def get_runner_buttons(self):
        buttons = {}
        if self.game.runner_name and self.game.is_installed:
            runner = runners.import_runner(self.game.runner_name)(self.game.config)
            for entry in runner.context_menu_entries:
                name, label, callback = entry
                button = GameBar.get_link_button(label)
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
            (self.game.is_db_stored and game.id == self.game.id)
            or (self.appid and game.appid == self.appid)
        ):
            self.game = game
        elif self.game != game:
            return True
        self.clear_view()
        self.update_view()
        return True
