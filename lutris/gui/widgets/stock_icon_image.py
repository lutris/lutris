"""Gtk.Image subclass that picks a stock icon from a list of candidates."""

from collections.abc import Iterable

from gi.repository import Gdk, Gtk

from lutris.gui.widgets.utils import pick_stock_icon


class StockIconImage(Gtk.Image):
    """A Gtk.Image that shows the first available stock icon from a list of candidates.

    Re-evaluates the selection when the icon theme changes, so an icon that only
    becomes available (or unavailable) after a theme switch is picked up."""

    __gtype_name__ = "StockIconImage"

    def __init__(
        self,
        candidate_names: Iterable[str],
        fallback_name: str = "package-x-generic-symbolic",
        pixel_size: int = 16,
    ) -> None:
        super().__init__()
        self.candidate_names = list(candidate_names)
        self.fallback_name = fallback_name
        self.pixel_size = pixel_size
        self.set_pixel_size(pixel_size)
        self._theme_changed_handler_id = 0
        self._reload_icon()
        self.connect("realize", self._on_realize)
        self.connect("unrealize", self._on_unrealize)

    def _reload_icon(self) -> None:
        icon_name = pick_stock_icon(self.candidate_names, fallback_name=self.fallback_name)
        self.set_from_icon_name(icon_name)

    def _get_theme(self) -> Gtk.IconTheme | None:
        display = self.get_display() or Gdk.Display.get_default()
        if display is None:
            return None
        return Gtk.IconTheme.get_for_display(display)

    def _on_realize(self, _widget: Gtk.Widget) -> None:
        theme = self._get_theme()
        if theme is not None:
            self._theme_changed_handler_id = theme.connect("changed", self._on_theme_changed)

    def _on_unrealize(self, _widget: Gtk.Widget) -> None:
        if self._theme_changed_handler_id:
            theme = self._get_theme()
            if theme is not None:
                theme.disconnect(self._theme_changed_handler_id)
            self._theme_changed_handler_id = 0

    def _on_theme_changed(self, _theme: Gtk.IconTheme) -> None:
        self._reload_icon()
