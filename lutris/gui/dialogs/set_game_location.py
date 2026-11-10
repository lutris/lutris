from gettext import gettext as _

from gi.repository import Gtk

from lutris.gui.dialogs import ModalDialog
from lutris.gui.widgets.common import FileChooserEntry

KEEP_ACTION = "keep"
MOVE_ACTION = "move"


class SetLocationDialog(ModalDialog):
    def __init__(self, parent: Gtk.Window | None = None, default_path: str = "") -> None:
        super().__init__(parent=parent, border_width=24)

        self.set_title("Set Game Location")

        self.action = KEEP_ACTION

        frame = Gtk.Frame(label=_("Location"), visible=True, shadow_type=Gtk.ShadowType.ETCHED_OUT)
        frame_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, visible=True)
        frame.add(frame_vbox)

        game_location_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, margin_start=12, margin_end=12)
        game_location_label = Gtk.Label(label=_("Game location:"))
        self._game_location_chooser = FileChooserEntry(
            title=_("Select folder"),
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            text=default_path,
            default_path=default_path,
        )
        self._game_location_chooser.set_valign(Gtk.Align.CENTER)
        self._game_location_chooser.set_size_request(400, -1)
        game_location_box.pack_start(game_location_label, False, False, 0)
        game_location_box.pack_start(self._game_location_chooser, True, True, 0)

        self.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        self.add_default_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)

        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 6)
        keep_button = Gtk.RadioButton.new_with_label_from_widget(None, _("Game is already at location"))
        keep_button.connect("toggled", self.on_button_toggled, KEEP_ACTION)
        vbox.pack_start(keep_button, False, False, 0)
        move_button = Gtk.RadioButton.new_from_widget(keep_button)
        move_button.set_label(_("Move game to location"))
        move_button.connect("toggled", self.on_button_toggled, MOVE_ACTION)
        vbox.pack_start(move_button, False, False, 0)

        frame_vbox.pack_start(game_location_box, False, False, 0)
        frame_vbox.pack_start(vbox, False, False, 0)

        self.get_content_area().add(frame)

        self.show_all()
        self.run()

    @property
    def new_location(self) -> str:
        return self._game_location_chooser.get_path()

    def on_button_toggled(self, _button, action):
        self.action = action

    def on_response(self, _widget, response):
        if response == Gtk.ResponseType.CANCEL:
            self.action = None
        super().on_response(_widget, response)
