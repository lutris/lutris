import copy
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional

from lutris.database import games
from lutris.database.categories import (
    get_game_ids_for_categories,
    get_uncategorized_game_ids,
    normalized_category_names,
)
from lutris.runners.runner import Runner
from lutris.util.strings import strip_accents


def tokenize_search(text: str, tags: Iterable[str]) -> Iterable[str]:
    tag_set = set(tags)

    def _tokenize():
        buffer = ""
        it = iter(text)
        while True:
            ch = next(it, None)
            if ch is None:
                break

            if ch.isspace() != buffer.isspace():
                yield buffer
                buffer = ""

            if ch == "-" or ch == "(" or ch == ")":
                yield buffer
                yield ch
                buffer = ""
                continue
            elif ch == ":" and buffer.casefold() in tag_set:
                buffer += ch
                yield buffer
                buffer = ""
                continue
            elif ch == '"':
                yield buffer

                buffer = ch
                while True:
                    ch = next(it, None)
                    if ch is None:
                        break

                    buffer += ch

                    if ch == '"':
                        break

                yield buffer
                buffer = ""
                continue

            buffer += ch
        yield buffer

    return filter(lambda t: len(t) > 0, _tokenize())


ITEM_STOP_TOKENS = ["OR", "AND", ")"]
ISOLATED_TOKENS = ITEM_STOP_TOKENS + ["-", "("]


def implicitly_join_tokens(tokens: Iterable[str]) -> Iterable[str]:
    def is_isolated(t: str):
        return t.startswith('"') or t in ISOLATED_TOKENS

    def _join():
        buffer = ""
        isolate_next = False
        for token in tokens:
            if token.endswith(":"):
                yield buffer
                yield token
                buffer = ""
                isolate_next = True
                continue

            if isolate_next or is_isolated(token):
                yield buffer
                yield token
                buffer = ""
            else:
                buffer += token
            isolate_next = False
        yield buffer

    return filter(lambda t: t and not t.isspace(), _join())


class _TokenReader:
    def __init__(self, tokens: Iterator[str]) -> None:
        self.tokens = tokens
        self.putback_buffer = []

    def get_token(self) -> Optional[str]:
        if self.putback_buffer:
            return self.putback_buffer.pop()

        try:
            return next(self.tokens)
        except StopIteration:
            return None

    def peek_token(self) -> Optional[str]:
        token = self.get_token()
        self.putback(token)
        return token

    def consume(self, candidate) -> bool:
        token = self.get_token()
        if token == candidate:
            return True
        if token is not None:
            self.putback(token)
        return False

    def putback(self, token: Optional[str]):
        if token:
            self.putback_buffer.append(token)


def clean_token(to_clean: str) -> str:
    if to_clean.startswith('"'):
        if to_clean.endswith('"'):
            return to_clean[1:-1]
        else:
            return to_clean[1:]
    return to_clean.strip()


SearchPredicate = Callable[[Any], bool]

