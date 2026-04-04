from datetime import datetime
from gettext import gettext as _
from typing import TYPE_CHECKING

from gi.repository import Gtk, Pango

from lutris import runners, services
from lutris.database.games import get_game_for_service
from lutris.game import GAME_INSTALLED, GAME_START, GAME_STARTED, GAME_STOPPED, GAME_UPDATED, Game
from lutris.game_actions import get_game_actions
from lutris.gui.widgets.contextual_menu import update_action_widget_visibility
from lutris.util.strings import gtk_safe

if TYPE_CHECKING:
    from lutris.gui.application import LutrisApplication
    from lutris.gui.lutriswindow import LutrisWindow


class GameBar(Gtk.Box):
    def __init__(self, db_game: dict, application: "LutrisApplication", window: "LutrisWindow"):
        """Create the game bar with a database row; db_game may be a DbGameDict
        from the games DB or a DBServiceGame from the service games DB."""
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            visible=True,
            margin_top=12,
            margin_start=12,
            margin_bottom=12,
            margin_end=12,
            spacing=6,
        )

        self.application = application
        self.window = window

        self.game_start_registration = GAME_START.register(self.on_game_state_changed)
        self.game_started_registration = GAME_STARTED.register(self.on_game_state_changed)
        self.game_stopped_registration = GAME_STOPPED.register(self.on_game_state_changed)
        self.game_updated_registration = GAME_UPDATED.register(self.on_game_state_changed)
        self.game_installed_registration = GAME_INSTALLED.register(self.on_game_state_changed)
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
            self.game = application.get_game_by_id(game_id)
        else:
            self.game = Game.create_empty_service_game(db_game, self.service)
        self.update_view()

    def on_destroy(self, widget):
        self.game_start_registration.unregister()
        self.game_started_registration.unregister()
        self.game_stopped_registration.unregister()
        self.game_updated_registration.unregister()
        self.game_installed_registration.unregister()
        return True

    def update_view(self):
        """Populate the view with widgets"""
        game_actions = get_game_actions([self.game], window=self.window, application=self.application)

        game_label = self.get_game_name_label()
        game_label.set_halign(Gtk.Align.START)
        self.append(game_label)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.append(hbox)

        self.play_button = self.get_play_button(game_actions)
        hbox.append(self.play_button)

        hbox.append(self.get_runner_button())
        hbox.append(self.get_platform_label())
        if self.game.lastplayed:
            hbox.append(self.get_last_played_label())
        if self.game.playtime:
            hbox.append(self.get_playtime_label())

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
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, visible=True, spacing=3)
            vbox.set_margin_top(9)
            vbox.set_margin_bottom(9)
            vbox.set_margin_start(9)
            vbox.set_margin_end(9)

            for button in popover_buttons:
                vbox.append(button)

            pop.set_child(vbox)
            pop.set_position(Gtk.PositionType.TOP)
            return pop

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, visible=True)
        box.add_css_class("linked")

        box.append(primary_button)

        if popover_buttons:
            popover_button = Gtk.MenuButton(direction=Gtk.ArrowType.UP, visible=True)
            popover_button.set_size_request(32, 32)
            popover = get_popover(popover_button)
            popover_button.set_popover(popover)
            box.append(popover_button)

            if primary_opens_popover:
                primary_button.connect("clicked", lambda _x: popover_button.emit("clicked"))

        return box

    def get_link_button(self, text, callback=None):
        """Return a suitable button for a menu popover."""
        if text == "-":
            return Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)

        button = Gtk.Button(label=text)
        button.set_has_frame(False)
        button.set_halign(Gtk.Align.FILL)
        child = button.get_child()
        if child and isinstance(child, Gtk.Label):
            child.set_halign(Gtk.Align.START)
        if callback:
            button.connect("clicked", self.on_link_button_clicked, callback)
        return button

    def get_game_name_label(self):
        """Return the label with the game's title"""
        title_label = Gtk.Label(visible=True)
        title_label.set_ellipsize(Pango.EllipsizeMode.END)
        title_label.set_markup("<span font_desc='16'><b>%s</b></span>" % gtk_safe(self.game.name))
        return title_label

    def get_runner_button(self):
        if not self.game.has_runner:
            return Gtk.Box()
        icon_name = self.game.runner.name + "-symbolic"
        runner_icon = Gtk.Image.new_from_icon_name(icon_name)
        runner_popover_buttons = self.get_runner_buttons()
        if runner_popover_buttons:
            runner_button = Gtk.Button(child=runner_icon, visible=True)
            return GameBar.get_popover_box(runner_button, runner_popover_buttons, primary_opens_popover=True)

        runner_icon.set_margin_start(49)
        runner_icon.set_margin_end(6)
        return runner_icon

    def get_platform_label(self):
        platform_label = Gtk.Label(visible=True)
        if not self.game.platform:
            return platform_label
        platform_label.set_size_request(120, -1)
        platform_label.set_xalign(0)
        platform = gtk_safe(self.game.platform)
        platform_label.set_tooltip_markup(platform)
        platform_label.set_markup(_("Platform:\n<b>%s</b>") % platform)
        platform_label.set_property("ellipsize", Pango.EllipsizeMode.END)
        return platform_label

    def get_playtime_label(self):
        """Return the label containing the playtime info"""
        playtime_label = Gtk.Label(visible=True)
        playtime_label.set_size_request(120, -1)
        playtime_label.set_xalign(0)
        playtime_label.set_markup(_("Time played:\n<b>%s</b>") % self.game.formatted_playtime)
        return playtime_label

    def get_last_played_label(self):
        """Return the label containing the last played info"""
        last_played_label = Gtk.Label(visible=True)
        last_played_label.set_size_request(120, -1)
        last_played_label.set_xalign(0)
        lastplayed = datetime.fromtimestamp(self.game.lastplayed)
        last_played_label.set_markup(_("Last played:\n<b>%s</b>") % lastplayed.strftime("%b %-d %Y"))
        return last_played_label

    def get_locate_installed_game_button(self, game_actions):
        """Return a button to locate an existing install"""
        button = self.get_link_button(_("Locate installed game"))
        button.connect("clicked", game_actions.on_locate_installed_game)
        return button

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
                button.set_sensitive(game_actions.is_game_launchable)
            elif self.game.state == self.game.STATE_LAUNCHING:
                button.set_label(_("Launching"))
                button.set_sensitive(False)
            else:
                button.set_label(_("Stop"))
                button.connect("clicked", game_actions.on_game_stop)
                button.set_sensitive(game_actions.is_game_running)
        else:
            button.set_label(_("Install"))
            button.connect("clicked", game_actions.on_install_clicked)
            button.set_sensitive(game_actions.is_installable)
            if self.service:
                if self.service.local:
                    # Local services don't show an install dialog, they can be launched directly
                    button.set_label(_("Play"))
                if self.service.drm_free:
                    game_buttons = [self.get_locate_installed_game_button(game_actions)]

        if game_buttons:
            button.set_size_request(84, 32)
            box = GameBar.get_popover_box(button, game_buttons)
            return box
        return button

    def get_game_buttons(self, game_actions):
        """Return a list of buttons to use in the panel"""
        displayed = game_actions.get_displayed_entries()
        buttons = []
        button_visibility = {}
        for action_id, label, callback in game_actions.get_game_actions():
            if action_id in ("play", "stop", "install"):
                continue
            button = self.get_link_button(label, callback)
            if action_id:
                button_visibility[button] = displayed.get(action_id, True)
            buttons.append(button)

        update_action_widget_visibility(buttons, lambda w: button_visibility.get(w, None))
        return buttons

    def get_runner_buttons(self):
        buttons = []
        if self.game.has_runner and self.game.is_installed:
            runner = runners.import_runner(self.game.runner_name)(self.game.config)
            for _name, label, callback in runner.context_menu_entries:
                button = self.get_link_button(label, callback)
                buttons.append(button)
        return buttons

    def on_link_button_clicked(self, button, callback):
        """Callback for link buttons. Closes the popover then runs the actual action"""
        popover = button.get_parent().get_parent()
        popover.popdown()
        callback(button)

    def on_install_clicked(self, button):
        """Handler for installing service games"""
        self.service.install(self.db_game)

    def on_game_state_changed(self, game: Game) -> None:
        """Handler called when the game has changed state"""
        if (self.game.is_db_stored and game.id == self.game.id) or (self.appid and game.appid == self.appid):
            self.game = game
        elif self.game != game:
            return

        child = self.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.remove(child)
            child = next_child
        self.update_view()
