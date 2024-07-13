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
    """This class is a filter function that also includes formatting and other functionality so
    it can be edited in the UI."""

    @abstractmethod
    def accept(self, candidate: Any) -> bool:
        """This method tests an object against the predicate."""
        return True

    def simplify(self) -> "SearchPredicate":
        """This method and return a simplified and flattened version of
        the predicate; the simplified predicate will match the same objects as
        the original."""
        return self

    def without_match(self, tag: str, value: Optional[str] = None) -> "SearchPredicate":
        """Returns a predicate without the MatchPredicate that has the tag and value
        given (or just the tag). Matches that are negated or the like are not removed."""
        return self

    def get_matches(self, tag: str) -> List[str]:
        """ "Returns all the values for the matches for the tag given; again any
        negated matches are ignored."""
        return []

    def without_flag(self, tag: str) -> "SearchPredicate":
        """Returns a predicate without the FlagPredicate that has the tag
        given. Flags that are negated or the like are not removed."""
        return self

    def has_flag(self, tag: str) -> bool:
        """True if the predicate has a FlagPredicate with the tag given;
        Flags that are negated or the like are ignored."""
        return False

    def get_flag(self, tag: str) -> Optional[bool]:
        """Returns the flag test value for the FlagPredicte with the tag
        given. None represents 'maybe', not that the flag is missing."""
        return None

    def to_child_text(self) -> str:
        """Returns the text of this predicate as it should be if nested inside a larger
        predicate; this may be in parentheses where __str__ would not be."""
        return str(self)

    @abstractmethod
    def __str__(self) -> str:
        pass


class FunctionPredicate(SearchPredicate):
    """This is a generate predicate that wraps a function to perform the test."""

    def __init__(self, predicate: Callable[[Any], bool], text: str) -> None:
        self.predicate = predicate
        self.text = text

    def accept(self, candidate: Any) -> bool:
        return self.predicate(candidate)

    def __str__(self):
        return self.text


class MatchPredicate(FunctionPredicate):
    """MatchPredicate is a predicate that test a property against a value; you still provide
    a function to do the test, but the object records the tag and value explicitly for editing
    purposes."""

    def __init__(self, predicate: Callable[[Any], bool], text: str, tag: str, value: str) -> None:
        super().__init__(predicate, text)
        self.tag = tag
        self.value = value

    def get_matches(self, tag: str) -> List[str]:
        return [self.value] if self.tag == tag else []

    def without_match(self, tag: str, value: Optional[str] = None) -> "SearchPredicate":
        if value is None:
            return TRUE_PREDICATE if self.tag == tag else self

        return TRUE_PREDICATE if self.tag == tag and self.value == value else self


class FlagPredicate(SearchPredicate):
    """This is a predicate to match a boolean property, with the special feature that it can
    match 'maybe' which actually matching anything. This odd setting is useful to override
    the default filtering Lutris provides, like filtering out hidden games."""

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


class TextPredicate(SearchPredicate):
    """This is a predicate with no tag used to make text generically."""

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


class NotPredicate(SearchPredicate):
    """This predicate reverses the effect of another, and also 'hides' it from
    editing methods."""

    def __init__(self, to_negate: SearchPredicate) -> None:
        self.to_negate = to_negate

    def accept(self, candidate: Any) -> bool:
        return not self.to_negate.accept(candidate)

    def to_child_text(self) -> str:
        return f"(-{self.to_negate.to_child_text()})"

    def __str__(self):
        return "-" + str(self.to_negate)


class AndPredicate(SearchPredicate):
    """This predicate combines other predicates so all must accept a candidate
    before it is accepted."""

    def __init__(self, components: List[SearchPredicate]) -> None:
        self.components = components

    def accept(self, candidate: Any) -> bool:
        for c in self.components:
            if not c.accept(candidate):
                return False
        return True

    def simplify(self) -> "SearchPredicate":
        simplified = []
        for c in self.components:
            c = c.simplify()
            if c != TRUE_PREDICATE:
                if isinstance(c, AndPredicate):
                    simplified += c.components
                else:
                    simplified.append(c)
        return AndPredicate(simplified) if simplified else TRUE_PREDICATE

    def get_matches(self, tag: str) -> List[str]:
        matches = []
        for c in self.components:
            matches += c.get_matches(tag)
        return matches

    def without_match(self, tag: str, value: Optional[str] = None) -> "SearchPredicate":
        new_components = []
        for c in self.components:
            r = c.without_match(tag, value)
            if r != TRUE_PREDICATE:
                new_components.append(r)

        if new_components != self.components:
            return AndPredicate(new_components)

        return self

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
    """This predicate combines other predicates so that a candidate is accepted
    if any component accepts it. This also hides the components from editing."""

    def __init__(self, components: List[SearchPredicate]) -> None:
        self.components = components

    def accept(self, candidate: Any) -> bool:
        for c in self.components:
            if c.accept(candidate):
                return True
        return False

    def simplify(self) -> "SearchPredicate":
        simplified = []
        for c in self.components:
            c = c.simplify()
            if c == TRUE_PREDICATE:
                return c
            if isinstance(c, OrPredicate):
                simplified += c.components
            else:
                simplified.append(c)
        return OrPredicate(simplified)

    def to_child_text(self) -> str:
        return f"({self})"

    def __str__(self):
        return " OR ".join(c.to_child_text() for c in self.components)


class TruePredicate(SearchPredicate):
    """This predicate matches everything."""

    def accept(self, candidate: Any) -> bool:
        return True

    def __str__(self):
        return ""


TRUE_PREDICATE: SearchPredicate = TruePredicate()
