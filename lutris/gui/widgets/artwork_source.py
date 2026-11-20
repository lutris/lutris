"""Native linked buttons for artwork source selection."""

from gi.repository import Gtk


class ArtworkSourceButtons(Gtk.Box):
    def __init__(self, choices, value, on_changed):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.get_style_context().add_class("linked")
        self.buttons = {}
        self._initializing = True
        group = None
        for label, choice in choices:
            button = Gtk.RadioButton.new_with_label_from_widget(group, label)
            button.set_mode(False)
            group = button
            self.pack_start(button, False, False, 0)
            self.buttons[choice] = button
            button.connect("toggled", self._on_toggled, choice, on_changed)
        self.buttons[value].set_active(True)
        self._initializing = False

    def _on_toggled(self, button, choice, callback):
        if not self._initializing and button.get_active():
            callback(choice)

    def get_value(self):
        return next(value for value, button in self.buttons.items() if button.get_active())
