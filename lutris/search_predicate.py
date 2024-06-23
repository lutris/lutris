from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from lutris.util.strings import strip_accents

FLAG_TEXTS: Dict[str, Optional[bool]] = {"true": True, "yes": True, "false": False, "no": False, "maybe": None}


def format_flag(flag: Optional[bool]) -> str:
    if flag is None:
        return "maybe"
    else:
        return "yes" if flag else "no"


class SearchPredicate(ABC):
    @abstractmethod
    def accept(self, candidate: Any) -> bool:
        return True

    def without_flag(self, tag: str) -> "SearchPredicate":
        return self

    def has_flag(self, tag: str) -> bool:
        return False

    def get_flag(self, tag: str) -> Optional[bool]:
        return None

    def to_child_text(self) -> str:
        return str(self)

    @abstractmethod
    def __str__(self) -> str:
        pass


class FunctionPredicate(SearchPredicate):
    def __init__(self, predicate: Callable[[Any], bool], formatter: Callable[[], str]) -> None:
        self.predicate = predicate
        self.formatter = formatter

    def accept(self, candidate: Any) -> bool:
        return self.predicate(candidate)

    def __str__(self):
        return self.formatter()


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

    def without_flag(self, tag: str) -> "SearchPredicate":
        return TRUE_PREDICATE if self.tag == tag else self

    def has_flag(self, tag: str) -> bool:
        return tag == self.tag

    def get_flag(self, tag: str) -> Optional[bool]:
        return self.flag if self.tag == tag else None

    def __str__(self):
        flag_text = format_flag(self.flag)
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

    def without_flag(self, tag: str) -> "SearchPredicate":
        new_components = []
        for c in self.components:
            r = c.without_flag(tag)
            if r != TRUE_PREDICATE:
                new_components.append(r)

        if new_components != self.components:
            return AndPredicate(new_components)

        return self

    def has_flag(self, tag: str) -> bool:
        for c in self.components:
            if c.has_flag(tag):
                return True
        return False

    def get_flag(self, tag: str) -> Optional[bool]:
        for c in self.components:
            if c.has_flag(tag):
                return c.get_flag(tag)
        return None

    def __str__(self):
        return " ".join(str(c) for c in self.components)


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
