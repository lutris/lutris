from abc import ABC, abstractmethod
from typing import Any, Callable, List, Optional

from lutris.util.strings import strip_accents


class SearchPredicate(ABC):
    @abstractmethod
    def accept(self, candidate: Any) -> bool:
        return True


class FunctionPredicate(SearchPredicate):
    def __init__(self, predicate: Callable[[Any], bool]) -> None:
        self.predicate = predicate

    def accept(self, candidate: Any) -> bool:
        return self.predicate(candidate)


class TextPredicate(SearchPredicate):
    def __init__(self, match_text: str, text_function: Callable[[Any], Optional[str]]):
        self.stripped_text = strip_accents(match_text).casefold()
        self.text_function = text_function

    def accept(self, candidate: Any) -> bool:
        candidate_text = self.text_function(candidate)
        if not candidate_text:
            return False

        candidate_text = strip_accents(candidate_text).casefold()
        return bool(candidate_text and self.stripped_text in candidate_text)


class FlagPredicate(SearchPredicate):
    def __init__(self, flag: Optional[bool], flag_function: Callable[[Any], bool]):
        self.flag = flag
        self.flag_function = flag_function

    def accept(self, candidate: Any) -> bool:
        if self.flag is None:
            return True
        return self.flag == self.flag_function(candidate)


class NotPredicate(SearchPredicate):
    def __init__(self, to_negate: SearchPredicate) -> None:
        self.to_negate = to_negate

    def accept(self, candidate: Any) -> bool:
        return not self.to_negate.accept(candidate)


class AndPredicate(SearchPredicate):
    def __init__(self, components: List[SearchPredicate]) -> None:
        self.components = components

    def accept(self, candidate: Any) -> bool:
        for c in self.components:
            if not c.accept(candidate):
                return False
        return True


class OrPredicate(SearchPredicate):
    def __init__(self, components: List[SearchPredicate]) -> None:
        self.components = components

    def accept(self, candidate: Any) -> bool:
        for c in self.components:
            if c.accept(candidate):
                return True
        return False


class TruePredicate(SearchPredicate):
    def accept(self, candidate: Any) -> bool:
        return True


TRUE_PREDICATE: SearchPredicate = TruePredicate()
