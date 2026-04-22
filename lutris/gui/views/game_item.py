"""GObject wrapper for a game, for use in Gio.ListStore."""

from gi.repository import GObject

from lutris import settings
from lutris.gui.views.store_item import StoreItem
from lutris.util.strings import gtk_safe


class GameItem(GObject.Object):
    """A game row exposed as a GObject so it can live in a Gio.ListStore.

    Properties mirror the columns that the list/grid views need.
    """

    id = GObject.Property(type=str, default="")
    slug = GObject.Property(type=str, default="")
    name = GObject.Property(type=str, default="")
    sortname = GObject.Property(type=str, default="")
    year = GObject.Property(type=str, default="")
    runner = GObject.Property(type=str, default="")
    runner_human_name = GObject.Property(type=str, default="")
    platform = GObject.Property(type=str, default="")
    lastplayed = GObject.Property(type=float, default=0.0)
    lastplayed_text = GObject.Property(type=str, default="")
    installed = GObject.Property(type=bool, default=False)
    installed_at = GObject.Property(type=float, default=0.0)
    installed_at_text = GObject.Property(type=str, default="")
    playtime = GObject.Property(type=float, default=0.0)
    playtime_text = GObject.Property(type=str, default="")
    media_paths = GObject.Property(type=object)

    @classmethod
    def from_store_item(cls, store_item: StoreItem) -> "GameItem":
        item = cls()
        item.update_from_store_item(store_item)
        return item

    def update_from_store_item(self, store_item: StoreItem) -> set[str]:
        """Apply the StoreItem's fields to this GameItem. Returns the set of
        property names that changed — callers use this to decide whether a
        view re-sort is needed."""
        new_values = {
            "id": store_item.id,
            "slug": store_item.slug,
            "name": store_item.name,
            "sortname": store_item.sortname if store_item.sortname else store_item.name,
            "media_paths": store_item.get_media_paths() if settings.SHOW_MEDIA else [],
            "year": store_item.year,
            "runner": store_item.runner,
            "runner_human_name": store_item.runner_text,
            # Labels in the list view use Pango markup, so escape ampersands
            # and angle brackets that may appear in platform strings.
            "platform": gtk_safe(store_item.platform),
            "lastplayed": float(store_item.lastplayed or 0),
            "lastplayed_text": store_item.lastplayed_text,
            "installed": store_item.installed,
            "installed_at": float(store_item.installed_at or 0),
            "installed_at_text": store_item.installed_at_text,
            "playtime": store_item.playtime,
            "playtime_text": store_item.playtime_text,
        }
        changed: set[str] = set()
        for name, value in new_values.items():
            if getattr(self, name) != value:
                setattr(self, name, value)
                changed.add(name)
        return changed
