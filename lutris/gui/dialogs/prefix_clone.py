"""Progress dialog shown while cloning a Wine prefix into a new profile directory."""

import os
import shutil
import threading
from gettext import gettext as _
from typing import Optional

from gi.repository import GLib, Gtk, Pango  # type: ignore

from lutris.gui.dialogs import ModalDialog
from lutris.util.log import logger


class PrefixCloneDialog(ModalDialog):
    """Modal dialog that copies a Wine prefix tree with a real file-by-file progress bar.

    Usage::

        dialog = PrefixCloneDialog(source, dest, game_name="My Game", parent=window)
        success = dialog.run_clone()
    """

    def __init__(
        self,
        source: str,
        dest: str,
        game_name: str = "",
        parent: Optional[Gtk.Window] = None,
    ) -> None:
        super().__init__(title=_("Setting up Wine prefix"), parent=parent, border_width=16)  # type: ignore[arg-type]
        self.set_size_request(440, -1)
        self.set_resizable(False)

        self._source = source
        self._dest = dest

        content = self.get_content_area()
        content.set_spacing(10)

        if game_name:
            title_label = Gtk.Label(
                label=_("Preparing Wine prefix for <b>%s</b>…") % GLib.markup_escape_text(game_name),
                use_markup=True,
                xalign=0,
                visible=True,
                wrap=True,
            )
            content.add(title_label)

        self._progress_bar = Gtk.ProgressBar(
            visible=True,
            show_text=True,
            text="0%",
        )
        content.add(self._progress_bar)

        self._status_label = Gtk.Label(
            label="",
            xalign=0,
            visible=True,
            ellipsize=Pango.EllipsizeMode.MIDDLE,
        )
        content.add(self._status_label)

        self.show_all()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_clone(self) -> bool:
        """Start the clone in a background thread and run the dialog modal loop.

        Returns True if the clone completed successfully, False on error.
        The dialog destroys itself after returning.
        """
        thread = threading.Thread(target=self._do_clone, daemon=True)
        thread.start()
        result = self.run()
        return result == Gtk.ResponseType.OK

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _do_clone(self) -> None:
        """Background thread: count files, copy them, update progress via idle callbacks."""
        try:
            total = sum(len(files) for _, _, files in os.walk(self._source))
            done = 0

            def copy_fn(src: str, dst: str) -> None:
                nonlocal done
                shutil.copy2(src, dst)
                done += 1
                fraction = done / total if total else 1.0
                GLib.idle_add(self._update_progress, fraction, os.path.basename(src))

            shutil.copytree(self._source, self._dest, symlinks=True, copy_function=copy_fn)
        except Exception as ex:
            logger.exception("Wine prefix clone failed: %s", ex)
            GLib.idle_add(self.response, Gtk.ResponseType.CANCEL)
            return

        GLib.idle_add(self.response, Gtk.ResponseType.OK)

    def _update_progress(self, fraction: float, filename: str) -> None:
        self._progress_bar.set_fraction(fraction)
        self._progress_bar.set_text("%.0f%%" % (fraction * 100))
        self._status_label.set_text(filename)
