import copy
import time
from typing import Any, Callable, Optional, Set

from lutris.database import games
from lutris.database.categories import (
    get_game_ids_for_categories,
    get_uncategorized_game_ids,
    normalized_category_names,
)
from lutris.exceptions import InvalidSearchTermError
from lutris.runners import get_runner_human_name
from lutris.search_predicate import (
    FLAG_TEXTS,
    TRUE_PREDICATE,
    AndPredicate,
    FlagPredicate,
    FunctionPredicate,
    MatchPredicate,
    NotPredicate,
    OrPredicate,
    SearchPredicate,
    TextPredicate,
)
from lutris.services import SERVICES
from lutris.util.strings import get_formatted_playtime, parse_playtime_parts
from lutris.util.tokenization import (
    TokenReader,
    clean_token,
    tokenize_search,
)

ISOLATED_TOKENS = set([":", "-", "(", ")", "<", ">", ">=", "<="])
ITEM_STOP_TOKENS = (ISOLATED_TOKENS | set(["OR", "AND"])) - set(["(", "-"])


def read_flag_token(tokens: TokenReader) -> Optional[bool]:
    token = tokens.get_cleaned_token() or ""
    folded = token.casefold()
    if folded in FLAG_TEXTS:
        return FLAG_TEXTS[folded]
    raise InvalidSearchTermError(f"'{token}' was found where a flag was expected.")


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
        return self.get_predicate().accept(candidate)

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

        if not parts:
            return None
        if len(parts) == 1:
            return parts[0]
        return OrPredicate(parts)

    def _parse_items(self, tokens: TokenReader) -> Optional[SearchPredicate]:
        buffer = []
        while True:
            parsed = self._parse_item(tokens)
            if parsed:
                buffer.append(parsed)
            else:
                break

        if not buffer:
            return None
        if len(buffer) == 1:
            return buffer[0]
        return AndPredicate(buffer)

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
                return NotPredicate(inner)

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

    def with_predicate(self, predicate: SearchPredicate):
        old_predicate = self.get_predicate()  # force generation of predicate
        new_search = copy.copy(self)
        new_search.predicate = AndPredicate([old_predicate, predicate])
        return new_search

    def get_part_predicate(self, name: str, tokens: TokenReader) -> SearchPredicate:
        raise InvalidSearchTermError(f"'{name}' is not a valid search tag.")

    def get_text_predicate(self, text: str) -> SearchPredicate:
        return TextPredicate(text, self.get_candidate_text, tag="")

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

    def quote_token(self, text: str) -> str:
        if text and " " not in text:
            tokens = list(tokenize_search(text, ISOLATED_TOKENS))
            test_reader = TokenReader(tokens)
            cleaned = test_reader.get_cleaned_token_sequence(self.is_stop_token)
            if cleaned == text:
                return text
        return f'"{text}"'


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

    def __init__(self, text: str, service=None) -> None:
        self.service = service
        super().__init__(text)

    def get_candidate_text(self, candidate: Any) -> str:
        return candidate["name"]

    def get_part_predicate(self, name: str, tokens: TokenReader) -> SearchPredicate:
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

        flag_predicate = self.get_flag_predicate(name, flag)

        if flag_predicate:
            return flag_predicate

        return super().get_part_predicate(name, tokens)

    def get_flag_predicate(self, name: str, flag: Optional[bool]) -> Optional[SearchPredicate]:
        if name == "installed":
            return self.get_installed_predicate(flag)

        if name == "hidden":
            return self.get_category_flag_predicate(".hidden", "hidden", in_category=flag)

        if name == "favorite":
            return self.get_category_flag_predicate("favorite", "favorite", in_category=flag)

        if name == "categorized":
            return self.get_categorized_predicate(flag)

        return None

    def get_playtime_predicate(self, tokens: TokenReader) -> SearchPredicate:
        def get_game_playtime(db_game):
            return db_game.get("playtime")

        return self.get_duration_predicate(get_game_playtime, tokens, tag="playtime")

    def get_lastplayed_predicate(self, tokens: TokenReader) -> SearchPredicate:
        now = time.time()

        def get_game_lastplayed_duration_ago(db_game):
            lastplayed = db_game.get("lastplayed")
            if lastplayed:
                return (now - lastplayed) / (60 * 60)
            return None

        return self.get_duration_predicate(get_game_lastplayed_duration_ago, tokens, tag="lastplayed")

    def get_duration_predicate(self, value_function: Callable, tokens: TokenReader, tag: str) -> SearchPredicate:
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
            matcher = lambda *a: match_greater_playtime(*a) or match_playtime(*a)  # noqa: E731
            tokens.get_token()
        elif operator == "<=":
            matcher = lambda *a: match_lesser_playtime(*a) or match_playtime(*a)  # noqa: E731
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

        text = f"{tag}:{operator}{get_formatted_playtime(duration)}"
        return FunctionPredicate(matcher, text)

    def get_directory_predicate(self, directory: str) -> SearchPredicate:
        return TextPredicate(directory, lambda c: c.get("directory"), tag="directory")

    def get_installed_predicate(self, installed: Optional[bool]) -> SearchPredicate:
        if self.service:

            def is_installed(db_game):
                appid = db_game.get("appid")
                return bool(appid and appid in games.get_service_games(self.service.id))

            return FlagPredicate(installed, is_installed, tag="installed")

        return FlagPredicate(installed, lambda db_game: bool(db_game["installed"]), tag="installed")

    def get_categorized_predicate(self, categorized: Optional[bool]) -> SearchPredicate:
        uncategorized_ids = get_uncategorized_game_ids()

        def is_categorized(db_game):
            return db_game["id"] not in uncategorized_ids

        return FlagPredicate(categorized, is_categorized, tag="categorized")

    def get_category_predicate(self, category: str) -> SearchPredicate:
        names = normalized_category_names(category, subname_allowed=True)
        category_game_ids = set(get_game_ids_for_categories(names))

        def match_category(db_game):
            game_id = db_game["id"]
            return game_id in category_game_ids

        text = f"category:{self.quote_token(category)}"
        return MatchPredicate(match_category, text=text, tag="category", value=category)

    def get_category_flag_predicate(self, category: str, tag: str, in_category: Optional[bool] = True) -> FlagPredicate:
        names = normalized_category_names(category, subname_allowed=True)
        category_game_ids = set(get_game_ids_for_categories(names))

        def is_in_category(db_game):
            game_id = db_game["id"]
            return game_id in category_game_ids

        return FlagPredicate(in_category, is_in_category, tag=tag)

    def get_service_predicate(self, service_name: str) -> SearchPredicate:
        service_name = service_name.casefold()

        def match_service(db_game):
            game_service = db_game.get("service")
            if not game_service:
                return False

            if game_service.casefold() == service_name:
                return True

            service = SERVICES.get(game_service)
            return service and service_name in service.name.casefold()

        text = f"source:{service_name}"
        return MatchPredicate(match_service, text=text, tag="source", value=service_name)

    def get_runner_predicate(self, runner_name: str) -> SearchPredicate:
        folded_runner_name = runner_name.casefold()

        def match_runner(db_game):
            game_runner = db_game.get("runner")

            if not game_runner:
                return False

            if game_runner.casefold() == folded_runner_name:
                return True

            runner_human_name = get_runner_human_name(game_runner)
            return runner_name in runner_human_name.casefold()

        text = f"runner:{self.quote_token(runner_name)}"
        return MatchPredicate(match_runner, text=text, tag="runner", value=runner_name)

    def get_platform_predicate(self, platform: str) -> SearchPredicate:
        folded_platform = platform.casefold()

        def match_platform(db_game):
            game_platform = db_game.get("platform")
            if game_platform:
                return folded_platform in game_platform.casefold()
            if self.service:
                platforms = [p.casefold() for p in self.service.get_game_platforms(db_game)]
                matches = [p for p in platforms if folded_platform in p]
                return any(matches)
            return False

        text = f"platform:{self.quote_token(platform)}"
        return MatchPredicate(match_platform, text=text, tag="platform", value=platform)


class RunnerSearch(BaseSearch):
    """A search for runners, which applies to the runner objects."""

    tags = set(["installed"])

    def get_candidate_text(self, candidate: Any) -> str:
        return f"{candidate.name}\n{candidate.description}"

    def get_part_predicate(self, name: str, tokens: TokenReader) -> SearchPredicate:
        if name == "installed":
            flag = read_flag_token(tokens)

            if flag is None:
                return TRUE_PREDICATE

            return self.get_installed_predicate(flag)

        return super().get_part_predicate(name, tokens)

    def get_installed_predicate(self, installed: bool) -> SearchPredicate:
        return FlagPredicate(installed, lambda runner: runner.is_installed(), tag="installed")
