from abc import ABC, abstractmethod
from typing import Any, Callable, List, Optional

from lutris.util.strings import strip_accents


class SearchPredicate(ABC):
    @abstractmethod
    def accept(self, candidate: Any) -> bool:
        return True

    def to_child_text(self) -> str:
        return str(self)

    @abstractmethod
    def __str__(self) -> str:
        pass


class FunctionPredicate(SearchPredicate):
    def __init__(self, predicate: Callable[[Any], bool], text: str) -> None:
        self.predicate = predicate
        self.text = text

    def accept(self, candidate: Any) -> bool:
        return self.predicate(candidate)

    def __str__(self):
        return self.text


class TextPredicate(SearchPredicate):
    def __init__(self, match_text: str, text_function: Callable[[Any], Optional[str]], tag: str):
        self.tag = tag
        self.match_text = match_text
        self.stripped_text = strip_accents(match_text).casefold()
        self.text_function = text_function

    def accept(self, candidate: Any) -> bool:
        candidate_text = self.text_function(candidate)
        if not candidate_text:
            return False

        candidate_text = strip_accents(candidate_text).casefold()
        return bool(candidate_text and self.stripped_text in candidate_text)

    def __str__(self):
        if self.tag:
            return f"{self.tag}: {self.match_text}"
        return self.match_text


class FlagPredicate(SearchPredicate):
    def __init__(self, flag: Optional[bool], flag_function: Callable[[Any], bool], tag: str):
        self.flag = flag
        self.flag_function = flag_function
        self.tag = tag

    def accept(self, candidate: Any) -> bool:
        if self.flag is None:
            return True
        return self.flag == self.flag_function(candidate)

    def __str__(self):
        if self.flag is None:
            flag_text = "maybe"
        else:
            flag_text = "yes" if self.flag else "no"

        return f"{self.tag}: {flag_text}"


class NotPredicate(SearchPredicate):
    def __init__(self, to_negate: SearchPredicate) -> None:
        self.to_negate = to_negate

    def accept(self, candidate: Any) -> bool:
        return not self.to_negate.accept(candidate)

    def to_child_text(self) -> str:
        return f"(-{self.to_negate.to_child_text()})"

    def __str__(self):
        return "-" + str(self.to_negate)


class AndPredicate(SearchPredicate):
    def __init__(self, components: List[SearchPredicate]) -> None:
        self.components = components

    def accept(self, candidate: Any) -> bool:
        for c in self.components:
            if not c.accept(candidate):
                return False
        return True

    def __str__(self):
        return " ".join(self.components)


class OrPredicate(SearchPredicate):
    def __init__(self, components: List[SearchPredicate]) -> None:
        self.components = components

    def accept(self, candidate: Any) -> bool:
        for c in self.components:
            if c.accept(candidate):
                return True
        return False

    def to_child_text(self) -> str:
        return f"({self})"

    def __str__(self):
        return " OR ".join(c.to_child_text() for c in self.components)


class TruePredicate(SearchPredicate):
    def accept(self, candidate: Any) -> bool:
        return True

    def __str__(self):
        return ""


TRUE_PREDICATE: SearchPredicate = TruePredicate()
