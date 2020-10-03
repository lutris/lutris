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
from lutris.gui.views.store import GameStore
from lutris.gui.widgets.contextual_menu import ContextualMenu
from lutris.gui.widgets.game_bar import GameBar
from lutris.gui.widgets.gi_composites import GtkTemplate
from lutris.gui.widgets.services import ServiceBar
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
    game_revealer = GtkTemplate.Child()
    search_entry = GtkTemplate.Child()
    search_toggle = GtkTemplate.Child()
    zoom_adjustment = GtkTemplate.Child()
    blank_overlay = GtkTemplate.Child()
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
        self.service = None

        # Load settings
        self.window_size = (width, height)
        self.maximized = settings.read_setting("maximized") == "True"

        icon_type = self.load_icon_type()
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

        self.game_bar = None
        self.service_bar = None
        self.revealer_box = Gtk.HBox(visible=True)
        self.game_revealer.add(self.revealer_box)

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
        self.view.grab_focus()
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
        searches, _filters, excludes = self.get_sql_filters()
        return games_db.get_games(searches=searches, filters={'installed': '1'}, excludes=excludes)

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

    def unset_service(self):
        self.service = None
        if self.service_bar:
            self.service_bar.destroy()

    def get_games_from_filters(self):
        if self.filters.get("service"):
            service_name = self.filters["service"]
            if service_name in services.get_services():
                self.service = services.get_services()[service_name]()
                if self.service.online:
                    self.service.connect("service-login", self.on_service_games_updated)
                    self.service.connect("service-logout", self.on_service_logout)
                self.service.connect("service-games-loaded", self.on_service_games_updated)

                service_games = ServiceGameCollection.get_for_service(service_name)
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
            self.unset_service()
        dynamic_categories = {
            "running": self.get_running_games,
            "installed": self.get_installed_games
        }
        if self.filters.get("dynamic_category") in dynamic_categories:
            return dynamic_categories[self.filters["dynamic_category"]]()
        self.unset_service()
        if self.filters.get("category"):
            game_ids = categories_db.get_game_ids_for_category(self.filters["category"])
            return games_db.get_games_by_ids(game_ids)

        searches, filters, excludes = self.get_sql_filters()
        return games_db.get_games(
            searches=searches,
            filters=filters,
            excludes=excludes,
            sorts=self.sort_params
        )

    def get_sql_filters(self):
        """Return the current filters for the view"""
        sql_filters = {}
        sql_excludes = {}
        if self.filters.get("runner"):
            sql_filters["runner"] = self.filters["runner"]
        if self.filters.get("platform"):
            sql_filters["platform"] = self.filters["platform"]
        if self.filters.get("installed"):
            sql_filters["installed"] = "1"
        if self.filters.get("text"):
            searches = {"name": self.filters["text"]}
        else:
            searches = None
        if not self.show_hidden_games:
            sql_excludes["hidden"] = 1
        return searches, sql_filters, sql_excludes

    def get_service_media(self, icon_type):
        """Return the ServiceMedia class used for this view"""
        service = self.service if self.service else LutrisService
        medias = service.medias
        if icon_type in medias:
            return medias[icon_type]()
        return medias[service.default_format]()

    def update_service_box(self):
        if self.service:
            if self.service_bar:
                if self.service.id == self.service_bar.service.id:
                    return
                self.service_bar.destroy()
            self.service_bar = ServiceBar(self.service)
            self.revealer_box.pack_end(self.service_bar, False, False, 0)
        elif self.service_bar:
            self.service_bar.destroy()

    def update_revealer(self, game=None):
        if game:
            if self.game_bar:
                self.game_bar.destroy()
            self.game_bar = GameBar(game, self.game_actions)
            self.revealer_box.pack_start(self.game_bar, True, True, 0)
        elif self.game_bar:
            self.game_bar.destroy()
        self.update_service_box()
        if self.revealer_box.get_children():
            self.game_revealer.set_reveal_child(True)
        else:
            self.game_revealer.set_reveal_child(False)

    def update_store(self, *_args, **_kwargs):
        self.game_store.store.clear()
        for child in self.blank_overlay.get_children():
            child.destroy()
        games = self.get_games_from_filters()
        self.view.service = self.service.id if self.service else None
        self.reload_service_media()
        self.update_revealer()
        if games is None:
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
        self.search_timer_id = None
        return False

    def set_dark_theme(self):
        """Enables or disables dark theme"""
        gtksettings = Gtk.Settings.get_default()
        gtksettings.set_property("gtk-application-prefer-dark-theme", self.use_dark_theme)

    def _bind_zoom_adjustment(self):
        """Bind the zoom slider to the supported banner sizes"""
        service = self.service if self.service else LutrisService
        media_services = list(service.medias.keys())
        self.zoom_adjustment.set_lower(0)
        self.zoom_adjustment.set_upper(len(media_services))
        if self.icon_type in media_services:
            value = media_services.index(self.icon_type)
        else:
            value = 0
        self.zoom_adjustment.props.value = value
        self.zoom_adjustment.connect("value-changed", self.on_zoom_changed)

    def on_zoom_changed(self, adjustment):
        """Handler for zoom modification"""
        media_index = int(adjustment.props.value)
        adjustment.props.value = media_index
        service = self.service if self.service else LutrisService
        media_services = list(service.medias.keys())
        if len(media_services) <= media_index:
            media_index = media_services.index(service.default_format)
        icon_type = media_services[media_index]
        if icon_type != self.icon_type:
            self.save_icon_type(icon_type)
            self.reload_service_media()
            self.game_store.load_icons()
            self.emit("view-updated")

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

    def load_icon_type(self):
        """Return the icon style depending on the type of view."""
        if self.view_type == "list":
            self.icon_type = settings.read_setting("icon_type_listview")
        else:
            self.icon_type = settings.read_setting("icon_type_gridview")
        return self.icon_type

    def save_icon_type(self, icon_type):
        self.icon_type = icon_type
        if self.current_view_type == "grid":
            settings.write_setting("icon_type_gridview", self.icon_type)
        elif self.current_view_type == "list":
            settings.write_setting("icon_type_listview", self.icon_type)
        self.switch_view()

    def reload_service_media(self):
        self.game_store.set_service_media(
            self.get_service_media(
                self.load_icon_type()
            )
        )

    def switch_view(self, view_type=None):
        """Switch between grid view and list view."""
        if self.view:
            self.view.destroy()
            logger.debug("View destroyed")
        self.reload_service_media()
        view_class = GameGridView if self.view_type == "grid" else GameListView
        self.view = view_class(self.game_store, self.game_store.service_media)

        self.view.connect("game-selected", self.on_game_selection_changed)
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

    def set_viewtype_icon(self, view_type):
        self.viewtype_icon.set_from_icon_name("view-%s-symbolic" % view_type, Gtk.IconSize.BUTTON)

    def update_runtime(self):
        """Check that the runtime is up to date"""
        runtime_sync = AsyncCall(self.runtime_updater.update, None)
        self.threads_stoppers.append(runtime_sync.stop_request.set)

    def set_show_installed_state(self, filter_installed):
        """Shows or hide uninstalled games"""
        settings.write_setting("filter_installed", bool(filter_installed))
        self.filters["installed"] = filter_installed
        self.emit("view-updated")

    def on_service_games_updated(self, service):
        self.game_store.load_icons()
        service.match_games()
        self.emit("view-updated")
        return False

    def on_service_logout(self, *args, **kwargs):
        self.update_store()
        return False

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

    @GtkTemplate.Callback
    def on_search_entry_changed(self, entry):
        """Callback for the search input keypresses"""
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
        for filter_type in ("category", "dynamic_category", "service", "runner", "platform"):
            if filter_type in self.filters:
                self.filters.pop(filter_type)
        if row:
            self.filters[row.type] = row.id
        self.emit("view-updated")

    def on_game_selection_changed(self, view, game_id):
        if not game_id:
            GLib.idle_add(self.update_revealer)
            return False
        if self.service:
            game = ServiceGameCollection.get_game(self.service.id, game_id)
        else:
            game = games_db.get_game_by_field(int(game_id), "id")
        GLib.idle_add(self.update_revealer, game)
        return False
