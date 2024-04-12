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

                self.add_predicate(self.get_text_predicate(part))

    def __str__(self) -> str:
        return self.text

    def add_predicate(self, predicate: Callable) -> None:
        self.predicates.append(predicate)

    def get_part_predicate(self, name: str, value: str) -> Optional[Callable]:
        return None

    @property
    def is_empty(self) -> bool:
        return not self.predicates

    def matches(self, candidate: Any) -> bool:
        for predicate in self.predicates:
            if not predicate(candidate):
                return False

        return True

    def get_text_predicate(self, text: str) -> Callable:
        stripped = strip_accents(text).casefold()

        def match_text(candidate):
            name = strip_accents(self.get_candidate_text(candidate)).casefold()
            return stripped in name

        return match_text

    def get_candidate_text(self, candidate: Any) -> str:
        return str(candidate)


class GameSearch(BaseSearch):
    def __init__(self, text: str, service) -> None:
        self.service = service
        super().__init__(text)

    def get_candidate_text(self, candidate: Any) -> str:
        return candidate["name"]

    def get_part_predicate(self, name: str, value: str) -> Optional[Callable]:
        if name.casefold() == "installed":
            if value in GameSearch.flag_texts:
                installed = GameSearch.flag_texts[value]
                return self.get_installed_predicate(installed)

        return super().get_part_predicate(name, value)

    def get_installed_predicate(self, installed: bool) -> Callable:
        def match_installed(db_game):
            is_installed = self._is_installed(db_game)
            return installed == is_installed

        return match_installed

    def _is_installed(self, db_game: Dict[str, Any]) -> bool:
        if self.service:
            appid = db_game.get("appid")
            return bool(appid and appid in games.get_service_games(self.service.id))

        return bool(db_game["installed"])
