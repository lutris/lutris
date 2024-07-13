import copy
import time
from typing import Any, Callable, Dict, List, Optional, Set

from lutris.database import games
from lutris.database.categories import (
    get_game_ids_for_categories,
    get_uncategorized_game_ids,
    normalized_category_names,
)
from lutris.runners import get_runner_human_name
from lutris.runners.runner import Runner
from lutris.services import SERVICES
from lutris.util.strings import parse_playtime_parts, strip_accents
from lutris.util.tokenization import (
    TokenReader,
    clean_token,
    tokenize_search,
)

ISOLATED_TOKENS = set([":", "-", "(", ")", "<", ">", ">=", "<="])
ITEM_STOP_TOKENS = (ISOLATED_TOKENS | set(["OR", "AND"])) - set(["(", "-"])

SearchPredicate = Callable[[Any], bool]

TRUE_PREDICATE: SearchPredicate = lambda *a: True  # noqa: E731
FLAG_TEXTS: Dict[str, Optional[bool]] = {"true": True, "yes": True, "false": False, "no": False, "maybe": None}


class InvalidSearchTermError(ValueError):
    def __init__(self, message: str, *args, **kwargs) -> None:
        super().__init__(message, *args, **kwargs)
        self.message = message


def read_flag_token(tokens: TokenReader) -> Optional[bool]:
    token = tokens.get_cleaned_token() or ""
    folded = token.casefold()
    if folded in FLAG_TEXTS:
        return FLAG_TEXTS[folded]
    raise InvalidSearchTermError(f"'{token}' was found where a flag was expected.")


def and_predicates(predicates: List[SearchPredicate]) -> Optional[SearchPredicate]:
    if not predicates:
        return None
    if len(predicates) == 1:
        return predicates[0]

    return lambda *a: all(p(*a) for p in predicates)


def or_predicates(predicates: List[SearchPredicate]) -> Optional[SearchPredicate]:
    if not predicates:
        return None
    if len(predicates) == 1:
        return predicates[0]

    return lambda *a: any(p(*a) for p in predicates)


class BaseSearch:
    tags: Set[str] = set()

    def __init__(self, text: str) -> None:
        self.text = text
        self.predicate: Optional[SearchPredicate] = None

    def __str__(self) -> str:
        return self.text

    @property
    def is_empty(self) -> bool:
        return not self.text and not self.predicate

    def matches(self, candidate: Any) -> bool:
        return self.get_predicate()(candidate)

    def get_candidate_text(self, candidate: Any) -> str:
        return str(candidate)

    def has_component(self, component_name: str) -> bool:
        if component_name in self.tags:
            prev_token = None
            for token in tokenize_search(self.text, ISOLATED_TOKENS):
                if not token.isspace():
                    if token == ":" and prev_token and prev_token.casefold() == component_name:
                        return True
                    prev_token = token
        return False

    def get_predicate(self) -> SearchPredicate:
        if self.predicate is None:
            if self.text:
                raw_tokens = tokenize_search(self.text, ISOLATED_TOKENS)
                tokens = TokenReader(raw_tokens)
                self.predicate = self._parse_or(tokens) or TRUE_PREDICATE
            else:
                self.predicate = TRUE_PREDICATE
        return self.predicate

    def _parse_or(self, tokens: TokenReader) -> Optional[SearchPredicate]:
        parsed = self._parse_items(tokens)
        parts = []
        if parsed:
            parts.append(parsed)

            while tokens.consume("OR"):  # case-sensitive!
                more = self._parse_items(tokens)
                if not more:
                    break

                parts.append(more)
        return or_predicates(parts)

    def _parse_items(self, tokens: TokenReader) -> Optional[SearchPredicate]:
        buffer = []
        while True:
            parsed = self._parse_item(tokens)
            if parsed:
                buffer.append(parsed)
            else:
                break

        return and_predicates(buffer)

    def _parse_item(self, tokens: TokenReader) -> Optional[SearchPredicate]:
        # AND is kinda fake - we and together items by default anyway,
        # so we'll just ignore this conjunction.
        while tokens.consume("AND"):
            pass

        token = tokens.peek_token()

        if not token or token in ITEM_STOP_TOKENS:
            return None

        if token.startswith('"'):
            tokens.get_token()  # consume token
            return self.get_text_predicate(clean_token(token))

        if tokens.consume("("):
            predicate = self._parse_or(tokens) or TRUE_PREDICATE
            tokens.consume(")")
            return predicate

        if tokens.consume("-"):
            inner = self._parse_items(tokens)
            if inner:
                return lambda *a: not inner(*a)

        saved_index = tokens.index

        tokens.get_token()  # consume tag name
        if tokens.consume(":"):
            name = token.casefold()
            if name in self.tags:
                try:
                    return self.get_part_predicate(name, tokens)
                except InvalidSearchTermError:
                    pass

        # If the tag is no good, we'll rewind and fall back on a
        # literal text predicate for the whole thing
        tokens.index = saved_index

        text_token = tokens.get_cleaned_token_sequence(stop_function=self.is_stop_token)
        if text_token:
            return self.get_text_predicate(text_token)

        return None

    def with_predicate(self, predicate: Callable):
        old_predicate = self.get_predicate()  # force generation of predicate
        new_search = copy.copy(self)
        new_search.predicate = lambda *a: old_predicate(*a) and predicate(*a)
        return new_search

    def get_part_predicate(self, name: str, tokens: TokenReader) -> Callable:
        raise InvalidSearchTermError(f"'{name}' is not a valid search tag.")

    def get_text_predicate(self, text: str) -> Callable:
        stripped = strip_accents(text).casefold()

        def match_text(candidate):
            name = strip_accents(self.get_candidate_text(candidate)).casefold()
            return stripped in name

        return match_text

    def is_stop_token(self, tokens: TokenReader) -> bool:
        """This function decides when to stop when reading an item;
        pass this to tokens.get_cleaned_token_sequence().

        It will stop at the end of tokens, any of our stop tokens
        like AND, or at any tag, which must be a known tag followed by
        a colon."""
        peeked = tokens.peek_tokens(2)
        if not peeked:
            return True
        if peeked[0] in ITEM_STOP_TOKENS:
            return True
        if len(peeked) > 1 and peeked[1] == ":" and peeked[0].casefold() in self.tags:
            return True
        return False


