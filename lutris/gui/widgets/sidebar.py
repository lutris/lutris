"""Sidebar for the main window"""

import locale
from gettext import gettext as _
from typing import List

from gi.repository import GObject, Gtk, Pango

from lutris import runners, services
from lutris.config import LutrisConfig
from lutris.database import categories as categories_db
from lutris.database import games as games_db
from lutris.database import saved_searches as saved_search_db
from lutris.database.categories import CATEGORIES_UPDATED
from lutris.database.saved_searches import SAVED_SEARCHES_UPDATED
from lutris.game import GAME_START, GAME_STOPPED, GAME_UPDATED, Game
from lutris.gui.config.edit_category_games import EditCategoryGamesDialog
from lutris.gui.config.edit_saved_search import EditSavedSearchDialog
from lutris.gui.config.runner import RunnerConfigDialog
from lutris.gui.config.runner_box import RunnerBox
from lutris.gui.config.services_box import ServicesBox
from lutris.gui.dialogs import display_error
from lutris.gui.dialogs.runner_install import RunnerInstallDialog
from lutris.gui.widgets.utils import get_widget_children, has_stock_icon
from lutris.installer.interpreter import ScriptInterpreter
from lutris.runners import InvalidRunnerError
from lutris.services import SERVICES
from lutris.services.base import (
    SERVICE_GAMES_LOADED,
    SERVICE_GAMES_LOADING,
    SERVICE_LOGIN,
    SERVICE_LOGOUT,
    AuthTokenExpiredError,
)
from lutris.util.jobs import schedule_at_idle
from lutris.util.library_sync import LOCAL_LIBRARY_SYNCED, LOCAL_LIBRARY_SYNCING
from lutris.util.log import logger
from lutris.util.strings import get_natural_sort_key

TYPE = 0
SLUG = 1
ICON = 2
LABEL = 3
GAMECOUNT = 4

SERVICE_INDICES = {name: index for index, name in enumerate(SERVICES.keys())}


class SidebarRow(Gtk.ListBoxRow):
    """A row in the sidebar containing possible action buttons"""

    MARGIN = 9
    SPACING = 6

    def __init__(self, id_, type_, name, icon, application=None):
        """Initialize the row

        Parameters:
            id_: identifier of the row
            type: type of row to display (still used?)
            name (str): Text displayed on the row
            icon (GtkImage): icon displayed next to the label
            application (GtkApplication): reference to the running application
        """
        super().__init__()
        self.application = application
        self.type = type_
        self.id = id_
        self.name = name
        self.is_updating = False
        self.buttons = {}
        self.box = Gtk.Box(spacing=self.SPACING, margin_start=self.MARGIN, margin_end=self.MARGIN)
        self.connect("realize", self.on_realize)
        self.add(self.box)

        if not icon:
            icon = Gtk.Box(spacing=self.SPACING, margin_start=self.MARGIN, margin_end=self.MARGIN)
        self.box.add(icon)
        label = Gtk.Label(
            label=name,
            halign=Gtk.Align.START,
            hexpand=True,
            margin_top=self.SPACING,
            margin_bottom=self.SPACING,
            ellipsize=Pango.EllipsizeMode.END,
        )
        self.box.pack_start(label, True, True, 0)
        self.btn_box = Gtk.Box(spacing=3, no_show_all=True, valign=Gtk.Align.CENTER, homogeneous=True)
        self.box.pack_end(self.btn_box, False, False, 0)
        self.spinner = Gtk.Spinner()
        self.box.pack_end(self.spinner, False, False, 0)

    @property
    def sort_key(self):
        """An index indicate the place this row has within its type. The id is used
        as a tie-breaker."""
        return 0

    def get_actions(self):
        return []

    def is_row_active(self):
        """Return true if the row is hovered or is the one selected"""
        flags = self.get_state_flags()
        # Naming things sure is hard... But "prelight" instead of "hover"? Come on...
        return flags & Gtk.StateFlags.PRELIGHT or flags & Gtk.StateFlags.SELECTED

    def do_state_flags_changed(self, previous_flags):  # pylint: disable=arguments-differ
        if self.id:
            self.update_buttons()
        Gtk.ListBoxRow.do_state_flags_changed(self, previous_flags)

    def update_buttons(self):
        if self.is_updating:
            self.btn_box.hide()
            self.spinner.show()
            self.spinner.start()
            return
        self.spinner.stop()
        self.spinner.hide()
        if self.is_row_active():
            self.btn_box.show()
        elif self.btn_box.get_visible():
            self.btn_box.hide()

    def create_button_box(self):
        """Adds buttons in the button box based on the row's actions"""
        for child in self.btn_box.get_children():
            child.destroy()
        for action in self.get_actions():
            btn = Gtk.Button(tooltip_text=action[1], relief=Gtk.ReliefStyle.NONE, visible=True)
            image = Gtk.Image.new_from_icon_name(action[0], Gtk.IconSize.MENU)
            image.show()
            btn.add(image)
            btn.connect("clicked", action[2])
            self.buttons[action[3]] = btn
            self.btn_box.add(btn)

    def on_realize(self, widget):
        self.create_button_box()


