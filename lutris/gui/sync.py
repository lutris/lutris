"""Window for importing games from third party services"""
from gi.repository import Gtk, Gio
from gi.repository.GdkPixbuf import Pixbuf
from lutris.gui.widgets.utils import get_icon, get_pixbuf
from lutris.gui.dialogs import NoticeDialog
from lutris.services import get_services
from lutris.settings import read_setting, write_setting
from lutris.util.log import logger
from lutris.util.jobs import AsyncCall


class ServiceSyncBox(Gtk.Box):
    """Display components to import games from a service"""

    content_index = 1

    COL_SELECTED = 0
    COL_APPID = 1
    COL_NAME = 2
    COL_ICON = 3
    COL_EXE = 4
    COL_ARGS = 5

    def __init__(self, service, _dialog):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(12)

        self.service = service
        self.identifier = service.__name__.split(".")[-1]
        self.icon_name = service.ICON
        self.name = service.NAME
        self.games = []

        label = Gtk.Label()
        label.set_markup("<b>{}</b>".format(self.name))
        self.pack_start(label, False, False, 20)

        center_alignment = Gtk.Alignment()
        center_alignment.set(0.5, 0.5, 0.1, 0.1)

        if hasattr(service, "connect"):
            self.connect_button = Gtk.Button()
            self.connect_button.connect("clicked", self.on_connect_clicked, service)
            self._connect_button_toggle(service.is_connected())
            center_alignment.add(self.connect_button)
        else:
            spinner = Gtk.Spinner()
            spinner.start()
            center_alignment.add(spinner)
        self.pack_start(center_alignment, True, True, 0)

        actions = Gtk.Box()
        self.pack_start(actions, False, False, 10)

        if hasattr(service, "sync_with_lutris"):
            self.sync_button = Gtk.Button("Import games")
            self.sync_button.set_tooltip_text("Sync now")
            self.sync_button.connect(
                "clicked", self.on_sync_button_clicked, service.sync_with_lutris
            )
            actions.pack_start(self.sync_button, False, False, 10)

            self.sync_switch = Gtk.Switch()
            self.sync_switch.props.valign = Gtk.Align.CENTER
            self.sync_switch.connect("notify::active", self.on_switch_changed)

            if read_setting("sync_at_startup", self.identifier) == "True":
                self.sync_switch.set_state(True)
            actions.pack_start(self.sync_switch, False, False, 10)
            actions.pack_start(Gtk.Label("Sync (Re-import all games at startup)"), False, False, 10)

            if hasattr(service, "connect") and not service.is_connected():
                self.sync_switch.set_sensitive(False)
                self.sync_button.set_sensitive(False)

        if hasattr(service, "load_games"):
            self.load_games()

    def get_icon(self):
        """Return the icon for the service (used in tabs)"""
        icon = get_icon(self.icon_name)
        if icon:
            return icon
        return Gtk.Label(self.name)

    def on_connect_clicked(self, button, service):
        if service.is_connected():
            service.disconnect()
            self._connect_button_toggle(False)

            self.sync_switch.set_sensitive(False)
            self.sync_button.set_sensitive(False)

            # Disable sync on disconnect
            if self.sync_switch and self.sync_switch.get_active():
                self.sync_switch.set_state(False)
        else:
            service.connect()
            self._connect_button_toggle(True)
            self.sync_switch.set_sensitive(True)
            self.sync_button.set_sensitive(True)

    def _connect_button_toggle(self, is_connected):
        self.connect_button.set_label("Disconnect" if is_connected else "Connect")

    def on_sync_button_clicked(self, button, sync_method):
        """Called when the sync button is clicked.

        Launches the import of selected games
        """
        games = self.get_imported_games()
        AsyncCall(sync_method, self.on_service_synced, games)

    def on_service_synced(self, caller, data):
        """Called when games are imported"""
        parent = self.get_toplevel()
        if not isinstance(parent, Gtk.Window):
            # The sync dialog may have closed
            parent = Gio.Application.get_default().props.active_window
        logger.info("Games imported to library")

    def on_switch_changed(self, switch, data):
        state = switch.get_active()
        write_setting("sync_at_startup", state, self.identifier)

    def get_content_widget(self):
        for index, child in enumerate(self.get_children()):
            if index == self.content_index:
                return child

    def get_treeview(self, model):
        treeview = Gtk.TreeView(model=model)
        treeview.set_headers_visible(False)

        renderer_toggle = Gtk.CellRendererToggle()
        renderer_toggle.connect("toggled", self.on_import_toggled)

        renderer_text = Gtk.CellRendererText()

        import_column = Gtk.TreeViewColumn("Import", renderer_toggle, active=self.COL_SELECTED)
        treeview.append_column(import_column)

        image_cell = Gtk.CellRendererPixbuf()
        icon_column = Gtk.TreeViewColumn("", image_cell, pixbuf=self.COL_ICON)
        treeview.append_column(icon_column)

        name_column = Gtk.TreeViewColumn(None, renderer_text)
        name_column.add_attribute(renderer_text, "text", self.COL_NAME)
        name_column.set_property("min-width", 80)
        treeview.append_column(name_column)
        return treeview

    def on_import_toggled(self, widget, game_index):
        """Toggle state for import"""
        self.store[game_index][self.COL_SELECTED] = not self.store[game_index][self.COL_SELECTED]

    def get_store(self):
        """Return a ListStore for the games to import"""
        liststore = Gtk.ListStore(
            bool,  # import
            str,  # appid
            str,  # name
            Pixbuf,  # icon
            str,  # exe
            str,  # args
        )
        for game in sorted(self.games, key=lambda x: x.name):
            liststore.append(
                [
                    False,
                    game.appid,
                    game.name,
                    get_pixbuf(game.icon, (32, 32)),
                    game.exe,
                    game.args
                ]
            )
        return liststore

    def load_games(self):
        """Load the list of games in a treeview"""
        self.games = self.service.load_games()
        self.store = self.get_store()
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                   Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_shadow_type(Gtk.ShadowType.ETCHED_OUT)
        treeview = self.get_treeview(self.store)
        spinner = self.get_content_widget()
        spinner.destroy()
        scrolled_window.add(treeview)
        self.pack_start(scrolled_window, True, True, 0)
        self.reorder_child(scrolled_window, self.content_index)

    def get_imported_games(self):
        games = []
        for game in self.store:
            if game[self.COL_SELECTED]:
                games.append({
                    'appid': game[self.COL_APPID],
                    'name': game[self.COL_NAME],
                    'exe': game[self.COL_EXE],
                    'args': game[self.COL_ARGS],
                })
        return games

class SyncServiceWindow(Gtk.Window):
    def __init__(self, parent=None):
        super().__init__(title="Import local games", parent=parent)
        self.connect("delete-event", lambda *x: self.destroy())

        self.set_border_width(10)
        self.set_size_request(640, 480)

        notebook = Gtk.Notebook()
        notebook.set_tab_pos(Gtk.PositionType.LEFT)
        self.add(notebook)

        for service in get_services():
            sync_row = ServiceSyncBox(service, self)
            notebook.append_page(sync_row, sync_row.get_icon())
        self.show_all()
