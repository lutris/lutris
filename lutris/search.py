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


def tokenize_search(text: str) -> Iterable[str]:
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

            if ch == "-":
                yield buffer
                yield ch
                buffer = ""
                continue
            elif ch == ":":
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


def implicitly_join_tokens(tokens: Iterable[str]) -> Iterable[str]:
    def is_isolated(t: str):
        return t.startswith('"') or t == "OR" or t == "AND" or t == "-"

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


class BaseSearch:
    flag_texts = {"true": True, "yes": True, "false": False, "no": False, "maybe": None}
    tags = []

    def __init__(self, text: str) -> None:
        self.text = text
        self.predicates: Optional[List[Callable]] = None

    def __str__(self) -> str:
        return self.text

    @property
    def is_empty(self) -> bool:
        return not self.text

    def get_candidate_text(self, candidate: Any) -> str:
        return str(candidate)

    def has_component(self, component_name: str) -> bool:
        match_token = component_name + ":"
        for token in tokenize_search(self.text):
            if token.casefold() == match_token:
                return True
        return False

    def get_predicates(self) -> List[Callable]:
        if self.predicates is None:
            if self.text:
                joined_tokens = implicitly_join_tokens(tokenize_search(self.text))
                tokens = _TokenReader(iter(joined_tokens))
                self.predicates = self._parse_or(tokens)
            else:
                self.predicates = []
        return self.predicates

    def _parse_or(self, tokens: _TokenReader) -> List[Callable]:
        parts = list(self._parse_chain("OR", self._parse_and, tokens))

        def apply_or(*args):
            for part in parts:
                if all(p(*args) for p in part):
                    return True
            return False

        return [apply_or]

    def _parse_and(self, tokens: _TokenReader) -> List[Callable]:
        parts = list(self._parse_chain("AND", self._parse_items, tokens))

        def apply_and(*args):
            for part in parts:
                if not all(p(*args) for p in part):
                    return False
            return True

        return [apply_and]

    def _parse_chain(self, conjunction: str, next_parser: Callable, tokens: _TokenReader) -> Iterator[List[Callable]]:
        yield next_parser(tokens)

        while tokens.consume(conjunction):  # case-sensitive!
            more = self._parse_and(tokens)
            if not more:
                break

            yield more

    def _parse_items(self, tokens: _TokenReader) -> List[Callable]:
        buffer = []
        while True:
            parsed = self._parse_item(tokens)
            buffer.extend(parsed)
            if not parsed:
                break
        return buffer

    def _parse_item(self, tokens: _TokenReader) -> List[Callable]:
        token = tokens.get_token()

        if not token or token == "OR" or token == "AND":
            tokens.putback(token)
            return []

        if token == "-":
            inner = self._parse_items(tokens)
            return [lambda *a, i=i: not i(*a) for i in inner]

        if token.startswith('"'):
            return [self.get_text_predicate(clean_token(token))]

        if token.endswith(":"):
            arg_token = tokens.get_token()
            if arg_token:
                name = token[:-1].casefold()
                value = clean_token(arg_token)
                part_predicate = self.get_part_predicate(name, value)
                if part_predicate:
                    return [part_predicate]
                else:
                    return [self.get_text_predicate(token + arg_token)]

        return [self.get_text_predicate(token)]

    def with_predicate(self, predicate: Callable):
        predicates = list(self.get_predicates())  # force generation of predicates & copy
        predicates.append(predicate)
        new_search = copy.copy(self)
        new_search.predicates = predicates
        return new_search

    def get_part_predicate(self, name: str, value: str) -> Optional[Callable]:
        return None

    def matches(self, candidate: Any) -> bool:
        for predicate in self.get_predicates():
            if not predicate(candidate):
                return False

        return True

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