class ServiceSidebarRow(SidebarRow):
    def __init__(self, service):
        super().__init__(service.id, "service", service.name, LutrisSidebar.get_sidebar_icon(service.icon))
        self.service = service

    @property
    def sort_key(self):
        return SERVICE_INDICES[self.id]

    def get_actions(self):
        """Return the definition of buttons to be added to the row"""
        displayed_buttons = []
        if self.service.is_launchable():
            displayed_buttons.append(("media-playback-start-symbolic", _("Run"), self.on_service_run, "run"))
        displayed_buttons.append(("view-refresh-symbolic", _("Reload"), self.on_refresh_clicked, "refresh"))
        return displayed_buttons

    def on_service_run(self, button):
        """Run a launcher associated with a service"""
        self.service.run(self.get_toplevel())

    def on_refresh_clicked(self, button):
        """Reload the service games"""
        button.set_sensitive(False)
        if self.service.online and not self.service.is_connected():
            self.service.logout()
            self.service.login(parent=self.get_toplevel())  # login will trigger reload if successful
            return
        self.service.start_reload(self.service_reloaded_cb)

    def service_reloaded_cb(self, error):
        if error:
            if isinstance(error, AuthTokenExpiredError):
                self.service.logout()
                self.service.login(parent=self.get_toplevel())  # login will trigger reload if successful
            else:
                display_error(error, parent=self.get_toplevel())
        schedule_at_idle(self.enable_refresh_button, delay_seconds=2.0)

    def enable_refresh_button(self) -> None:
        self.buttons["refresh"].set_sensitive(True)


class OnlineServiceSidebarRow(ServiceSidebarRow):
    def get_buttons(self):
        return {
            "run": (("media-playback-start-symbolic", _("Run"), self.on_service_run, "run")),
            "refresh": ("view-refresh-symbolic", _("Reload"), self.on_refresh_clicked, "refresh"),
            "disconnect": ("system-log-out-symbolic", _("Disconnect"), self.on_connect_clicked, "disconnect"),
            "connect": ("avatar-default-symbolic", _("Connect"), self.on_connect_clicked, "connect"),
        }

    def get_actions(self):
        buttons = self.get_buttons()
        displayed_buttons = []
        if self.service.is_launchable():
            displayed_buttons.append(buttons["run"])
        if self.service.is_authenticated():
            displayed_buttons += [buttons["refresh"], buttons["disconnect"]]
        else:
            displayed_buttons += [buttons["connect"]]
        return displayed_buttons

    def on_connect_clicked(self, button):
        button.set_sensitive(False)
        if self.service.is_authenticated():
            self.service.logout()
        else:
            self.service.login(parent=self.get_toplevel())
        self.create_button_box()


class RunnerSidebarRow(SidebarRow):
    def get_actions(self):
        """Return the definition of buttons to be added to the row"""
        if not self.id:
            return []
        entries = []

        # Creation is delayed because only installed runners can be imported
        # and all visible boxes should be installed.
        try:
            runner = self.get_runner()
        except InvalidRunnerError:
            return entries

        if runner.multiple_versions:
            entries.append(
                ("system-software-install-symbolic", _("Manage Versions"), self.on_manage_versions, "manage-versions")
            )
        if runner.runnable_alone:
            entries.append(("media-playback-start-symbolic", _("Run"), self.on_run_runner, "run"))
        entries.append(("emblem-system-symbolic", _("Configure"), self.on_configure_runner, "configure"))
        return entries

    def get_runner(self):
        return runners.import_runner(self.id)()

    def on_run_runner(self, *_args):
        """Runs the runner without no game."""
        runner = self.get_runner()
        runner.run(self.get_toplevel())

    def on_configure_runner(self, *_args):
        """Show runner configuration"""
        runner = self.get_runner()
        self.application.show_window(RunnerConfigDialog, runner=runner, parent=self.get_toplevel())

    def on_manage_versions(self, *_args):
        """Manage runner versions"""
        runner = self.get_runner()
        dlg_title = _("Manage %s versions") % runner.human_name
        self.application.show_window(RunnerInstallDialog, title=dlg_title, runner=runner, parent=self.get_toplevel())


