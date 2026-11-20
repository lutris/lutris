"""Text a running command writes, kept where any frontend can show it."""

from lutris.util.notifications import NotificationSource


class LogBuffer:
    """The output of a game or installer command.

    Frontends display it and follow `changed`, which fires with `(text, replaced)`:
    `replaced` is False when `text` was appended to the end, and True when it
    replaced everything (so `("", True)` means the buffer was cleared). Appends and
    replacements go through the same notification so they're delivered in order.
    """

    def __init__(self, text: str = "") -> None:
        self._chunks: list[str] = [text] if text else []
        self.changed = NotificationSource()

    @property
    def text(self) -> str:
        """Everything written so far."""
        return "".join(self._chunks)

    def append(self, text: str) -> None:
        """Add text at the end."""
        if not text:
            return
        self._chunks.append(text)
        self.changed.fire(text, False)

    def set_text(self, text: str) -> None:
        """Replace the whole contents."""
        self._chunks = [text] if text else []
        self.changed.fire(text, True)

    def clear(self) -> None:
        """Empty the buffer."""
        self.set_text("")
