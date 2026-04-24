"""Gtk.Image subclass that picks a stock icon from a list of candidates."""

from collections.abc import Iterable

from gi.repository import Gtk

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
        icon_size: Gtk.IconSize = Gtk.IconSize.MENU,
    ) -> None:
        super().__init__()
        self.candidate_names = list(candidate_names)
        self.fallback_name = fallback_name
        self.icon_size = icon_size
        self._theme_changed_handler_id = 0
        self._reload_icon()
        self.connect("realize", self._on_realize)
        self.connect("unrealize", self._on_unrealize)

    def _reload_icon(self) -> None:
        icon_name = pick_stock_icon(self.candidate_names, fallback_name=self.fallback_name)
        self.set_from_icon_name(icon_name, self.icon_size)
        # The chosen icon may only be available at the wrong size; pin our
        # preferred pixel size so adjacent widgets line up.
        found, _width, height = Gtk.IconSize.lookup(self.icon_size)
        if found:
            self.set_pixel_size(height)

    def _on_realize(self, _widget: Gtk.Widget) -> None:
        theme = Gtk.IconTheme.get_default()
        self._theme_changed_handler_id = theme.connect("changed", self._on_theme_changed)

    def _on_unrealize(self, _widget: Gtk.Widget) -> None:
        if self._theme_changed_handler_id:
            Gtk.IconTheme.get_default().disconnect(self._theme_changed_handler_id)
            self._theme_changed_handler_id = 0

    def _on_theme_changed(self, _theme: Gtk.IconTheme) -> None:
        self._reload_icon()
