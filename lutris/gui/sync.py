"""Window for importing games from third party services"""
from gi.repository import Gtk
from gi.repository.GdkPixbuf import Pixbuf
from lutris.gui.widgets.utils import get_icon, get_pixbuf
from lutris.services import get_services
from lutris.settings import read_setting, write_setting
from lutris.util.log import logger
from lutris.util.jobs import AsyncCall


class ServiceSyncBox(Gtk.Box):
    """Display components to import games from a service"""

    COL_SELECTED = 0
    COL_APPID = 1
    COL_NAME = 2
    COL_ICON = 3
    COL_DETAILS = 4

    def __init__(self, service, _dialog):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(12)
        self.set_margin_right(12)
        self.set_margin_left(12)
        self.set_margin_bottom(12)

        self.service = service
        self.identifier = service.__name__.split(".")[-1]
        self.icon_name = service.ICON
        self.name = service.NAME
        self.games = []
        self.store = None
        self.num_selected = 0

        title_box = Gtk.Box()
        label = Gtk.Label()
        label.set_markup("<b>{}</b>".format(self.name))
        title_box.pack_start(label, True, True, 0)

        self.connect_button = Gtk.Button()
        self.connect_button.connect("clicked", self.on_connect_clicked, self.service)
        if service.ONLINE:
            self._connect_button_toggle()
            title_box.add(self.connect_button)

        self.pack_start(title_box, False, False, 12)

        center_alignment = Gtk.Alignment()
        center_alignment.set(0.5, 0.5, 0.1, 0.1)

        spinner = Gtk.Spinner()
        spinner.start()
        center_alignment.add(spinner)
        self.content_widget = center_alignment
        self.pack_start(center_alignment, True, True, 0)

        actions = Gtk.Box(spacing=6)
        self.pack_start(actions, False, False, 0)

        if hasattr(service, "sync_with_lutris"):
            self.sync_button = Gtk.Button("Import games")
            self.sync_button.set_sensitive(False)
            self.sync_button.set_tooltip_text("Sync now")
            self.sync_button.connect(
                "clicked", self.on_sync_button_clicked, service.sync_with_lutris
            )
            actions.pack_start(self.sync_button, False, False, 0)

            self.sync_switch = Gtk.Switch()
            self.sync_switch.props.valign = Gtk.Align.CENTER
            self.sync_switch.connect("notify::active", self.on_switch_changed)

            if read_setting("sync_at_startup", self.identifier) == "True":
                self.sync_switch.set_state(True)
            actions.pack_start(Gtk.Alignment(), True, True, 0)
            actions.pack_start(self.sync_switch, False, False, 0)
            actions.pack_start(Gtk.Label("Sync all games at startup"), False, False, 0)

            if service.ONLINE and not service.is_connected():
                self.sync_switch.set_sensitive(False)
                self.sync_button.set_sensitive(False)

    def get_icon(self):
        """Return the icon for the service (used in tabs)"""
        icon = get_icon(self.icon_name, size=(24, 24))
        if icon:
            return icon
        return Gtk.Label(self.name)

    def on_connect_clicked(self, button, service):
        if service.is_connected():
            service.disconnect()
            self._connect_button_toggle()

            self.sync_switch.set_sensitive(False)
            self.sync_button.set_sensitive(False)

            # Disable sync on disconnect
            if self.sync_switch and self.sync_switch.get_active():
                self.sync_switch.set_state(False)
        else:
            service.connect()
            self._connect_button_toggle()
            self.sync_switch.set_sensitive(True)
            self.sync_button.set_sensitive(True)
            self.load_games()

    def _connect_button_toggle(self):
        icon_name = "user-offline-symbolic" \
            if self.service.is_connected() \
            else "user-available-symbolic"
        self.connect_button.set_image(Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU))

    def on_sync_button_clicked(self, _button, sync_method):
        """Called when the sync button is clicked.

        Launches the import of selected games
        """
        games = self.get_imported_games()
        AsyncCall(sync_method, self.on_service_synced, games)

    def on_service_synced(self, caller, data):
        """Called when games are imported"""
        # parent = self.get_toplevel()
        # if not isinstance(parent, Gtk.Window):
        #     # The sync dialog may have closed
        #     parent = Gio.Application.get_default().props.active_window
        logger.info("Games imported to library")

    def on_switch_changed(self, switch, data):
        state = switch.get_active()
        write_setting("sync_at_startup", state, self.identifier)

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

    def on_import_toggled(self, _widget, game_index):
        """Toggle state for import"""
        col = self.COL_SELECTED
        new_state = not self.store_filter[game_index][col]
        if new_state:
            self.num_selected += 1
        else:
            self.num_selected -= 1
        self.sync_button.set_sensitive(bool(self.num_selected))
        self.store_filter[game_index][col] = new_state

    def on_select_all(self, widget):
        self.num_selected = 0
        for game in self.store_filter:
            if widget.get_active():
                self.num_selected += 1
            game[self.COL_SELECTED] = widget.get_active()
        self.sync_button.set_sensitive(bool(self.num_selected))

    def get_store(self):
        """Return a ListStore for the games to import"""
        liststore = Gtk.ListStore(
            bool,  # import
            str,  # appid
            str,  # name
            Pixbuf,  # icon
            str,  # details
        )
        for game in sorted(self.games, key=lambda x: x.name):
            liststore.append(
                [
                    False,
                    game.appid,
                    game.name,
                    get_pixbuf(game.icon, (32, 32)),
                    str(game.details),
                ]
            )
        return liststore

    def get_game_list_widget(self):
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        filter_box = Gtk.Box(spacing=6)
        select_all_button = Gtk.CheckButton.new_with_label("Select all")
        select_all_button.connect("toggled", self.on_select_all)
        filter_box.add(select_all_button)

        search_entry = Gtk.Entry()
        search_entry.connect("changed", self.on_search_entry_changed)
        filter_box.pack_start(Gtk.Alignment(), True, True, 0)
        filter_box.add(Gtk.Label("Filter:"))
        filter_box.add(search_entry)
        content.pack_start(filter_box, False, False, 0)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_shadow_type(Gtk.ShadowType.ETCHED_OUT)
        scrolled_window.add(self.get_treeview(self.store_filter))
        content.pack_start(scrolled_window, True, True, 0)
        content.show_all()
        return content

    def load_games(self):
        """Load the list of games in a treeview"""
        if self.service.ONLINE and not self.service.is_connected():
            return
        self.games = self.service.load_games()
        self.store = self.get_store()

        self.current_filter = None
        self.store_filter = self.store.filter_new()
        self.store_filter.set_visible_func(self.store_filter_func)

        position = self.child_get_property(self.content_widget, 'position')
        self.content_widget.destroy()
        self.content_widget = self.get_game_list_widget()

        self.pack_start(self.content_widget, True, True, 0)
        self.reorder_child(self.content_widget, position)

    def store_filter_func(self, model, _iter, _data):
        if not self.current_filter:
            return True
        return self.current_filter.lower() in model[_iter][self.COL_NAME].lower()

    def on_search_entry_changed(self, widget):
        self.current_filter = widget.props.text
        self.store_filter.refilter()

    def get_imported_games(self):
        games = []
        for game in self.store:
            if game[self.COL_SELECTED]:
                games.append({
                    'appid': game[self.COL_APPID],
                    'name': game[self.COL_NAME],
                    'details': game[self.COL_DETAILS],
                })
        return games


class SyncServiceWindow(Gtk.ApplicationWindow):
    def __init__(self, application=None):
        super().__init__(title="Import local games", application=application)
        self.connect("delete-event", lambda *x: self.destroy())

        self.set_border_width(10)
        self.set_size_request(640, 480)

        notebook = Gtk.Notebook()
        notebook.set_tab_pos(Gtk.PositionType.LEFT)
        self.add(notebook)

        for service in get_services():
            sync_row = ServiceSyncBox(service, self)
            notebook.append_page(sync_row, sync_row.get_icon())
        notebook.connect("switch-page", self.on_page_change)
        self.show_all()

    def on_page_change(self, notebook, child, page_index):
        """Event handler to trigger game load"""
        current_page = notebook.get_current_page()
        if current_page == -1 and page_index > 0:
            return
        child.load_games()
