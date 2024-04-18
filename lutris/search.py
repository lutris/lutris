import copy
from typing import Any, Callable, Dict, List, Optional, Set

from lutris.database import games
from lutris.database.categories import (
    get_game_ids_for_categories,
    get_uncategorized_game_ids,
    normalized_category_names,
)
from lutris.runners.runner import Runner
from lutris.util.strings import parse_playtime, strip_accents
from lutris.util.tokenization import (
    TokenReader,
    clean_token,
    tokenize_search,
)

ISOLATED_TOKENS = set([":", "-", "(", ")", "<", ">", ">=", "<="])
ITEM_STOP_TOKENS = (ISOLATED_TOKENS | set(["OR", "AND"])) - set(["("])

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
        return not self.text

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
                tokens = TokenReader(list(raw_tokens))
                self.predicate = self._parse_or(tokens) or TRUE_PREDICATE
            else:
                self.predicate = TRUE_PREDICATE
        return self.predicate

    def _parse_or(self, tokens: TokenReader) -> Optional[SearchPredicate]:
        parts = self._parse_chain("OR", self._parse_items, tokens)
        return or_predicates(parts)

    def _parse_chain(self, conjunction: str, next_parser: Callable, tokens: TokenReader) -> List[SearchPredicate]:
        parsed = next_parser(tokens)
        parts = []
        if parsed:
            parts.append(parsed)

            while tokens.consume(conjunction):  # case-sensitive!
                more = next_parser(tokens)
                if not more:
                    break

                parts.append(more)
        return parts

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

        text_token = tokens.get_cleaned_token_sequence(stop_tokens=ITEM_STOP_TOKENS)
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


class GameSearch(BaseSearch):
    tags = set(["installed", "hidden", "favorite", "categorized", "category", "runner", "platform", "playtime"])

    def __init__(self, text: str, service) -> None:
        self.service = service
        super().__init__(text)

    def get_candidate_text(self, candidate: Any) -> str:
        return candidate["name"]

    def get_part_predicate(self, name: str, tokens: TokenReader) -> Callable:
        if name == "category":
            category = tokens.get_cleaned_token() or ""
            return self.get_category_predicate(category)

        if name == "runner":
            runner_name = tokens.get_cleaned_token() or ""
            return self.get_runner_predicate(runner_name)

        if name == "platform":
            platform = tokens.get_cleaned_token() or ""
            return self.get_platform_predicate(platform)

        if name == "playtime":
            return self.get_playtime_predicate(tokens)

        # All flags handle the 'maybe' option the same way, so we'll
        # group them at the end.
        flag = read_flag_token(tokens)

        if flag is None:
            # None represents 'maybe' which performs no test, but overrides
            # the tests performed outside the search. Useful for 'hidden' and
            # 'installed' components
            return lambda *args: True

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
        def match_greater_playtime(db_game):
            game_playtime = db_game.get("playtime")
            return game_playtime and game_playtime > playtime

        def match_lesser_playtime(db_game):
            game_playtime = db_game.get("playtime")
            return game_playtime and game_playtime < playtime

        def match_playtime(db_game):
            game_playtime = db_game.get("playtime")
            return game_playtime and game_playtime == playtime

        operator = tokens.peek_token()
        if operator == ">":
            matcher = match_greater_playtime
            tokens.get_token()
        elif operator == ">":
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

        # We'll hope none of our tags are ever part of a legit playtime
        playtime_text = tokens.get_cleaned_token_sequence(stop_tokens=ITEM_STOP_TOKENS | self.tags)
        if not playtime_text:
            raise InvalidSearchTermError("A blank is not a valid playtime.")

        try:
            playtime = parse_playtime(playtime_text)
        except ValueError as ex:
            raise InvalidSearchTermError(f"'{playtime_text}' is not a valid playtime.") from ex

        return matcher

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
        names = normalized_category_names(category)
        category_game_ids = set(get_game_ids_for_categories(names))

        def match_categorized(db_game):
            game_id = db_game["id"]
            game_in_category = game_id in category_game_ids
            return game_in_category == in_category

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
    tags = set(["installed"])

    def get_candidate_text(self, candidate: Any) -> str:
        return f"{candidate.name}\n{candidate.description}"

    def get_part_predicate(self, name: str, tokens: TokenReader) -> Callable:
        if name == "installed":
            flag = read_flag_token(tokens)

            if flag is None:
                return lambda *args: True

            return self.get_installed_predicate(flag)

        return super().get_part_predicate(name, tokens)

    def get_installed_predicate(self, installed: bool) -> Callable:
        def match_installed(runner: Runner):
            is_installed = runner.is_installed()
            return installed == is_installed

        return match_installed
