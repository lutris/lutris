from lutris import pga
from lutris.runners import import_runner
from lutris.util.log import logger
from gi.repository import Gtk, Gdk, GObject, GLib
from lutris.gui.widgets import get_pixbuf_for_game

try:
    FlowBox = Gtk.FlowBox
    FLOWBOX_SUPPORTED = True
except AttributeError:
    FlowBox = object
    FLOWBOX_SUPPORTED = False


class GameItem(Gtk.VBox):
    def __init__(self, game, parent, icon_type='banner'):
        super(GameItem, self).__init__()

        self.icon_type = icon_type

        self.parent = parent
        self.game = game
        self.name = game['name']
        self.slug = game['slug']
        self.runner = game['runner']
        self.platform = game['platform']
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
        self.image = Gtk.Image()
        self.set_image_pixpuf()
        eventbox.add(self.image)
        return eventbox

    def set_image_pixpuf(self):
        pixbuf = get_pixbuf_for_game(self.slug,
                                     self.icon_type,
                                     self.installed)
        self.image.set_from_pixbuf(pixbuf)

    def get_label(self):
        self.label = Gtk.Label(self.game['name'])
        self.label.set_size_request(184, 40)

        if self.icon_type == 'banner':
            self.label.set_max_width_chars(20)
        else:
            self.label.set_max_width_chars(15)

        self.label.set_property('wrap', True)
        self.label.set_justify(Gtk.Justification.CENTER)
        self.label.set_halign(Gtk.Align.CENTER)
        return self.label

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
        "remove-game": (GObject.SIGNAL_RUN_FIRST, None, ())
    }

    def __init__(self, game_list, icon_type='banner', filter_installed=False):
        super(GameFlowBox, self).__init__()

        self.set_valign(Gtk.Align.START)

        self.connect('child-activated', self.on_child_activated)
        self.connect('selected-children-changed', self.on_selection_changed)
        self.connect('key-press-event', self.handle_key_press)

        self.set_filter_func(self.filter_func)
        self.set_sort_func(self.sort_func)
        self.set_activate_on_single_click(False)
        self.set_max_children_per_line(1)
        self.set_max_children_per_line(20)

        self.contextual_menu = None

        self.icon_type = icon_type

        self.filter_text = ''
        self.filter_runner = None
        self.filter_platform = None
        self.filter_installed = filter_installed

        self.game_list = game_list
        self.populate_games(self.game_list)

    @property
    def selected_game(self):
        """Because of shitty naming conventions in previous Game views, this
        returns an id and not a game.
        """
        children = self.get_selected_children()
        if not children:
            return
        game_item = children[0].get_children()[0]
        return game_item.game['id']

    def populate_games(self, games):
        loader = self._fill_store_generator(games)
        GLib.idle_add(loader.__next__)

    def _fill_store_generator(self, games, step=50):
        """Generator to fill the model in steps."""
        n = 0
        for game in games:
            item = GameItem(game, self, icon_type=self.icon_type)
            game['item'] = item  # keep a reference of created widgets
            self.add(item)
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
        if self.filter_platform:
            platform = game.platform
            if not platform and game.runner:
                runner = import_runner(game.runner)()
                if runner and runner.is_installed():
                    platform = runner.platform
            if self.filter_platform != platform:
                return False
        return True

    def sort_func(self, child1, child2):
        game1 = child1.get_children()[0]
        game2 = child2.get_children()[0]
        if game1.name.lower() > game2.name.lower():
            return 1
        elif game1.name.lower() < game2.name.lower():
            return -1
        else:
            return 0

    def on_child_activated(self, widget, child):
        self.emit('game-activated')

    def on_selection_changed(self, widget):
        self.emit('game-selected')

    def get_child(self, game_item):
        for child in self.get_children():
            widget = child.get_children()[0]
            if widget == game_item:
                return child

    def has_game_id(self, game_id):
        for game in self.game_list:
            if game['id'] == game_id:
                return True
        return False

    def add_game_by_id(self, game_id):
        if not game_id:
            return
        game = pga.get_game_by_field(game_id, 'id')
        if not game or 'slug' not in game:
            raise ValueError('Can\'t find game {} ({})'.format(
                game_id, game
            ))
        self.add_game(game)

    def add_game(self, game):
        item = GameItem(game, self)
        game['item'] = item
        self.add(item)
        self.game_list.append(game)

    def remove_game(self, game_id):
        for index, game in enumerate(self.game_list):
            if game['id'] == game_id:
                child = self.get_child(game['item'])
                self.remove(child)
                self.game_list.pop(index)
                return

    def set_installed(self, game):
        for index, _game in enumerate(self.game_list):
            if game.id == _game['id']:
                _game['runner'] = game.runner_name
                _game['installed'] = True
                self.update_image(_game['id'], True)

    def set_uninstalled(self, game):
        for index, _game in enumerate(self.game_list):
            if game.id == _game['id']:
                _game['runner'] = ''
                _game['installed'] = False
                self.update_image(_game['id'], False)

    def update_row(self, game):
        for index, _game in enumerate(self.game_list):
            if game['id'] == _game['id']:
                self.update_image(game['id'], _game['installed'])

    def update_image(self, game_id, is_installed):
        for index, game in enumerate(self.game_list):
            if game['id'] == game_id:
                item = game.get('item')
                if not item:
                    logger.error("Couldn't get item for game %s", game)
                    return
                item.installed = is_installed
                item.set_image_pixpuf()

    def set_selected_game(self, game_id):
        for game in self.game_list:
            if game['id'] == game_id:
                self.select_child(self.get_child(game['item']))

    def popup_contextual_menu(self, event, widget):
        self.select_child(self.get_child(widget))
        self.contextual_menu.popup(event, game=widget.game)

    def handle_key_press(self, widget, event):
        if not self.selected_game:
            return
        key = event.keyval
        if key == Gdk.KEY_Delete:
            self.emit("remove-game")