class CategorySidebarRow(SidebarRow):
    def __init__(self, category, application):
        super().__init__(
            category["name"],
            "user_category",
            category["name"],
            LutrisSidebar.get_sidebar_icon("folder-symbolic"),
            application=application,
        )
        self.category = category

        self._sort_name = locale.strxfrm(category["name"])

    @property
    def sort_key(self):
        return get_natural_sort_key(self.name)

    def get_actions(self):
        """Return the definition of buttons to be added to the row"""
        return [("applications-system-symbolic", _("Edit Games"), self.on_category_clicked, "manage-category-games")]

    def on_category_clicked(self, button):
        category = categories_db.get_category_by_id(self.category["id"]) or self.category
        self.application.show_window(EditCategoryGamesDialog, category=category, parent=self.get_toplevel())
        return True

    def __lt__(self, other):
        if not isinstance(other, CategorySidebarRow):
            raise ValueError("Cannot compare %s to %s" % (self.__class__.__name__, other.__class__.__name__))

        return self._sort_name < other._sort_name

    def __gt__(self, other):
        if not isinstance(other, CategorySidebarRow):
            raise ValueError("Cannot compare %s to %s" % (self.__class__.__name__, other.__class__.__name__))

        return self._sort_name > other._sort_name


class SavedSearchSidebarRow(SidebarRow):
    def __init__(self, saved_search: saved_search_db.SavedSearch, application):
        super().__init__(
            saved_search.name,
            "saved_search",
            saved_search.name,
            LutrisSidebar.get_sidebar_icon("folder-saved-search-symbolic"),
            application=application,
        )
        self.saved_search = saved_search

        self._sort_name = locale.strxfrm(saved_search.name)

    @property
    def sort_key(self):
        return get_natural_sort_key(self.name)

    def get_actions(self):
        """Return the definition of buttons to be added to the row"""
        return [
            ("applications-system-symbolic", _("Edit Games"), self.on_saved_search_clicked, "manage-category-games")
        ]

    def on_saved_search_clicked(self, button):
        saved_search = saved_search_db.get_saved_search_by_id(self.saved_search.saved_search_id) or self.saved_search
        self.application.show_window(EditSavedSearchDialog, saved_search=saved_search, parent=self.get_toplevel())
        return True

    def __lt__(self, other):
        if not isinstance(other, SavedSearchSidebarRow):
            raise ValueError("Cannot compare %s to %s" % (self.__class__.__name__, other.__class__.__name__))

        return self._sort_name < other._sort_name

    def __gt__(self, other):
        if not isinstance(other, SavedSearchSidebarRow):
            raise ValueError("Cannot compare %s to %s" % (self.__class__.__name__, other.__class__.__name__))

        return self._sort_name > other._sort_name


class SidebarHeader(Gtk.Box):
    """Header shown on top of each sidebar section"""

    def __init__(self, name, header_index):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.header_index = header_index
        self.first_row = None

        label = Gtk.Label(
            halign=Gtk.Align.START,
            hexpand=True,
            use_markup=True,
            label="<b>{}</b>".format(name),
        )
        box = Gtk.Box(margin_start=9, margin_top=6, margin_bottom=6, margin_right=9)
        box.add(label)
        self.add(box)
        self.add(Gtk.Separator())
        self.show_all()


class DummyRow:
    """Dummy class for rows that may not be initialized."""

    def show(self):
        """Dummy method for showing the row"""

    def hide(self):
        """Dummy method for hiding the row"""


