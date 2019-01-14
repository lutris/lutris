"""Unused flowbox view (most code removed)"""
from gi.repository import Gtk, Gdk, GObject

from lutris.gui.widgets.utils import get_pixbuf_for_game
from lutris.game import Game

try:
    FlowBox = Gtk.FlowBox
    FLOWBOX_SUPPORTED = True
except AttributeError:
    FlowBox = object
    FLOWBOX_SUPPORTED = False


class GameItem(Gtk.VBox):
    def __init__(self, game, parent, icon_type="banner"):
        super(GameItem, self).__init__()

        self.icon_type = icon_type

        self.parent = parent
        self.game = Game(game["id"])
        self.id = game["id"]
        self.name = game["name"]
        self.slug = game["slug"]
        self.runner = game["runner"]
        self.platform = game["platform"]
        self.installed = game["installed"]

        image = self.get_image()
        self.pack_start(image, False, False, 0)
        label = self.get_label()
        self.pack_start(label, False, False, 0)

        self.connect("button-press-event", self.popup_contextual_menu)
        self.show_all()

    def get_image(self):
        # For some reason, button-press-events are not registered by the image
        # so it needs to be wrapped in an EventBox
        eventbox = Gtk.EventBox()
        self.image = Gtk.Image()
        self.set_image_pixbuf()
        eventbox.add(self.image)
        return eventbox

    def set_image_pixbuf(self):
        pixbuf = get_pixbuf_for_game(self.slug, self.icon_type, self.installed)
        self.image.set_from_pixbuf(pixbuf)

    def get_label(self):
        self.label = Gtk.Label(self.name)
        self.label.set_size_request(184, 40)

        if self.icon_type == "banner":
            self.label.set_max_width_chars(20)
        else:
            self.label.set_max_width_chars(15)

        self.label.set_property("wrap", True)
        self.label.set_justify(Gtk.Justification.CENTER)
        self.label.set_halign(Gtk.Align.CENTER)
        eventbox = Gtk.EventBox()
        eventbox.add(self.label)
        return eventbox

    def set_label_text(self, text):
        self.label.set_text(text)

    def popup_contextual_menu(self, widget, event):
        if event.button != 3:
            return
        self.parent.popup_contextual_menu(event, self)


class GameFlowBox(FlowBox):
    __gsignals__ = {
        "game-selected": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-activated": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-installed": (GObject.SIGNAL_RUN_FIRST, None, (int,)),
        "remove-game": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, game_list, icon_type="banner", filter_installed=False):
        super(GameFlowBox, self).__init__()

        self.set_valign(Gtk.Align.START)

        self.connect("child-activated", self.on_child_activated)
        self.connect("selected-children-changed", self.on_selection_changed)
        self.connect("key-press-event", self.handle_key_press)

        self.set_filter_func(self.filter_func)
        self.set_sort_func(self.sort_func)
        self.set_activate_on_single_click(False)
        self.set_max_children_per_line(1)
        self.set_max_children_per_line(20)

        self.contextual_menu = None

        self.icon_type = icon_type

        self.filter_text = ""
        self.filter_runner = None
        self.filter_platform = None
        self.filter_installed = filter_installed

        self.game_list = game_list

    @property
    def selected_game(self):
        """Because of shitty naming conventions in previous Game views, this
        returns an id and not a game.
        """
        children = self.get_selected_children()
        if not children:
            return None
        game_item = children[0].get_children()[0]
        return game_item.game.id

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
        if self.filter_platform:
            if not game.game.runner:
                return False
            if self.filter_platform != game.game.platform:
                return False
        return True

    @staticmethod
    def sort_func(child1, child2):
        game1 = child1.get_children()[0]
        game2 = child2.get_children()[0]
        if game1.name.lower() > game2.name.lower():
            return 1
        elif game1.name.lower() < game2.name.lower():
            return -1
        else:
            return 0

    def on_child_activated(self, widget, child):
        self.emit("game-activated")

    def on_selection_changed(self, widget):
        self.emit("game-selected")

    def get_child(self, game_item):
        for child in self.get_children():
            widget = child.get_children()[0]
            if widget == game_item:
                return child

    def set_selected_game(self, game_id):
        for game in self.game_list:
            if game["id"] == game_id:
                self.select_child(self.get_child(game["item"]))

    def popup_contextual_menu(self, event, widget):
        self.select_child(self.get_child(widget))
        self.contextual_menu.popup(event, game=widget.game)

    def handle_key_press(self, widget, event):
        if not self.selected_game:
            return
        key = event.keyval
        if key == Gdk.KEY_Delete:
            self.emit("remove-game")
