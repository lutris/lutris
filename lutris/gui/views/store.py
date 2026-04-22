"""Store object for a list of games"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lutris.services.base import BaseService
    from lutris.services.service_media import ServiceMedia

from gi.repository import Gio, GObject

from lutris.database.games import get_all_installed_game_for_service
from lutris.gui.views.game_item import GameItem
from lutris.gui.views.store_item import StoreItem


class GameStore(GObject.Object):
    def __init__(self, service: "BaseService | None", service_media: "ServiceMedia") -> None:
        super().__init__()
        self.service = service
        self.service_media = service_media

        self.list_store = Gio.ListStore.new(GameItem)
        self._items_by_id: dict[str, GameItem] = {}

    def remove_game(self, game_id) -> None:
        """Remove a game from the view."""
        item = self._items_by_id.pop(str(game_id), None)
        if item is None:
            return
        found, position = self.list_store.find(item)
        if found:
            self.list_store.remove(position)

    def update(self, db_game: dict) -> set[str] | None:
        """Update game information.
        Return the set of GameItem property names that changed, or an empty set
        if no change was made, or None if the game could not be found.
        """
        store_item = StoreItem(db_game, self.service, self.service_media)
        item = self._items_by_id.get(store_item.id)
        if item is None and "service_id" in db_game:
            item = self._items_by_id.get(db_game["service_id"])
        if item is None:
            return None

        old_id = item.id
        changed = item.update_from_store_item(store_item)
        new_id = item.id
        if old_id != new_id:
            self._items_by_id.pop(old_id, None)
            self._items_by_id[new_id] = item
        return changed

    def add_game(self, db_game) -> None:
        """Add a game to the store"""
        store_item = StoreItem(db_game, self.service, self.service_media)
        self.add_item(store_item)

    def add_item(self, store_item: StoreItem) -> None:
        game_item = GameItem.from_store_item(store_item)
        self.list_store.append(game_item)
        self._items_by_id[store_item.id] = game_item

    def add_preloaded_games(self, db_games, service_id) -> None:
        """Add games to the store, but preload their installed-game data
        all at once, for faster database access. This should be used if all or almost all
        games are being loaded."""

        installed_db_games = {}
        if service_id and db_games:
            installed_db_games = get_all_installed_game_for_service(service_id)

        for db_game in db_games:
            if installed_db_games is not None and "appid" in db_game:
                appid = db_game["appid"]
                store_item = StoreItem(db_game, self.service, self.service_media)
                store_item.apply_installed_game_data(installed_db_games.get(appid))
                self.add_item(store_item)
            else:
                self.add_game(db_game)
