from gi.repository import Gtk, GObject, GLib
from lutris.gui.widgets import get_pixbuf_for_game


class GameItem(Gtk.VBox):
    def __init__(self, game, parent):
        super(GameItem, self).__init__()

        self.banner_type = 'banner'

        self.parent = parent
        self.game = game
        self.name = game['name']
        self.runner = game['runner']
        self.installed = game['installed']

        image = self.get_image()
        self.pack_start(image, False, False, 0)
        label = self.get_label()
        self.pack_start(label, False, False, 0)

        self.connect('button-press-event', self.popup_contextual_menu)
        self.show_all()

    def get_image(self):
        # For some reason, button-press-events are not registered by the image
        # so it needs to be wrapped in an EventBox
        eventbox = Gtk.EventBox()
        image = Gtk.Image()
        pixbuf = get_pixbuf_for_game(self.game['slug'],
                                     self.banner_type,
                                     self.game['installed'])
        image.set_from_pixbuf(pixbuf)
        eventbox.add(image)
        return eventbox

    def get_label(self):
        label = Gtk.Label(self.game['name'])
        label.set_size_request(184, 40)
        label.set_max_width_chars(20)
        label.set_property('wrap', True)
        label.set_justify(Gtk.Justification.CENTER)
        label.set_halign(Gtk.Align.CENTER)
        return label

    def popup_contextual_menu(self, widget, event):
        if event.button != 3:
            return
        self.parent.popup_contextual_menu(event, self)
        #try:
        #    view.current_path = view.get_path_at_pos(event.x, event.y)
        #    if view.current_path:
        #        pass
        #        #if type(view) is GameGridView:
        #        #    view.select_path(view.current_path)
        #        #elif type(view) is GameListView:
        #        #    view.set_cursor(view.current_path[0])
        #except ValueError:
        #    (_, path) = view.get_selection().get_selected()
        #    view.current_path = path

        #if view.current_path:
        #    game_row = self.get_row_by_id(self.selected_game)
        #    self.contextual_menu.popup(event, game_row)

class GameFlowBox(Gtk.FlowBox):
    __gsignals__ = {
        "game-selected": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-activated": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-installed": (GObject.SIGNAL_RUN_FIRST, None, (int,)),
    }

    def __init__(self, game_list):
        super(GameFlowBox, self).__init__()

        self.set_valign(Gtk.Align.START)

        self.connect('child-activated', self.on_child_activated)

        self.set_filter_func(self.filter_func)
        self.set_activate_on_single_click(False)

        self.contextual_menu = None

        self.filter_text = ''
        self.filter_runner = ''
        self.filter_installed = False

        self.game_list = game_list
        loader = self._fill_store_generator()
        GLib.idle_add(loader.__next__)

    @property
    def selected_game(self):
        children = self.get_selected_children()
        if not children:
            return
        game_item = children[0].get_children()[0]
        return game_item.game['id']

    def _fill_store_generator(self, step=50):
        """Generator to fill the model in steps."""
        n = 0
        for game in self.game_list:
            self.add(GameItem(game, self))
            n += 1
            if (n % step) == 0:
                yield True
        yield False

    def filter_func(self, child):
        game = child.get_children()[0]
        if self.filter_installed:
            if not game.installed:
                return False
        if self.filter_text:
            if self.filter_text.lower() not in game.name.lower():
                return False
        if self.filter_runner:
            if self.filter_runner != game.runner:
                return False
        return True

    def on_child_activated(self, widget, child):
        self.emit('game-activated')

    def get_child(self, game_item):
        for child in self.get_children():
            widget = child.get_children()[0]
            if widget == game_item:
                return child

    def popup_contextual_menu(self, event, widget):
        self.select_child(self.get_child(widget))
        self.contextual_menu.popup(event, game=widget.game)
