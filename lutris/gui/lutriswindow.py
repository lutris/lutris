"""Main window for the Lutris interface."""
# pylint: disable=no-member
import os
from collections import namedtuple
from gettext import gettext as _

from gi.repository import Gdk, Gio, GLib, GObject, Gtk

from lutris import api, services, settings
from lutris.database import categories as categories_db
from lutris.database import games as games_db
from lutris.database.services import ServiceGameCollection
from lutris.game_actions import GameActions
from lutris.gui import dialogs
from lutris.gui.config.add_game import AddGameDialog
from lutris.gui.config.system import SystemConfigDialog
from lutris.gui.dialogs.runners import RunnersDialog
from lutris.gui.views.grid import GameGridView
from lutris.gui.views.list import GameListView
from lutris.gui.views.menu import ContextualMenu
from lutris.gui.views.store import GameStore
from lutris.gui.widgets.game_bar import GameBar
from lutris.gui.widgets.gi_composites import GtkTemplate
from lutris.gui.widgets.services import ServiceBox
from lutris.gui.widgets.sidebar import LutrisSidebar
from lutris.gui.widgets.utils import open_uri
from lutris.runtime import RuntimeUpdater
from lutris.services.lutris import LutrisService
from lutris.util import datapath
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger


@GtkTemplate(ui=os.path.join(datapath.get(), "ui", "lutris-window.ui"))
class LutrisWindow(Gtk.ApplicationWindow):  # pylint: disable=too-many-public-methods

    """Handler class for main window signals."""

    default_view_type = "grid"
    default_width = 800
    default_height = 600

    __gtype_name__ = "LutrisWindow"
    __gsignals__ = {
        "view-updated": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    main_box = GtkTemplate.Child()
    games_scrollwindow = GtkTemplate.Child()
    sidebar_revealer = GtkTemplate.Child()
    sidebar_scrolled = GtkTemplate.Child()
    search_revealer = GtkTemplate.Child()
    game_revealer = GtkTemplate.Child()
    search_entry = GtkTemplate.Child()
    search_toggle = GtkTemplate.Child()
    zoom_adjustment = GtkTemplate.Child()
    blank_overlay = GtkTemplate.Child()
    search_spinner = GtkTemplate.Child()
    viewtype_icon = GtkTemplate.Child()

    def __init__(self, application, **kwargs):
        width = int(settings.read_setting("width") or self.default_width)
        height = int(settings.read_setting("height") or self.default_height)
        super().__init__(
            default_width=width,
            default_height=height,
            window_position=Gtk.WindowPosition.NONE,
            icon_name="lutris",
            application=application,
            **kwargs
        )
        self.application = application
        self.runtime_updater = RuntimeUpdater()
        self.threads_stoppers = []
        self.icon_type = None
        self.service = LutrisService()

        # Load settings
        self.window_size = (width, height)
        self.maximized = settings.read_setting("maximized") == "True"

        icon_type = self.load_icon_type_from_settings()
        self.service_media = self.get_service_media(icon_type)

        # Window initialization
        self.game_actions = GameActions(application=application, window=self)
        self.search_timer_id = None
        self.game_store = None
        self.view = Gtk.Box()

        self.connect("delete-event", self.on_window_delete)
        self.connect("map-event", self.on_load)
        if self.maximized:
            self.maximize()
        self.init_template()
        self._init_actions()
        self._bind_zoom_adjustment()

        # Set theme to dark if set in the settings
        self.set_dark_theme()
        self.set_viewtype_icon(self.view_type)

        # Add additional widgets
        lutris_icon = Gtk.Image.new_from_icon_name("lutris", Gtk.IconSize.MENU)
        lutris_icon.set_margin_right(3)
        self.selected_category = settings.read_setting("selected_category", default="runner:all")
        category, value = self.selected_category.split(":")
        self.filters = {category: value}  # Type of filter corresponding to the selected sidebar element
        self.sidebar = LutrisSidebar(self.application, selected=self.selected_category)
        self.sidebar.set_size_request(250, -1)
        self.sidebar.connect("selected-rows-changed", self.on_sidebar_changed)
        self.sidebar_scrolled.add(self.sidebar)

        # Sidebar visibility
        self.sidebar_revealer.set_reveal_child(self.left_side_panel_visible)
        self.sidebar_revealer.set_transition_duration(300)

    def _init_actions(self):
        Action = namedtuple("Action", ("callback", "type", "enabled", "default", "accel"))
        Action.__new__.__defaults__ = (None, None, True, None, None)

        actions = {
            "add-game": Action(self.on_add_game_button_clicked),
            "preferences": Action(self.on_preferences_activate),
            "manage-runners": Action(self.on_manage_runners, ),
            "about": Action(self.on_about_clicked),
            "show-installed-only": Action(  # delete?
                self.on_show_installed_state_change,
                type="b",
                default=self.filter_installed,
                accel="<Primary>h",
            ),
            "toggle-viewtype": Action(self.on_toggle_viewtype),
            "icon-type": Action(self.on_icontype_state_change, type="s", default=self.icon_type),
            "view-sorting": Action(self.on_view_sorting_state_change, type="s", default=self.view_sorting),
            "view-sorting-ascending": Action(
                self.on_view_sorting_direction_change,
                type="b",
                default=self.view_sorting_ascending,
            ),
            "use-dark-theme": Action(self.on_dark_theme_state_change, type="b", default=self.use_dark_theme),
            "show-tray-icon": Action(self.on_tray_icon_toggle, type="b", default=self.show_tray_icon),
            "show-left-side-panel": Action(
                self.on_left_side_panel_state_change,
                type="b",
                default=self.left_side_panel_visible,
                accel="F9",
            ),
            "show-hidden-games": Action(
                self.hidden_state_change,
                type="b",
                default=self.show_hidden_games,
            ),
            "open-forums": Action(lambda *x: open_uri("https://forums.lutris.net/")),
            "open-discord": Action(lambda *x: open_uri("https://discord.gg/Pnt5CuY")),
            "donate": Action(lambda *x: open_uri("https://lutris.net/donate")),
        }

        self.actions = {}
        app = self.props.application
        for name, value in actions.items():
            if not value.type:
                action = Gio.SimpleAction.new(name)
                action.connect("activate", value.callback)
            else:
                default_value = None
                param_type = None
                if value.default is not None:
                    default_value = GLib.Variant(value.type, value.default)
                if value.type != "b":
                    param_type = default_value.get_type()
                action = Gio.SimpleAction.new_stateful(name, param_type, default_value)
                action.connect("change-state", value.callback)
            self.actions[name] = action
            if value.enabled is False:
                action.props.enabled = False
            self.add_action(action)
            if value.accel:
                app.add_accelerator(value.accel, "win." + name)

    def on_load(self, widget, data):
        self.game_store = GameStore(self.service_media)
        self.switch_view()
        self.view.contextual_menu = ContextualMenu(self.game_actions.get_game_actions())
        self.update_runtime()

    def hidden_state_change(self, action, value):
        """Hides or shows the hidden games"""
        action.set_state(value)
        settings.write_setting("show_hidden_games", str(self.show_hidden_games).lower(), section="lutris")
        self.emit("view-updated")

    @property
    def current_view_type(self):
        """Returns which kind of view is currently presented (grid or list)"""
        return "grid" if isinstance(self.view, GameGridView) else "list"

    @property
    def filter_installed(self):
        return settings.read_setting("filter_installed").lower() == "true"

    @property
    def left_side_panel_visible(self):
        show_left_panel = (settings.read_setting("left_side_panel_visible").lower() != "false")
        return show_left_panel or self.sidebar_visible

    @property
    def sidebar_visible(self):
        """Deprecated: For compability only"""
        return settings.read_setting("sidebar_visible") in [
            "true",
            None,
        ]

    @property
    def use_dark_theme(self):
        """Return whether to use the dark theme variant (if the theme provides one)"""
        return settings.read_setting("dark_theme", default="false").lower() == "true"

    def on_tray_icon_toggle(self, action, value):
        """Callback for handling tray icon toggle"""
        action.set_state(value)
        settings.write_setting('show_tray_icon', value)
        self.application.set_tray_icon()

    @property
    def show_tray_icon(self):
        """Setting to hide or show status icon"""
        return settings.read_setting("show_tray_icon", default="false").lower() == "true"

    @property
    def view_sorting(self):
        value = settings.read_setting("view_sorting") or "name"
        if value.endswith("_text"):
            value = value[:-5]
        return value

    @property
    def view_sorting_ascending(self):
        return settings.read_setting("view_sorting_ascending").lower() != "false"

    @property
    def show_hidden_games(self):
        return settings.read_setting("show_hidden_games").lower() == "true"

    @property
    def sort_params(self):
        _sort_params = [("installed", "DESC")]
        _sort_params.append((self.view_sorting, "ASC" if self.view_sorting_ascending else "DESC"))
        return _sort_params

    def get_running_games(self):
        """Return a list of currently running games"""
        return games_db.get_games_by_ids([game.id for game in self.application.running_games])

    def get_installed_games(self):
        """Return a list of currently running games"""
        return games_db.get_games(filters={'installed': '1'})

    def get_api_games(self):
        """Return games from the lutris API"""
        if not self.filters.get("text"):
            api_games = api.get_bundle("featured")
        else:
            api_games = api.search_games(self.filters["text"])
        return api_games

    def game_matches(self, game):
        if not self.filters.get("text"):
            return True
        return self.filters["text"] in game["name"].lower()

    def get_games_from_filters(self):
        if "dynamic_category" in self.filters:
            category = self.filters["dynamic_category"]
            if category in services.get_services():
                self.service = services.get_services()[category]()
                if self.service.online:
                    self.service.connect("service-login", self.on_service_games_updated)
                    self.service.connect("service-logout", self.on_service_logout)
                self.service.connect("service-games-loaded", self.on_service_games_updated)

                service_games = ServiceGameCollection.get_for_service(category)
                if service_games:
                    return [
                        game for game in sorted(
                            service_games,
                            key=lambda game: game.get(self.view_sorting) or game["name"],
                            reverse=not self.view_sorting_ascending
                        ) if self.game_matches(game)
                    ]

                if not self.service.online or self.service.is_connected():
                    AsyncCall(self.service.load, None)
                    spinner = Gtk.Spinner(visible=True)
                    spinner.start()
                    self.blank_overlay.add(spinner)
                else:
                    self.blank_overlay.add(
                        Gtk.Label(_("Connect your %s account to access your games") % self.service.name, visible=True)
                    )
                self.blank_overlay.props.visible = True
                return
            self.service = LutrisService()
            self.service.connect("service-games-loaded", self.on_service_games_updated)
            game_providers = {
                "running": self.get_running_games,
                "installed": self.get_installed_games,
                "lutrisnet": self.get_api_games,
            }
            return game_providers[category]()
        self.service = LutrisService()
        self.service.connect("service-games-loaded", self.on_service_games_updated)
        if self.filters.get("category"):
            game_ids = categories_db.get_game_ids_for_category(self.filters["category"])
            return games_db.get_games_by_ids(game_ids)
        sql_filters = {}
        sql_excludes = {}
        if self.filters.get("runner"):
            sql_filters["runner"] = self.filters["runner"]
        if self.filters.get("platform"):
            sql_filters["platform"] = self.filters["platform"]
        if self.filters.get("installed"):
            sql_filters["installed"] = "1"
        if self.filters.get("text"):
            search_query = {"name": self.filters["text"]}
        else:
            search_query = None
        if not self.show_hidden_games:
            sql_excludes["hidden"] = 1
        games = games_db.get_games(
            searches=search_query,
            filters=sql_filters,
            excludes=sql_excludes,
            sorts=self.sort_params
        )
        return games

    def on_service_games_updated(self, service, service_id):
        self.game_store.load_icons()
        self.emit("view-updated")
        return False

    def on_service_logout(self, *args, **kwargs):
        self.update_store()
        return False

    def get_service_media(self, icon_type):
        """Return the ServiceMedia class used for this view"""
        medias = self.service.medias
        if icon_type in medias:
            return medias[icon_type]()
        return medias[self.service.default_format]()

    def update_store(self, *_args, **_kwargs):
        self.game_store.store.clear()
        for child in self.blank_overlay.get_children():
            child.destroy()
        games = self.get_games_from_filters()
        self.view.service = self.service.id
        self.reload_service_media()
        for child in self.search_revealer.get_children():
            child.destroy()
        service_box = ServiceBox(self.service)
        service_box.show()
        self.search_revealer.add(service_box)
        self.search_revealer.set_reveal_child(True)
        if games is None:
            self.search_spinner.props.active = True
            return False
        for game in games:
            game["image_size"] = self.service_media.size
            self.game_store.add_game(game)

        if self.filters.get("text"):
            empty_label = Gtk.Label(_("No games matching '%s' found ") % self.filters["text"], visible=True)
        else:
            empty_label = Gtk.Label(_("No games found"), visible=True)
        self.blank_overlay.add(empty_label)
        self.blank_overlay.props.visible = not bool(games)
        self.search_spinner.props.active = False
        self.search_timer_id = None
        return False

    def update_game_by_id(self, game_id):
        """Update the view by DB ID"""
        db_game = games_db.get_game_by_field(game_id, "id")
        if db_game:
            return self.game_store.update(db_game)
        return self.game_store.remove_game(game_id)

    def set_dark_theme(self):
        """Enables or disbales dark theme"""
        gtksettings = Gtk.Settings.get_default()
        gtksettings.set_property("gtk-application-prefer-dark-theme", self.use_dark_theme)

    def _bind_zoom_adjustment(self):
        """Bind the zoom slider to the supported banner sizes"""
        # media_services = self.service.medias.keys()
        # self.zoom_adjustment.props.value = self.service_media.size
        # self.zoom_adjustment.connect(
        #     "value-changed",
        #     lambda adj: self._set_icon_type(media_services[int(adj.props.value)]),
        # )

    @property
    def view_type(self):
        """Return the type of view saved by the user"""
        view_type = settings.read_setting("view_type")
        if view_type in ["grid", "list"]:
            return view_type
        return self.default_view_type

    def do_key_press_event(self, event):  # pylint: disable=arguments-differ
        if event.keyval == Gdk.KEY_Escape:
            self.search_toggle.set_active(False)
            return Gdk.EVENT_STOP
        # XXX: This block of code below is to enable searching on type.
        # Enabling this feature steals focus from other entries so it needs
        # some kind of focus detection before enabling library search.

        # Probably not ideal for non-english, but we want to limit
        # which keys actually start searching
        if (  # pylint: disable=too-many-boolean-expressions
            not Gdk.KEY_0 <= event.keyval <= Gdk.KEY_z or event.state & Gdk.ModifierType.CONTROL_MASK
            or event.state & Gdk.ModifierType.SHIFT_MASK or event.state & Gdk.ModifierType.META_MASK
            or event.state & Gdk.ModifierType.MOD1_MASK or self.search_entry.has_focus()
        ):
            return Gtk.ApplicationWindow.do_key_press_event(self, event)

        self.search_toggle.set_active(True)
        self.search_entry.grab_focus()
        return self.search_entry.do_key_press_event(self.search_entry, event)

    def load_icon_type_from_settings(self):
        """Return the icon style depending on the type of view."""
        if self.view_type == "list":
            self.icon_type = settings.read_setting("icon_type_listview")
            default = "icon"
        else:
            self.icon_type = settings.read_setting("icon_type_gridview")
            default = "banner"
        if self.icon_type not in self.service.medias:
            self.icon_type = default
        return self.icon_type

    def reload_service_media(self):
        icon_type = self.load_icon_type_from_settings()
        service_media = self.get_service_media(icon_type)
        self.game_store.set_service_media(service_media)
        # self.zoom_adjustment.props.value = list(self.service.medias.keys()).index(self.icon_type)
        return service_media

    def switch_view(self, view_type=None):
        """Switch between grid view and list view."""
        if self.view:
            self.view.destroy()
        service_media = self.reload_service_media()
        if self.view_type == "grid":
            self.view = GameGridView(self.game_store, service_media)
        else:
            self.view = GameListView(self.game_store, service_media)

        self.view.connect("game-selected", self.game_selection_changed)
        self.view.contextual_menu = ContextualMenu(self.game_actions.get_game_actions())
        for child in self.games_scrollwindow.get_children():
            child.destroy()
        self.games_scrollwindow.add(self.view)
        self.connect("view-updated", self.update_store)

        if view_type:
            self.set_viewtype_icon(view_type)
            settings.write_setting("view_type", view_type)

        self.view.show_all()
        self.update_store()

    def game_selection_changed(self, view, game_id):
        if not game_id:
            self.game_revealer.set_reveal_child(False)
            return
        if self.service:
            print(game_id)
            print(type(game_id))
            print(type(self.service))
            game = ServiceGameCollection.get_game(self.service.id, game_id)
        else:
            game = games_db.get_game_by_field(game_id, "id")
        for child in self.game_revealer.get_children():
            child.destroy()
        self.game_revealer.add(GameBar(game))
        self.game_revealer.set_reveal_child(True)

    def set_viewtype_icon(self, view_type):
        self.viewtype_icon.set_from_icon_name("view-%s-symbolic" % view_type, Gtk.IconSize.BUTTON)

    def update_runtime(self):
        """Check that the runtime is up to date"""
        runtime_sync = AsyncCall(self.runtime_updater.update, None)
        self.threads_stoppers.append(runtime_sync.stop_request.set)

    def on_dark_theme_state_change(self, action, value):
        """Callback for theme switching action"""
        action.set_state(value)
        settings.write_setting("dark_theme", value.get_boolean())
        self.set_dark_theme()

    @GtkTemplate.Callback
    def on_resize(self, widget, *_args):
        """Size-allocate signal.

        Updates stored window size and maximized state.
        """
        if not widget.get_window():
            return
        self.maximized = widget.is_maximized()
        if not self.maximized:
            self.window_size = widget.get_size()

    def on_window_delete(self, *_args):
        if self.application.running_games.get_n_items():
            self.hide()
            return True

    @GtkTemplate.Callback
    def on_destroy(self, *_args):
        """Signal for window close."""
        # Stop cancellable running threads
        for stopper in self.threads_stoppers:
            stopper()

        # Save settings
        width, height = self.window_size
        settings.write_setting("width", width)
        settings.write_setting("height", height)
        settings.write_setting("maximized", self.maximized)

    @GtkTemplate.Callback
    def on_preferences_activate(self, *_args):
        """Callback when preferences is activated."""
        self.application.show_window(SystemConfigDialog)

    @GtkTemplate.Callback
    def on_manage_runners(self, *args):
        self.application.show_window(RunnersDialog, transient_for=self)

    def on_show_installed_state_change(self, action, value):
        """Callback to handle uninstalled game filter switch"""
        action.set_state(value)
        self.set_show_installed_state(value.get_boolean())
        self.emit("view-updated")

    def set_show_installed_state(self, filter_installed):
        """Shows or hide uninstalled games"""
        settings.write_setting("filter_installed", bool(filter_installed))
        self.filters["installed"] = filter_installed
        self.emit("view-updated")

    @GtkTemplate.Callback
    def on_search_entry_changed(self, entry):
        """Callback for the search input keypresses"""
        self.search_spinner.props.active = True
        if self.search_timer_id:
            GLib.source_remove(self.search_timer_id)
        self.filters["text"] = entry.get_text().lower().strip()
        self.search_timer_id = GLib.timeout_add(350, self.update_store)

    @GtkTemplate.Callback
    def on_search_toggle(self, button):
        """Called when search bar is shown / hidden"""
        active = button.props.active
        if active:
            self.search_entry.show()
            self.search_entry.grab_focus()
        else:
            self.search_entry.props.text = ""
            self.search_entry.hide()

    @GtkTemplate.Callback
    def on_about_clicked(self, *_args):
        """Open the about dialog."""
        dialogs.AboutDialog(parent=self)

    def on_game_error(self, game, error):
        """Called when a game has sent the 'game-error' signal"""
        logger.error("%s crashed", game)
        dialogs.ErrorDialog(error, parent=self)

    @GtkTemplate.Callback
    def on_add_game_button_clicked(self, *_args):
        """Add a new game manually with the AddGameDialog."""
        if "runner" in self.filters:
            runner = self.filters["runner"]
        else:
            runner = None
        AddGameDialog(self, runner=runner)
        return True

    def on_toggle_viewtype(self, *args):
        self.switch_view("list" if self.current_view_type == "grid" else "grid")

    def on_viewtype_state_change(self, action, val):
        """Callback to handle view type switch"""
        action.set_state(val)
        view_type = val.get_string()
        if view_type != self.current_view_type:
            self.switch_view(view_type)

    def _set_icon_type(self, icon_type):
        self.icon_type = icon_type
        if self.icon_type == self.game_store.icon_type:
            return
        if self.current_view_type == "grid":
            settings.write_setting("icon_type_gridview", self.icon_type)
        elif self.current_view_type == "list":
            settings.write_setting("icon_type_listview", self.icon_type)
        self.switch_view()

    def on_icontype_state_change(self, action, value):
        action.set_state(value)
        self._set_icon_type(value.get_string())

    def on_view_sorting_state_change(self, action, value):
        self.actions["view-sorting"].set_state(value)
        value = str(value).strip("'")
        settings.write_setting("view_sorting", value)
        self.emit("view-updated")

    def on_view_sorting_direction_change(self, action, value):
        self.actions["view-sorting-ascending"].set_state(value)
        settings.write_setting("view_sorting_ascending", bool(value))
        self.emit("view-updated")

    def on_left_side_panel_state_change(self, action, value):
        """Callback to handle left side panel toggle"""
        action.set_state(value)
        left_side_panel_visible = value.get_boolean()
        settings.write_setting("left_side_panel_visible", bool(left_side_panel_visible))
        self.sidebar_revealer.set_reveal_child(left_side_panel_visible)
        # Retrocompatibility with sidebar_visible :
        # if we change the new attribute, we must set the old one to false
        if self.sidebar_visible:
            settings.write_setting("sidebar_visible", "false")

    def on_sidebar_changed(self, widget):
        row = widget.get_selected_row()
        self.selected_category = "%s:%s" % (row.type, row.id)
        for filter_type in ("category", "dynamic_category", "runner", "platform"):
            if filter_type in self.filters:
                self.filters.pop(filter_type)
        if row:
            self.filters[row.type] = row.id
        self.emit("view-updated")