class GameSearch(BaseSearch):
    """A search for games, which applies to the games database dictionaries, not the Game objects."""

    tags = set(
        [
            "installed",
            "hidden",
            "favorite",
            "categorized",
            "category",
            "source",
            "service",  # an alias for source
            "runner",
            "platform",
            "playtime",
            "lastplayed",
            "directory",
        ]
    )

    def __init__(self, text: str, service) -> None:
        self.service = service
        super().__init__(text)

    def get_candidate_text(self, candidate: Any) -> str:
        return candidate["name"]

    def get_part_predicate(self, name: str, tokens: TokenReader) -> Callable:
        if name == "category":
            category = tokens.get_cleaned_token() or ""
            return self.get_category_predicate(category)

        if name in ("source", "service"):
            service_name = tokens.get_cleaned_token() or ""
            return self.get_service_predicate(service_name)

        if name == "runner":
            runner_name = tokens.get_cleaned_token() or ""
            return self.get_runner_predicate(runner_name)

        if name == "platform":
            platform = tokens.get_cleaned_token() or ""
            return self.get_platform_predicate(platform)

        if name == "playtime":
            return self.get_playtime_predicate(tokens)

        if name == "lastplayed":
            return self.get_lastplayed_predicate(tokens)

        if name == "directory":
            directory = tokens.get_cleaned_token_sequence(stop_function=self.is_stop_token) or ""
            return self.get_directory_predicate(directory)

        # All flags handle the 'maybe' option the same way, so we'll
        # group them at the end.
        flag = read_flag_token(tokens)

        if flag is None:
            # None represents 'maybe' which performs no test, but overrides
            # the tests performed outside the search. Useful for 'hidden' and
            # 'installed' components
            return TRUE_PREDICATE

        if name == "installed":
            return self.get_installed_predicate(flag)

        if name == "hidden":
            return self.get_category_predicate(".hidden", in_category=flag)

        if name == "favorite":
            return self.get_category_predicate("favorite", in_category=flag)

        if name == "categorized":
            return self.get_categorized_predicate(flag)

        return super().get_part_predicate(name, tokens)

    def get_playtime_predicate(self, tokens: TokenReader) -> Callable:
        def get_game_playtime(db_game):
            return db_game.get("playtime")

        return self.get_duration_predicate(get_game_playtime, tokens)

    def get_lastplayed_predicate(self, tokens: TokenReader) -> Callable:
        now = time.time()

        def get_game_lastplayed_duration_ago(db_game):
            lastplayed = db_game.get("lastplayed")
            if lastplayed:
                return (now - lastplayed) / (60 * 60)
            return None

        return self.get_duration_predicate(get_game_lastplayed_duration_ago, tokens)

    def get_duration_predicate(self, value_function: Callable, tokens: TokenReader) -> Callable:
        def match_greater_playtime(db_game):
            game_playtime = value_function(db_game)
            return game_playtime and game_playtime > duration

        def match_lesser_playtime(db_game):
            game_playtime = value_function(db_game)
            return game_playtime and game_playtime < duration

        def match_playtime(db_game):
            game_playtime = value_function(db_game)
            return game_playtime and duration_parts.matches(game_playtime)

        operator = tokens.peek_token()
        if operator == ">":
            matcher = match_greater_playtime
            tokens.get_token()
        elif operator == "<":
            matcher = match_lesser_playtime
            tokens.get_token()
        elif operator == ">=":
            matcher = or_predicates([match_greater_playtime, match_playtime])
            tokens.get_token()
        elif operator == "<=":
            matcher = or_predicates([match_lesser_playtime, match_playtime])
            tokens.get_token()
        else:
            matcher = match_playtime

        # We'll hope none of our tags are ever part of a legit duration
        duration_text = tokens.get_cleaned_token_sequence(stop_function=self.is_stop_token)
        if not duration_text:
            raise InvalidSearchTermError("A blank is not a valid duration.")

        try:
            duration_parts = parse_playtime_parts(duration_text)
            duration = duration_parts.get_total_hours()
        except ValueError as ex:
            raise InvalidSearchTermError(f"'{duration_text}' is not a valid playtime.") from ex

        return matcher

    def get_directory_predicate(self, directory: str) -> Callable:
        def match_directory(db_game):
            game_dir = db_game.get("directory")
            return game_dir and directory in game_dir

        return match_directory

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

    def get_category_predicate(self, category: str, in_category: bool = True) -> Callable:
        names = normalized_category_names(category, subname_allowed=True)
        category_game_ids = set(get_game_ids_for_categories(names))

        def match_categorized(db_game):
            game_id = db_game["id"]
            game_in_category = game_id in category_game_ids
            return game_in_category == in_category

        return match_categorized

    def get_service_predicate(self, service_name: str) -> Callable:
        service_name = service_name.casefold()

        def match_service(db_game):
            game_service = db_game.get("service")
            if not game_service:
                return False

            if game_service.casefold() == service_name:
                return True

            service = SERVICES.get(game_service)
            return service and service_name in service.name.casefold()

        return match_service

    def get_runner_predicate(self, runner_name: str) -> Callable:
        runner_name = runner_name.casefold()

        def match_runner(db_game):
            game_runner = db_game.get("runner")

            if not game_runner:
                return False

            if game_runner.casefold() == runner_name:
                return True

            runner_human_name = get_runner_human_name(game_runner)
            return runner_name in runner_human_name.casefold()

        return match_runner

    def get_platform_predicate(self, platform: str) -> Callable:
        platform = platform.casefold()

        def match_platform(db_game):
            game_platform = db_game.get("platform")
            if game_platform:
                return platform in game_platform.casefold()
            if self.service:
                platforms = [p.casefold() for p in self.service.get_game_platforms(db_game)]
                matches = [p for p in platforms if platform in p]
                return any(matches)
            return False

        return match_platform


class RunnerSearch(BaseSearch):
    """A search for runners, which applies to the runner objects."""

    tags = set(["installed"])

    def get_candidate_text(self, candidate: Any) -> str:
        return f"{candidate.name}\n{candidate.description}"

    def get_part_predicate(self, name: str, tokens: TokenReader) -> Callable:
        if name == "installed":
            flag = read_flag_token(tokens)

            if flag is None:
                return TRUE_PREDICATE

            return self.get_installed_predicate(flag)

        return super().get_part_predicate(name, tokens)

    def get_installed_predicate(self, installed: bool) -> Callable:
        def match_installed(runner: Runner):
            is_installed = runner.is_installed()
            return installed == is_installed

        return match_installed
