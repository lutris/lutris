import copy
from typing import Any, Callable, Dict, Iterator, List, Optional, Set

from lutris.database import games
from lutris.database.categories import (
    get_game_ids_for_categories,
    get_uncategorized_game_ids,
    normalized_category_names,
)
from lutris.runners.runner import Runner
from lutris.util.strings import strip_accents
from lutris.util.tokenization import (
    TokenReader,
    clean_token,
    implicitly_join_tokens,
    tokenize_search,
)

ITEM_STOP_TOKENS = set(["OR", "AND", ")"])
ISOLATED_TOKENS = ITEM_STOP_TOKENS | set(["-", "("])

SearchPredicate = Callable[[Any], bool]

TRUE_PREDICATE: SearchPredicate = lambda *a: True  # noqa: E731
FLAG_TEXTS: Dict[str, Optional[bool]] = {"true": True, "yes": True, "false": False, "no": False, "maybe": None}


class InvalidSearchTermError(ValueError):
    def __init__(self, message: str, *args, **kwargs) -> None:
        super().__init__(message, *args, **kwargs)
        self.message = message


def read_flag_token(reader: TokenReader) -> Optional[bool]:
    token = clean_token(reader.get_token())
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
            match_token = component_name + ":"
            for token in tokenize_search(self.text, ISOLATED_TOKENS, self.tags):
                if token.casefold() == match_token:
                    return True
        return False

    def get_predicate(self) -> SearchPredicate:
        if self.predicate is None:
            if self.text:
                raw_tokens = tokenize_search(self.text, ISOLATED_TOKENS, self.tags)
                joined_tokens = implicitly_join_tokens(raw_tokens, ISOLATED_TOKENS)
                tokens = TokenReader(list(joined_tokens))
                self.predicate = self._parse_or(tokens) or TRUE_PREDICATE
            else:
                self.predicate = TRUE_PREDICATE
        return self.predicate

    def _parse_or(self, tokens: TokenReader) -> Optional[SearchPredicate]:
        parts = list(self._parse_chain("OR", self._parse_and, tokens))
        return or_predicates(parts)

    def _parse_and(self, tokens: TokenReader) -> Optional[SearchPredicate]:
        parts = list(self._parse_chain("AND", self._parse_items, tokens))
        return and_predicates(parts)

    def _parse_chain(self, conjunction: str, next_parser: Callable, tokens: TokenReader) -> Iterator[SearchPredicate]:
        parsed = next_parser(tokens)
        if parsed:
            yield parsed

            while tokens.consume(conjunction):  # case-sensitive!
                more = next_parser(tokens)
                if not more:
                    break

                yield more

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
        token = tokens.peek_token()

        if not token or token in ITEM_STOP_TOKENS:
            return None

        tokens.get_token()  # actually consume it

        if token == "(":
            return self._parse_or(tokens)

        if token == "-":
            inner = self._parse_items(tokens)
            if inner:
                return lambda *a: not inner(*a)

        if token.startswith('"'):
            return self.get_text_predicate(clean_token(token))

        if token.endswith(":") and not tokens.is_end_of_tokens():
            name = token[:-1].casefold()
            if name in self.tags:
                saved_index = tokens.index
                try:
                    return self.get_part_predicate(name, tokens)
                except InvalidSearchTermError:
                    # If the tag is no good, we'll rewind and fall back on a
                    # literal text predicate
                    tokens.index = saved_index

        return self.get_text_predicate(token)

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
    tags = set(["installed", "hidden", "favorite", "categorized", "category", "runner", "platform"])

    def __init__(self, text: str, service) -> None:
        self.service = service
        super().__init__(text)

    def get_candidate_text(self, candidate: Any) -> str:
        return candidate["name"]

    def get_part_predicate(self, name: str, tokens: TokenReader) -> Callable:
        if name == "category":
            category = clean_token(tokens.get_token())
            return self.get_category_predicate(category)

        if name == "runner":
            runner_name = clean_token(tokens.get_token())
            return self.get_runner_predicate(runner_name)

        if name == "platform":
            platform = clean_token(tokens.get_token())
            return self.get_platform_predicate(platform)

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
