from typing import Any, Callable, Dict, List, Optional

from lutris.database import games
from lutris.util.strings import strip_accents


class BaseSearch:
    flag_texts = {"true": True, "yes": True, "false": False, "no": False}

    def __init__(self, text: str) -> None:
        self.text = text
        self.predicates: List[Callable] = []

        if text:
            for part in text.split():
                if ":" in part:
                    pos = part.index(":", 1)
                    name = part[:pos]
                    value = part[(pos + 1) :]
                    predicate = self.get_part_predicate(name, value)
                    if predicate:
                        self.add_predicate(predicate)
                        continue

                self.add_predicate(GameSearch.get_text_predicate(part))

    def __str__(self) -> str:
        return self.text

    def add_predicate(self, predicate: Callable) -> None:
        self.predicates.append(predicate)

    def get_part_predicate(self, name: str, value: str) -> Optional[Callable]:
        return None

    @property
    def is_empty(self) -> bool:
        return not self.predicates

    def matches(self, db_game: Dict[str, Any], service) -> bool:
        for predicate in self.predicates:
            if not predicate(db_game, service):
                return False

        return True

    @staticmethod
    def get_text_predicate(text: str) -> Callable:
        stripped = strip_accents(text).casefold()

        def match_text(db_game, service):
            name = strip_accents(db_game["name"]).casefold()
            return stripped in name

        return match_text


class GameSearch(BaseSearch):
    def get_part_predicate(self, name: str, value: str) -> Optional[Callable]:
        if name.casefold() == "installed":
            if value in GameSearch.flag_texts:
                installed = GameSearch.flag_texts[value]
                return self.get_installed_predicate(installed)

        return super().get_part_predicate(name, value)

    @classmethod
    def get_installed_predicate(cls, installed: bool) -> Callable:
        def match_installed(db_game, service):
            is_installed = GameSearch._is_installed(db_game, service)
            return installed == is_installed

        return match_installed

    @classmethod
    def _is_installed(cls, db_game: Dict[str, Any], service) -> bool:
        if service:
            appid = db_game.get("appid")
            return bool(appid and appid in games.get_service_games(service.id))

        return bool(db_game["installed"])
