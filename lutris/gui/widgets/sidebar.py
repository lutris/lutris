"""Sidebar for the main window"""
from gettext import gettext as _

from gi.repository import GLib, GObject, Gtk, Pango

from lutris import runners, services
from lutris.database import games as games_db
from lutris.exceptions import watch_errors
from lutris.game import Game
from lutris.gui import dialogs
from lutris.gui.config.runner import RunnerConfigDialog
from lutris.gui.config.runner_box import RunnerBox
from lutris.gui.config.services_box import ServicesBox
from lutris.gui.dialogs import ErrorDialog
from lutris.gui.dialogs.runner_install import RunnerInstallDialog
from lutris.gui.widgets.utils import has_stock_icon
from lutris.installer.interpreter import ScriptInterpreter
from lutris.services.base import AuthTokenExpired, BaseService
from lutris.util.jobs import AsyncCall

TYPE = 0
SLUG = 1
ICON = 2
LABEL = 3
GAMECOUNT = 4


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
        self.runner = None
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
        super().__init__(
            service.id,
            "service",
            service.name,
            LutrisSidebar.get_sidebar_icon(service.icon)
        )
        self.service = service

    def get_actions(self):
        """Return the definition of buttons to be added to the row"""
        displayed_buttons = []
        if self.service.is_launchable():
            displayed_buttons.append(
                ("media-playback-start-symbolic", _("Run"), self.on_service_run, "run")
            )
        displayed_buttons.append(
            ("view-refresh-symbolic", _("Reload"), self.on_refresh_clicked, "refresh")
        )
        return displayed_buttons

    def on_service_run(self, button):
        """Run a launcher associated with a service"""
        self.service.run()

    def on_refresh_clicked(self, button):
        """Reload the service games"""
        button.set_sensitive(False)
        if self.service.online and not self.service.is_connected():
            self.service.logout()
            return
        AsyncCall(self.service.reload, self.service_load_cb)

    def service_load_cb(self, _result, error):
        if error:
            if isinstance(error, AuthTokenExpired):
                self.service.logout()
                self.service.login(parent=self.get_toplevel())
            else:
                ErrorDialog(str(error), parent=self.get_toplevel())
        GLib.timeout_add(2000, self.enable_refresh_button)

    def enable_refresh_button(self):
        self.buttons["refresh"].set_sensitive(True)
        return False


