from typing import Iterable, List, Optional, Set


def clean_token(to_clean: Optional[str]) -> str:
    """Removes quotes from a token, if they are present; if they are not, this strips whitespace
    off the token."""
    if to_clean is None:
        return ""

    if to_clean.startswith('"'):
        return to_clean[1:-1] if to_clean.endswith('"') else to_clean[1:]

    return to_clean.strip()


def tokenize_search(text: str, isolated_characters: Set[str], tags: Set[str]) -> Iterable[str]:
    """Iterates through a text and breaks in into tokens. Every character of the text is present
    in exactly one token returned, all in order, so the original text can be reconstructed by concatenating the
    tokens.

    Tokens are separated by whitespace, but also certain characters (isolated_characters) are kept as separate tokens.
    Double-quoted text are protected from further tokenization. Tokens that start with any of the 'tags', followed by
    a ':' are also separated."""

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

            if ch in isolated_characters:
                yield buffer
                yield ch
                buffer = ""
                continue
            elif ch == ":" and buffer.casefold() in tags:
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

    # Since we blindly return empty buffers, we must now filter them out
    return filter(lambda t: len(t) > 0, _tokenize())


def implicitly_join_tokens(tokens: Iterable[str], isolated_tokens: Set[str]) -> Iterable[str]:
    """Iterates the tokens, but joins together consecutive tokens that aren't quoted and aren't
    'special'; tags (ending with ':') are protected, along with the tag argument (its next token);
    any tokens matching 'isolated_tokens' also won't be joined."""

    def is_isolated(t: str):
        return t.startswith('"') or t in isolated_tokens

    def _join():
        buffer = ""
        isolate_next = False
        for token in tokens:
            if token.endswith(":"):
                # If a tag is found, yield it separately, but remember to
                # yield the next token separately too.
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

    # Since we blindly return empty buffers, we must now filter them out
    return filter(lambda t: t and not t.isspace(), _join())


class TokenReader:
    """TokenReader reads through a list of tokens, like an iterator. But it can also peek ahead, and you
    can save and store your 'place' in the token list via the 'index' member."""

    def __init__(self, tokens: List[str]) -> None:
        self.tokens = tokens
        self.index = 0

    def is_end_of_tokens(self):
        """True if get_token() and peek_token() will return None."""
        return self.index >= len(self.tokens)

    def get_token(self) -> Optional[str]:
        """Returns the next token, and advances one token in the list. Returns None if
        the end of tokens has been reached."""
        if self.index >= len(self.tokens):
            return None

        token = self.tokens[self.index]
        self.index += 1
        return token

    def peek_token(self) -> Optional[str]:
        """Returns the next token, or None if the end of tokens has been reached. However,
        will not advance - repeated calls return the same token."""
        if self.index >= len(self.tokens):
            return None

        return self.tokens[self.index]

    def consume(self, candidate: str) -> bool:
        """If the next token is 'candidate', advances over it and returns True;
        if not returns False and leaves the token as it was."""
        token = self.peek_token()
        if candidate and token == candidate:
            self.index += 1
            return True
        return False