TRUE_PREDICATE: SearchPredicate = lambda *a: True  # noqa: E731


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
    flag_texts = {"true": True, "yes": True, "false": False, "no": False, "maybe": None}
    tags = []

    def __init__(self, text: str) -> None:
        self.text = text
        self.predicate: Optional[SearchPredicate] = None

    def __str__(self) -> str:
        return self.text

    @property
    def is_empty(self) -> bool:
        return not self.text

    def get_candidate_text(self, candidate: Any) -> str:
        return str(candidate)

    def has_component(self, component_name: str) -> bool:
        if component_name in self.tags:
            match_token = component_name + ":"
            for token in tokenize_search(self.text, self.tags):
                if token.casefold() == match_token:
                    return True
        return False

    def get_predicate(self) -> SearchPredicate:
        if self.predicate is None:
            if self.text:
                joined_tokens = implicitly_join_tokens(tokenize_search(self.text, self.tags))
                tokens = _TokenReader(iter(joined_tokens))
                self.predicate = self._parse_or(tokens) or TRUE_PREDICATE
            else:
                self.predicate = TRUE_PREDICATE
        return self.predicate

    def _parse_or(self, tokens: _TokenReader) -> Optional[SearchPredicate]:
        parts = list(self._parse_chain("OR", self._parse_and, tokens))
        return or_predicates(parts)

    def _parse_and(self, tokens: _TokenReader) -> Optional[SearchPredicate]:
        parts = list(self._parse_chain("AND", self._parse_items, tokens))
        return and_predicates(parts)

    def _parse_chain(self, conjunction: str, next_parser: Callable, tokens: _TokenReader) -> Iterator[SearchPredicate]:
        parsed = next_parser(tokens)
        if parsed:
            yield parsed

            while tokens.consume(conjunction):  # case-sensitive!
                more = next_parser(tokens)
                if not more:
                    break

                yield more

    def _parse_items(self, tokens: _TokenReader) -> Optional[SearchPredicate]:
        buffer = []
        while True:
            parsed = self._parse_item(tokens)
            if parsed:
                buffer.append(parsed)
            else:
                break

        return and_predicates(buffer)

    def _parse_item(self, tokens: _TokenReader) -> Optional[SearchPredicate]:
        token = tokens.get_token()

        if not token or token in ITEM_STOP_TOKENS:
            tokens.putback(token)
            return None

        if token == "(":
            return self._parse_or(tokens)

        if token == "-":
            inner = self._parse_items(tokens)
            if inner:
                return lambda *a: not inner(*a)

        if token.startswith('"'):
            return self.get_text_predicate(clean_token(token))

        if token.endswith(":"):
            name = token[:-1].casefold()
            if name in self.tags:
                arg_token = tokens.get_token()
                if arg_token:
                    value = clean_token(arg_token)
                    return self.get_part_predicate(name, value) or self.get_text_predicate(token + arg_token)

        return self.get_text_predicate(token)

    def with_predicate(self, predicate: Callable):
        old_predicate = self.get_predicate()  # force generation of predicate
        new_search = copy.copy(self)
        new_search.predicate = lambda *a: old_predicate(*a) and predicate(*a)
        return new_search

    def get_part_predicate(self, name: str, value: str) -> Optional[Callable]:
        return None

    def matches(self, candidate: Any) -> bool:
        return self.get_predicate()(candidate)

    def get_text_predicate(self, text: str) -> Callable:
        stripped = strip_accents(text).casefold()

        def match_text(candidate):
            name = strip_accents(self.get_candidate_text(candidate)).casefold()
            return stripped in name

        return match_text


class GameSearch(BaseSearch):
    tags = ["installed", "hidden", "favorite", "categorized", "category", "runner", "platform"]

    def __init__(self, text: str, service) -> None:
        self.service = service
        super().__init__(text)

    def get_candidate_text(self, candidate: Any) -> str:
        return candidate["name"]

    def get_part_predicate(self, name: str, value: str) -> Optional[Callable]:
        folded_value = value.casefold()
        if folded_value in self.flag_texts:
            flag = self.flag_texts[folded_value]

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

        if name == "category":
            category = value.strip()
            return self.get_category_predicate(category)

        if name == "runner":
            runner_name = value.strip()
            return self.get_runner_predicate(runner_name)

        if name == "platform":
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
    tags = ["installed"]

    def get_candidate_text(self, candidate: Any) -> str:
        return f"{candidate.name}\n{candidate.description}"

    def get_part_predicate(self, name: str, value: str) -> Optional[Callable]:
        if value in self.flag_texts:
            flag = self.flag_texts[value]
            if name == "installed":
                if flag is None:
                    return lambda *args: True

                return self.get_installed_predicate(flag)

        return super().get_part_predicate(name, value)

    def get_installed_predicate(self, installed: bool) -> Callable:
        def match_installed(runner: Runner):
            is_installed = runner.is_installed()
            return installed == is_installed

        return match_installed