class OnlineServiceSidebarRow(ServiceSidebarRow):
    def get_buttons(self):
        return {
            "run": (("media-playback-start-symbolic", _("Run"), self.on_service_run, "run")),
            "refresh": ("view-refresh-symbolic", _("Reload"), self.on_refresh_clicked, "refresh"),
            "disconnect": ("system-log-out-symbolic", _("Disconnect"), self.on_connect_clicked, "disconnect"),
            "connect": ("avatar-default-symbolic", _("Connect"), self.on_connect_clicked, "connect")
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
        self.runner = runners.import_runner(self.id)()
        if self.runner.multiple_versions:
            entries.append((
                "system-software-install-symbolic",
                _("Manage Versions"),
                self.on_manage_versions,
                "manage-versions"
            ))
        if self.runner.runnable_alone:
            entries.append(("media-playback-start-symbolic", _("Run"), self.on_run_runner, "run"))
        entries.append(("emblem-system-symbolic", _("Configure"), self.on_configure_runner, "configure"))
        return entries

    @watch_errors()
    def on_run_runner(self, *_args):
        """Runs the runner without no game."""
        self.runner.run(self.get_toplevel())

    @watch_errors()
    def on_configure_runner(self, *_args):
        """Show runner configuration"""
        self.application.show_window(RunnerConfigDialog, runner=self.runner)

    @watch_errors()
    def on_manage_versions(self, *_args):
        """Manage runner versions"""
        dlg_title = _("Manage %s versions") % self.runner.name
        self.application.show_window(RunnerInstallDialog, title=dlg_title,
                                     runner=self.runner, parent=self.get_toplevel())

    def on_watched_error(self, error):
        dialogs.ErrorDialog(str(error), parent=self.get_toplevel())


class SidebarHeader(Gtk.Box):
    """Header shown on top of each sidebar section"""

    def __init__(self, name, header_index):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.header_index = header_index
        self.first_row = None
        self.get_style_context().add_class("sidebar-header")
        label = Gtk.Label(
            halign=Gtk.Align.START,
            hexpand=True,
            use_markup=True,
            label="<b>{}</b>".format(name),
        )
        label.get_style_context().add_class("dim-label")
        box = Gtk.Box(margin_start=9, margin_top=6, margin_bottom=6, margin_right=9)
        box.add(label)
        self.add(box)
        self.add(Gtk.Separator())
        self.show_all()


class DummyRow():
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
        self.get_style_context().add_class("sidebar")

        # Empty values until LutrisWindow explicitly initializes the rows
        # at the right time.
        self.installed_runners = []
        self.active_services = {}
        self.active_platforms = []
        self.service_rows = {}
        self.runner_rows = {}
        self.platform_rows = {}

        # A dummy objects that allows inspecting why/when we have a show() call on the object.
        self.running_row = DummyRow()
        self.missing_row = DummyRow()
        self.row_headers = {
            "library": SidebarHeader(_("Library"), header_index=0),
            "service": SidebarHeader(_("Sources"), header_index=1),
            "runner": SidebarHeader(_("Runners"), header_index=2),
            "platform": SidebarHeader(_("Platforms"), header_index=3),
        }
        GObject.add_emission_hook(RunnerBox, "runner-installed", self.update_rows)
        GObject.add_emission_hook(RunnerBox, "runner-removed", self.update_rows)
        GObject.add_emission_hook(ScriptInterpreter, "runners-installed", self.update_rows)
        GObject.add_emission_hook(ServicesBox, "services-changed", self.update_rows)
        GObject.add_emission_hook(Game, "game-start", self.on_game_start)
        GObject.add_emission_hook(Game, "game-stop", self.on_game_stop)
        GObject.add_emission_hook(Game, "game-updated", self.update_rows)
        GObject.add_emission_hook(Game, "game-removed", self.update_rows)
        GObject.add_emission_hook(BaseService, "service-login", self.on_service_auth_changed)
        GObject.add_emission_hook(BaseService, "service-logout", self.on_service_auth_changed)
        GObject.add_emission_hook(BaseService, "service-games-load", self.on_service_games_updating)
        GObject.add_emission_hook(BaseService, "service-games-loaded", self.on_service_games_updated)
        self.set_filter_func(self._filter_func)
        self.set_header_func(self._header_func)
        self.show_all()

    @staticmethod
    def get_sidebar_icon(icon_name):
        name = icon_name if has_stock_icon(icon_name) else "package-x-generic-symbolic"
        icon = Gtk.Image.new_from_icon_name(name, Gtk.IconSize.MENU)

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

        self.add(
            SidebarRow(
                "all",
                "category",
                _("Games"),
                Gtk.Image.new_from_icon_name("applications-games-symbolic", Gtk.IconSize.MENU)
            )
        )

        self.add(
            SidebarRow(
                "recent",
                "dynamic_category",
                _("Recent"),
                Gtk.Image.new_from_icon_name("document-open-recent-symbolic", Gtk.IconSize.MENU)
            )
        )

        self.add(
            SidebarRow(
                "favorite",
                "category",
                _("Favorites"),
                Gtk.Image.new_from_icon_name("favorite-symbolic", Gtk.IconSize.MENU)
            )
        )
        self.missing_row = SidebarRow(
            "missing",
            "dynamic_category",
            _("Missing"),
            Gtk.Image.new_from_icon_name("dialog-warning-symbolic", Gtk.IconSize.MENU)
        )
        self.add(self.missing_row)

        self.running_row = SidebarRow(
            "running",
            "dynamic_category",
            _("Running"),
            Gtk.Image.new_from_icon_name("media-playback-start-symbolic", Gtk.IconSize.MENU)
        )
        # I wanted this to be on top but it really messes with the headers when showing/hiding the row.
        self.add(self.running_row)
        self.show_all()
        self.running_row.hide()

        # Create the dynamic rows that are initially needed
        self.update_rows()

    @property
    def selected_category(self):
        """The selected sidebar row, as a tuple of category and category value,
        like ('service', 'lutris')."""
        row = self.get_selected_row()
        return (row.type, row.id) if row else ("category", "all")

    @selected_category.setter
    def selected_category(self, value):
        """Selects the rrow for the category indicated by a category tuple,
        like ('service', 'lutris')"""
        selected_row_type, selected_row_id = value or ("category", "all")
        for row in self.get_children():
            if row.type == selected_row_type and row.id == selected_row_id:
                self.select_row(row)
                break

    def _filter_func(self, row):
        if not row or not row.id or row.type in ("category", "dynamic_category"):
            return True
        if row.type == "service":
            return row.id in self.active_services
        if row.type == "runner":
            if row.id is None:
                return True  # 'All'
            return row.id in self.installed_runners
        return row.id in self.active_platforms

    def _header_func(self, row, before):
        if not before:
            header = self.row_headers["library"]
        elif before.type in ("category", "dynamic_category") and row.type == "service":
            header = self.row_headers[row.type]
        elif before.type == "service" and row.type == "runner":
            header = self.row_headers[row.type]
        elif before.type == "runner" and row.type == "platform":
            header = self.row_headers[row.type]
        else:
            header = None

        if row.get_header() != header:
            # GTK is messy here; a header can't belong to two rows at once,
            # so we must remove it from the one that owns it, if any, and
            # also from the sidebar itself. Then we can reuse it.
            if header.first_row:
                header.first_row.set_header(None)
                if header.get_parent() == self:
                    self.remove(header)
            header.first_row = row
            row.set_header(header)

    def update_rows(self, *_args):
        """Generates any missing rows that are now needed, and re-evaluate the filter to hide
        any no longer needed. GTK has a lot of trouble dynamically updating and re-arranging
        rows, so this will have to do. This keeps the total row count down reasonably well."""

        def get_sort_key(row):
            """Returns a key used to sort the rows. This keeps rows for a header
            together, and rows in a hopefully reasonable order as we insert them."""
            header_row = self.row_headers.get(row.type) if row.type else None
            header_index = header_row.header_index if header_row else 0
            return header_index, row.id

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

        self.active_services = services.get_enabled_services()
        self.installed_runners = [runner.name for runner in runners.get_installed()]
        self.active_platforms = games_db.get_used_platforms()

        for service_name, service_class in self.active_services.items():
            if service_name not in self.service_rows:
                service = service_class()
                row_class = OnlineServiceSidebarRow if service.online else ServiceSidebarRow
                service_row = row_class(service)
                self.service_rows[service_name] = service_row
                insert_row(service_row)

        for runner_name in self.installed_runners:
            if runner_name not in self.runner_rows:
                icon_name = runner_name.lower().replace(" ", "") + "-symbolic"
                runner = runners.import_runner(runner_name)()
                runner_row = RunnerSidebarRow(
                    runner_name,
                    "runner",
                    runner.human_name,
                    self.get_sidebar_icon(icon_name),
                    application=self.application
                )
                self.runner_rows[runner_name] = runner_row
                insert_row(runner_row)

        for platform in self.active_platforms:
            if platform not in self.platform_rows:
                icon_name = (platform.lower().replace(" ", "").replace("/", "_") + "-symbolic")
                platform_row = SidebarRow(
                    platform,
                    "platform",
                    platform,
                    self.get_sidebar_icon(icon_name),
                    application=self.application
                )
                self.platform_rows[platform] = platform_row
                insert_row(platform_row)

        self.invalidate_filter()
        return True

    def on_game_start(self, _game):
        """Show the "running" section when a game start"""
        self.running_row.show()
        return True

    def on_game_stop(self, _game):
        """Hide the "running" section when no games are running"""
        if not self.application.running_games.get_n_items():
            self.running_row.hide()

            if self.get_selected_row() == self.running_row:
                self.select_row(self.get_children()[0])

        return True

    def on_service_auth_changed(self, service):
        self.service_rows[service.id].create_button_box()
        self.service_rows[service.id].update_buttons()
        return True

    def on_service_games_updating(self, service):
        self.service_rows[service.id].is_updating = True
        self.service_rows[service.id].update_buttons()
        return True

    def on_service_games_updated(self, service):
        self.service_rows[service.id].is_updating = False
        self.service_rows[service.id].update_buttons()
        return True
