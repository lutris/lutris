from gettext import gettext as _

from gi.repository import GObject, Gtk

from lutris.exceptions import InvalidGameMoveError
from lutris.game import GAME_UPDATED
from lutris.gui.dialogs import ModelessDialog, WarningDialog, display_error
from lutris.util.jobs import AsyncCall, schedule_repeating_at_idle


class MoveDialog(ModelessDialog):
    __gsignals__ = {
        "game-moved": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, game, destination: str, parent: Gtk.Window = None) -> None:
        super().__init__(parent=parent, border_width=24)

        self.game = game
        self.destination = destination
        self.new_directory = None

        self.set_size_request(320, 60)
        self.set_decorated(False)
        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 12)
        label = Gtk.Label(_("Moving %s to %s..." % (game, destination)))
        vbox.add(label)
        self.progress = Gtk.ProgressBar(visible=True)
        self.progress.set_pulse_step(0.1)
        vbox.add(self.progress)
        self.get_content_area().add(vbox)
        self.progress_source_task = schedule_repeating_at_idle(self.show_progress, interval_seconds=0.125)
        self.connect("destroy", self.on_destroy)
        self.show_all()

    def on_destroy(self, _dialog):
        self.progress_source_task.unschedule()

    def move(self):
        AsyncCall(self._move_game, self._move_game_cb)

    def show_progress(self) -> bool:
        self.progress.pulse()
        return True

    def _move_game(self):
        # not safe fire a signal from a thread- it will surely hit GTK and may crash
        self.new_directory = self.game.move(self.destination, no_signal=True)

    def _move_game_cb(self, _result, error):
        if error and isinstance(error, InvalidGameMoveError):
            secondary = _(
                "Do you want to change the game location anyway? No files can be moved, "
                "and the game configuration may need to be adjusted."
            )
            dlg = WarningDialog(message_markup=error, secondary=secondary, parent=self)
            if dlg.result == Gtk.ResponseType.OK:
                self.new_directory = self.game.set_location(self.destination)
                self.on_game_moved(None, None)
            else:
                self.destroy()
            return

        self.on_game_moved(_result, error)

    def on_game_moved(self, _result, error):
        if error:
            display_error(error, parent=self)
        GAME_UPDATED.fire(self.game)  # because we could not fire this on the thread
        self.emit("game-moved")
        self.destroy()
