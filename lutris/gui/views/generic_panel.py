from gi.repository import Gtk, Gdk, Gio, Pango
from lutris.gui.widgets.utils import get_pixbuf_for_panel, get_pixbuf_for_game, get_main_window
from lutris.gui.config.system import SystemConfigDialog
from lutris.gui.widgets.utils import get_pixbuf_for_game


class GenericPanel(Gtk.Fixed):
    """Side panel displayed when no game is selected"""
    def __init__(self):
        super().__init__(visible=True)
        self.set_size_request(320, -1)
        self.get_style_context().add_class("game-panel")
        self.set_background()
        self.place_content()

    @property
    def background_id(self):
        return None

    def set_background(self):
        """Return the background image for the panel"""
        bg_path = get_pixbuf_for_panel(self.background_id)

        style = Gtk.StyleContext()
        style.add_class(Gtk.STYLE_CLASS_VIEW)
        bg_provider = Gtk.CssProvider()
        bg_provider.load_from_data(
            b".game-scrolled { background-image: url(\"%s\"); "
            b"background-repeat: no-repeat; }" % bg_path.encode("utf-8")
        )
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            bg_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def place_content(self):
        """Places widgets in the side panel"""
        self.put(self.get_preferences_button(), 272, 16)
        application = Gio.Application.get_default()
        games = application.running_games
        if games:
            running_label = Gtk.Label(visible=True)
            running_label.set_markup("<b>Running:</b>")
            self.put(running_label, 12, 328)
            self.put(self.get_running_games(games), 12, 360)

    def get_preferences_button(self):
        preferences_button = Gtk.Button.new_from_icon_name(
            "preferences-system-symbolic",
            Gtk.IconSize.MENU
        )
        preferences_button.set_tooltip_text("Preferences")
        preferences_button.set_size_request(32, 32)
        preferences_button.props.relief = Gtk.ReliefStyle.NONE
        preferences_button.connect("clicked", self.on_preferences_clicked)
        preferences_button.show()
        return preferences_button

    def on_preferences_clicked(self, button):
        SystemConfigDialog(get_main_window(button))

    def create_list_widget(self, game):
        box = Gtk.Box(
            spacing=6,
            margin_top=6,
            margin_bottom=6,
            margin_right=6,
            margin_left=6,
        )
        box.set_size_request(280, 32)

        icon = Gtk.Image.new_from_pixbuf(get_pixbuf_for_game(game.slug, "icon"))
        icon.show()
        box.add(icon)

        game_label = Gtk.Label(game.name, visible=True)
        game_label.set_ellipsize(Pango.EllipsizeMode.END)
        box.add(game_label)

        return box

    def get_running_games(self, games):
        listbox = Gtk.ListBox()
        listbox.bind_model(games, self.create_list_widget)
        listbox.show()
        return listbox
