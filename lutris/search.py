from typing import Any, Callable, Dict, List, Optional

from lutris.database import games
from lutris.database.categories import (
    get_game_ids_for_categories,
    get_uncategorized_game_ids,
    normalized_category_names,
)
from lutris.runners.runner import Runner
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
        if name.casefold() == "installed" and value in self.flag_texts:
            installed = self.flag_texts[value]
            return self.get_installed_predicate(installed)

        if name.casefold() == "categorized" and value in self.flag_texts:
            categorized = self.flag_texts[value]
            return self.get_categorized_predicate(categorized)

        if name.casefold() == "category":
            category = value.strip()
            return self.get_category_predicate(category)

        if name.casefold() == "runner":
            runner_name = value.strip()
            return self.get_runner_predicate(runner_name)

        if name.casefold() == "platform":
            platform = value.strip()
            return self.get_platform_predicate(platform)

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

    def get_categorized_predicate(self, categorized: bool) -> Callable:
        uncategorized_ids = set(get_uncategorized_game_ids())

        def match_categorized(db_game):
            game_id = db_game["id"]
            is_categorized = game_id not in uncategorized_ids
            return is_categorized == categorized

        return match_categorized

    def get_category_predicate(self, category: str) -> Callable:
        names = normalized_category_names(category)
        category_game_ids = set(get_game_ids_for_categories(names))

        def match_categorized(db_game):
            game_id = db_game["id"]
            return game_id in category_game_ids

        return match_categorized

    def get_runner_predicate(self, runner_name: str) -> Callable:
        runner_name = runner_name.casefold()

        def match_runner(db_game):
            game_runner = db_game.get("runner")
            return game_runner and game_runner.casefold() == runner_name

        return match_runner

    def get_platform_predicate(self, platform: str) -> Callable:
        platform = platform.casefold()

        def match_platform(db_game):
            game_platform = db_game.get("platform")
            if game_platform:
                return game_platform.casefold() == platform
            if self.service:
                platforms = [p.casefold() for p in self.service.get_game_platforms(db_game)]
                return platform in platforms
            return False

        return match_platform


class RunnerSearch(BaseSearch):
    def get_candidate_text(self, candidate: Any) -> str:
        return f"{candidate.name}\n{candidate.description}"

    def get_part_predicate(self, name: str, value: str) -> Optional[Callable]:
        if name.casefold() == "installed":
            if value in self.flag_texts:
                installed = self.flag_texts[value]
                return self.get_installed_predicate(installed)

        return super().get_part_predicate(name, value)

    def get_installed_predicate(self, installed: bool) -> Callable:
        def match_installed(runner: Runner):
            is_installed = runner.is_installed()
            return installed == is_installed

        return match_installed
