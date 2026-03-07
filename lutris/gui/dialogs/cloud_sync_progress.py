"""Cloud sync progress dialog for GOG cloud save integration.

Shows a non-intrusive progress dialog while cloud saves are being
synchronized before game launch or after game exit, keeping the GTK
main loop responsive so the window manager does not flag Lutris as
"not responding".
"""

from gettext import gettext as _
from typing import TYPE_CHECKING, Callable, List, Optional

from gi.repository import GLib, Gtk

from lutris.gui.dialogs import ModelessDialog
from lutris.services.gog_cloud import SyncResult
from lutris.util.jobs import AsyncCall, IdleTask, schedule_repeating_at_idle
from lutris.util.log import logger

if TYPE_CHECKING:
    from lutris.game import Game


class CloudSyncProgressDialog(ModelessDialog):
    """Modal-style progress dialog shown during GOG cloud save sync.

    The dialog displays a pulsing progress bar and status label while
    the actual sync work runs on a background thread.  This keeps the
    GTK main loop alive so the desktop environment will not report the
    application as unresponsive.

    Usage::

        dialog = CloudSyncProgressDialog(
            game=game,
            sync_func=sync_before_launch,
            direction="pre-launch",
            parent=parent_window,
        )
        dialog.run_sync()
        # dialog auto-destroys when done; results in dialog.results
    """

    def __init__(
        self,
        game: "Game",
        sync_func: Callable[["Game"], List[SyncResult]],
        direction: str = "pre-launch",
        parent: Optional[Gtk.Widget] = None,
    ) -> None:
        title = _("Syncing Cloud Saves…") if direction == "pre-launch" else _("Uploading Cloud Saves…")
        super().__init__(title=title, parent=parent, border_width=18)  # type: ignore[arg-type]

        self.game = game
        self._sync_func = sync_func
        self._direction = direction
        self.results: List[SyncResult] = []
        self._cancelled = False
        self._pulse_task: Optional[IdleTask] = None

        self.set_size_request(400, -1)
        self.set_resizable(False)
        self.set_deletable(False)

        content = self.get_content_area()

        # Status label
        self._status_label = Gtk.Label(visible=True)
        if direction == "pre-launch":
            self._status_label.set_markup(
                _("Downloading cloud saves for <b>%s</b>…") % GLib.markup_escape_text(game.name)
            )
        else:
            self._status_label.set_markup(
                _("Uploading saves for <b>%s</b> to cloud…") % GLib.markup_escape_text(game.name)
            )
        self._status_label.set_line_wrap(True)
        content.pack_start(self._status_label, False, False, 6)

        # Progress bar (pulsing - we don't know exact progress)
        self._progress_bar = Gtk.ProgressBar(visible=True)
        self._progress_bar.set_pulse_step(0.15)
        content.pack_start(self._progress_bar, False, False, 6)

        # Detail label (shows file counts once finished)
        self._detail_label = Gtk.Label(visible=True)
        self._detail_label.set_text(_("Please wait…"))
        self._detail_label.set_xalign(0.0)
        content.pack_start(self._detail_label, False, False, 2)

        # Skip button - lets the user skip sync and launch immediately
        self._skip_button = self.add_button(_("Skip Sync"), Gtk.ResponseType.CANCEL)
        self._skip_button.set_tooltip_text(_("Skip cloud sync and launch the game immediately"))

        self.connect("response", self._on_response)
        self.connect("destroy", self._on_destroy)
        self.show_all()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_sync(self) -> None:
        """Start the sync operation on a background thread."""
        self._pulse_task = schedule_repeating_at_idle(self._pulse, interval_seconds=0.1)
        AsyncCall(self._do_sync, self._on_sync_done)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _pulse(self) -> bool:
        """Advance the progress bar pulse; returns True to keep repeating."""
        if self._cancelled:
            return False
        self._progress_bar.pulse()
        return True

    def _do_sync(self) -> List[SyncResult]:
        """Run on a background thread - performs the actual sync."""
        return self._sync_func(self.game)

    def _on_sync_done(self, results: Optional[List[SyncResult]], error: Optional[Exception]) -> None:
        """Callback invoked on the main thread when the sync finishes."""
        if self._cancelled:
            self.destroy()
            return

        if error:
            logger.warning("GOG cloud sync (%s) failed: %s", self._direction, error)
            self._status_label.set_markup(_("<b>Cloud sync failed</b>"))
            self._detail_label.set_text(str(error))
        else:
            self.results = results or []
            total_down = sum(len(r.downloaded) for r in self.results)
            total_up = sum(len(r.uploaded) for r in self.results)
            if total_down or total_up:
                parts = []
                if total_down:
                    parts.append(_("%d file(s) downloaded") % total_down)
                if total_up:
                    parts.append(_("%d file(s) uploaded") % total_up)
                self._detail_label.set_text(", ".join(parts))
            else:
                self._detail_label.set_text(_("Saves are up to date."))

        # Auto-close after a brief moment so the user can see the result
        GLib.timeout_add(600, self._auto_close)

    def _auto_close(self) -> bool:
        """Destroy the dialog after sync completes."""
        self.destroy()
        return False  # do not repeat

    def _on_response(self, _dialog: Gtk.Dialog, response_id: int) -> None:
        """Handle user clicking *Skip Sync*."""
        if response_id == Gtk.ResponseType.CANCEL:
            logger.info("User skipped cloud sync (%s) for %s", self._direction, self.game.name)
            self._cancelled = True
            self._detail_label.set_text(_("Skipping…"))
            self._skip_button.set_sensitive(False)
            # The background thread may still be running; we just ignore
            # its result when it arrives.

    def _on_destroy(self, _dialog: Gtk.Widget) -> None:
        """Clean up the pulse timer."""
        if self._pulse_task is not None:
            self._pulse_task.unschedule()
            self._pulse_task = None