class LutrisSidebar(Gtk.ListBox):
    __gtype_name__ = "LutrisSidebar"

    def __init__(self, application):
        super().__init__()
        self.set_size_request(200, -1)
        self.application = application
        self.previous_category = None
        self.get_style_context().add_class("lutris-sidebar")

        # Empty values until LutrisWindow explicitly initializes the rows
        # at the right time.
        self.installed_runners = []
        self.runner_visibility_cache = {}
        self.used_categories = set()
        self.saved_searches = set()
        self.active_services = {}
        self.active_platforms = []
        self.service_rows = {}
        self.runner_rows = {}
        self.platform_rows = {}

        self.category_rows = {}
        self.saved_search_rows = {}
        # A dummy objects that allows inspecting why/when we have a show() call on the object.
        self.games_row = DummyRow()
        self.running_row = DummyRow()
        self.hidden_row = DummyRow()
        self.missing_row = DummyRow()
        self.row_headers = {
            "library": SidebarHeader(_("Library"), header_index=0),
            "user_category": SidebarHeader(_("Categories"), header_index=1),
            "saved_search": SidebarHeader(_("Saved Searches"), header_index=2),
            "service": SidebarHeader(_("Sources"), header_index=3),
            "runner": SidebarHeader(_("Runners"), header_index=4),
            "platform": SidebarHeader(_("Platforms"), header_index=5),
        }
        GObject.add_emission_hook(RunnerBox, "runner-installed", self.update_rows)
        GObject.add_emission_hook(RunnerBox, "runner-removed", self.update_rows)
        GObject.add_emission_hook(RunnerConfigDialog, "runner-updated", self.update_runner_rows)
        GObject.add_emission_hook(ScriptInterpreter, "runners-installed", self.update_rows)
        GObject.add_emission_hook(ServicesBox, "services-changed", self.update_rows)
        GAME_START.register(self.on_game_start)
        GAME_STOPPED.register(self.on_game_stopped)
        GAME_UPDATED.register(self.update_rows)
        CATEGORIES_UPDATED.register(self.update_rows)
        SAVED_SEARCHES_UPDATED.register(self.update_rows)
        SERVICE_LOGIN.register(self.on_service_auth_changed)
        SERVICE_LOGOUT.register(self.on_service_auth_changed)
        SERVICE_GAMES_LOADING.register(self.on_service_games_loading)
        SERVICE_GAMES_LOADED.register(self.on_service_games_loaded)
        LOCAL_LIBRARY_SYNCING.register(self.on_local_library_syncing)
        LOCAL_LIBRARY_SYNCED.register(self.on_local_library_synced)
        self.set_filter_func(self._filter_func)
        self.set_header_func(self._header_func)
        self.show_all()

    @staticmethod
    def get_sidebar_icon(icon_name: str, fallback_icon_names: List[str] = None) -> Gtk.Image:
        candidate_names = [icon_name] + (fallback_icon_names or [])
        candidate_names = [name for name in candidate_names if has_stock_icon(name)]

        # Even if this one is not a stock icon, we'll use it as a last resort and
        # get the 'broken icon' icon if it's not known.
        if not candidate_names:
            candidate_names = ["package-x-generic-symbolic"]

        icon = Gtk.Image.new_from_icon_name(candidate_names[0], Gtk.IconSize.MENU)

        # We can wind up with an icon of the wrong size, if that's what is
        # available. So we'll fix that.
        icon_size = Gtk.IconSize.lookup(Gtk.IconSize.MENU)
        if icon_size[0]:
            icon.set_pixel_size(icon_size[2])

        return icon

    def initialize_rows(self):
        """
        Select the initial row; this triggers the initialization of the game view,
        so we must do this even if this sidebar is never realized, but only after
        the sidebar's signals are connected.
        """

        # Create the basic rows that are not data dependant

        self.games_row = SidebarRow(
            "all",
            "category",
            _("Games"),
            self.get_sidebar_icon("applications-games-symbolic"),
        )
        self.add(self.games_row)

        self.add(
            SidebarRow(
                "recent",
                "dynamic_category",
                _("Recent"),
                self.get_sidebar_icon("document-open-recent-symbolic"),
            )
        )

        self.add(
            SidebarRow(
                "favorite",
                "category",
                _("Favorites"),
                self.get_sidebar_icon("favorite-symbolic"),
            )
        )

        self.add(
            SidebarRow(
                ".uncategorized",
                "dynamic_category",
                _("Uncategorized"),
                self.get_sidebar_icon("tag-symbolic", ["poi-marker", "favorite-symbolic"]),
            )
        )

        self.hidden_row = SidebarRow(
            ".hidden",
            "category",
            _("Hidden"),
            self.get_sidebar_icon("action-unavailable-symbolic"),
        )
        self.add(self.hidden_row)

        self.missing_row = SidebarRow(
            "missing",
            "dynamic_category",
            _("Missing"),
            self.get_sidebar_icon("dialog-warning-symbolic"),
        )
        self.add(self.missing_row)

        self.running_row = SidebarRow(
            "running",
            "dynamic_category",
            _("Running"),
            self.get_sidebar_icon("media-playback-start-symbolic"),
        )
        # I wanted this to be on top but it really messes with the headers when showing/hiding the row.
        self.add(self.running_row)
        self.show_all()
        self.hidden_row.hide()
        self.missing_row.hide()
        self.running_row.hide()

        # Create the dynamic rows that are initially needed
        self.update_rows()

    @property
    def selected_category(self):
        """The selected sidebar row, as a tuple of category type and category value,
        like ('service', 'lutris')."""
        row = self.get_selected_row()
        return (row.type, row.id) if row else ("category", "all")

    @selected_category.setter
    def selected_category(self, value):
        """Selects the row for the category indicated by a category tuple,
        like ('service', 'lutris')"""
        self.previous_category = self.selected_category
        selected_row_type, selected_row_id = value or ("category", "all")
        children = get_widget_children(self, SidebarRow)
        for row in children:
            if row.type == selected_row_type and row.id == selected_row_id:
                if row.get_visible():
                    self.select_row(row)
                    return

                break

        for row in children:
            if row.get_visible():
                self.select_row(row)
                return

    def _filter_func(self, row):
        def is_runner_visible(runner_name):
            if runner_name not in self.runner_visibility_cache:
                runner_config = LutrisConfig(runner_slug=row.id, options_supported={"visible_in_side_panel"})
                self.runner_visibility_cache[runner_name] = runner_config.runner_config.get(
                    "visible_in_side_panel", True
                )
            return self.runner_visibility_cache[runner_name]

        if not row or not row.id or row.type in ("category", "dynamic_category"):
            return True

        if row.type == "runner":
            if row.id is None:
                return True  # 'All'
            return row.id in self.installed_runners and is_runner_visible(row.id)

        if row.type == "user_category":
            allowed_ids = self.used_categories
        elif row.type == "saved_search":
            allowed_ids = self.saved_searches
        elif row.type == "service":
            allowed_ids = self.active_services
        else:
            allowed_ids = self.active_platforms

        return row.id in allowed_ids

    def _header_func(self, row, before):
        if not before:
            header = self.row_headers["library"]
        elif before.type in ("category", "dynamic_category") and row.type == "user_category":
            header = self.row_headers[row.type]
        elif before.type in ("category", "dynamic_category", "user_category") and row.type == "saved_search":
            header = self.row_headers[row.type]
        elif before.type in ("category", "dynamic_category", "user_category", "saved_search") and row.type == "service":
            header = self.row_headers[row.type]
        elif before.type == "service" and row.type == "runner":
            header = self.row_headers[row.type]
        elif before.type == "runner" and row.type == "platform":
            header = self.row_headers[row.type]
        else:
            header = None

        if header and row.get_header() != header:
            # GTK is messy here; a header can't belong to two rows at once,
            # so we must remove it from the one that owns it, if any, and
            # also from the sidebar itself. Then we can reuse it.
            if header.first_row:
                header.first_row.set_header(None)
                if header.get_parent() == self:
                    self.remove(header)
            header.first_row = row
            row.set_header(header)

    def update_runner_rows(self, *_args):
        self.runner_visibility_cache.clear()
        self.update_rows()
        return True

    def update_rows(self, *_args):
        """Generates any missing rows that are now needed, and re-evaluate the filter to hide
        any no longer needed. GTK has a lot of trouble dynamically updating and re-arranging
        rows, so this will have to do. This keeps the total row count down reasonably well."""

        def get_sort_key(row):
            """Returns a key used to sort the rows. This keeps rows for a header
            together, and rows in a hopefully reasonable order as we insert them."""
            header_row = self.row_headers.get(row.type) if row.type else None
            header_index = header_row.header_index if header_row else 0
            return header_index, row.sort_key, row.id

        def insert_row(row):
            """Find the best place to insert the row, to maintain order, and inserts it there."""
            index = 0
            seq = get_sort_key(row)
            while True:
                r = self.get_row_at_index(index)
                if not r or get_sort_key(r) > seq:
                    break
                index += 1

            row.show_all()
            self.insert(row, index)

        categories_db.remove_unused_categories()
        categories = [c for c in categories_db.get_categories() if not categories_db.is_reserved_category(c["name"])]
        saved_searches = saved_search_db.get_saved_searches()

        self.used_categories = {c["name"] for c in categories}
        self.saved_searches = {s.name for s in saved_searches}
        self.active_services = services.get_enabled_services()
        self.installed_runners = [runner.name for runner in runners.get_installed()]
        self.active_platforms = games_db.get_used_platforms()

        for service_name, service_class in self.active_services.items():
            if service_name not in self.service_rows:
                try:
                    service = service_class()
                    row_class = OnlineServiceSidebarRow if service.online else ServiceSidebarRow
                    service_row = row_class(service)
                    insert_row(service_row)
                    self.service_rows[service_name] = service_row
                except Exception as ex:
                    logger.exception("Sidebar row for '%s' could not be loaded: %s", service_name, ex)

        for runner_name in self.installed_runners:
            if runner_name not in self.runner_rows:
                try:
                    icon_name = runner_name.lower().replace(" ", "") + "-symbolic"
                    runner = runners.import_runner(runner_name)()
                    runner_row = RunnerSidebarRow(
                        runner_name,
                        "runner",
                        runner.human_name,
                        self.get_sidebar_icon(icon_name),
                        application=self.application,
                    )
                    insert_row(runner_row)
                    self.runner_rows[runner_name] = runner_row
                except Exception as ex:
                    logger.exception("Sidebar row for '%s' could not be loaded: %s", service_name, ex)

        for platform in self.active_platforms:
            if platform not in self.platform_rows:
                icon_name = platform.lower().replace(" ", "").replace("/", "_") + "-symbolic"
                platform_row = SidebarRow(
                    platform, "platform", platform, self.get_sidebar_icon(icon_name), application=self.application
                )
                self.platform_rows[platform] = platform_row
                insert_row(platform_row)

        for category in categories:
            if category["name"] not in self.category_rows:
                new_category_row = CategorySidebarRow(category, application=self.application)
                self.category_rows[category["name"]] = new_category_row
                insert_row(new_category_row)

        for saved_search in saved_searches:
            if saved_search.name not in self.saved_search_rows:
                new_saved_search_row = SavedSearchSidebarRow(saved_search, application=self.application)
                self.saved_search_rows[saved_search.name] = new_saved_search_row
                insert_row(new_saved_search_row)

        self.invalidate_filter()
        return True

    def on_game_start(self, _game: Game) -> None:
        """Show the "running" section when a game start"""
        self.running_row.show()

    def on_game_stopped(self, _game: Game) -> None:
        """Hide the "running" section when no games are running"""
        if not self.application.has_running_games:
            self.running_row.hide()

            if self.get_selected_row() == self.running_row:
                self.select_row(get_widget_children(self, SidebarRow)[0])

    def on_service_auth_changed(self, service):
        logger.debug("Service %s auth changed", service.id)
        if service.id in self.service_rows:
            self.service_rows[service.id].create_button_box()
            self.service_rows[service.id].update_buttons()
        else:
            logger.warning("Service %s is not found", service.id)
        return True

    def on_service_games_loading(self, service):
        logger.debug("Service %s games loading", service.id)
        if service.id in self.service_rows:
            self.service_rows[service.id].is_updating = True
            self.service_rows[service.id].update_buttons()
        else:
            logger.warning("Service %s is not found", service.id)
        return True

    def on_service_games_loaded(self, service):
        logger.debug("Service %s games loaded", service.id)
        if service.id in self.service_rows:
            self.service_rows[service.id].is_updating = False
            self.service_rows[service.id].update_buttons()
        else:
            logger.warning("Service %s is not found", service.id)
        return True

    def on_local_library_syncing(self):
        self.games_row.is_updating = True
        self.games_row.update_buttons()

    def on_local_library_synced(self):
        self.games_row.is_updating = False
        self.games_row.update_buttons()
