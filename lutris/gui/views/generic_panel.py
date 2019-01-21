from gi.repository import Gtk, Gdk
from lutris.gui.widgets.utils import get_pixbuf_for_panel, get_main_window
from lutris.gui.config.system import SystemConfigDialog


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
            b".game-scrolled { background-image: url(\"%s\"); }" % bg_path.encode("utf-8")
        )
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            bg_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def place_content(self):
        """Places widgets in the side panel"""
        self.put(self.get_preferences_button(), 272, 16)

    def get_preferences_button(self):
        preferences_button = Gtk.Button.new_from_icon_name("preferences-system-symbolic", Gtk.IconSize.MENU)
        preferences_button.set_tooltip_text("Preferences")
        preferences_button.set_size_request(32, 32)
        preferences_button.props.relief = Gtk.ReliefStyle.NONE
        preferences_button.connect("clicked", self.on_preferences_clicked)
        preferences_button.show()
        return preferences_button

    def on_preferences_clicked(self, button):
        SystemConfigDialog(get_main_window(button))
