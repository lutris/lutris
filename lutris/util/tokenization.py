from typing import Iterable, List, Optional, Set


def clean_token(to_clean: Optional[str]) -> str:
    if to_clean is None:
        return ""

    if to_clean.startswith('"'):
        return to_clean[1:-1] if to_clean.endswith('"') else to_clean[1:]

    return to_clean.strip()


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


def implicitly_join_tokens(tokens: Iterable[str], isolated_tokens: Set[str]) -> Iterable[str]:
    def is_isolated(t: str):
        return t.startswith('"') or t in isolated_tokens

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


class TokenReader:
    def __init__(self, tokens: List[str]) -> None:
        self.tokens = tokens
        self.index = 0

    def is_end_of_tokens(self):
        return self.index >= len(self.tokens)

    def get_token(self) -> Optional[str]:
        if self.index >= len(self.tokens):
            return None

        token = self.tokens[self.index]
        self.index += 1
        return token

    def peek_token(self) -> Optional[str]:
        if self.index >= len(self.tokens):
            return None

        return self.tokens[self.index]

    def consume(self, candidate: str) -> bool:
        token = self.peek_token()
        if token == candidate:
            self.index += 1
            return True
        return False
