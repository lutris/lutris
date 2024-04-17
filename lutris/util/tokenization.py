from typing import Iterable, List, Optional, Set


def clean_token(to_clean: Optional[str]) -> str:
    """Removes quotes from a token, if they are present; if they are not, this strips whitespace
    off the token."""
    if to_clean is None:
        return ""

    if to_clean.startswith('"'):
        return to_clean[1:-1] if to_clean.endswith('"') else to_clean[1:]

    return to_clean.strip()


def tokenize_search(text: str, isolated_tokens: Set[str]) -> Iterable[str]:
    """Iterates through a text and breaks in into tokens. Every character of the text is present
    in exactly one token returned, all in order, so the original text can be reconstructed by concatenating the
    tokens.

    Tokens are separated by whitespace, but also certain characters (isolated_characters) are kept as separate tokens.
    Double-quoted text are protected from further tokenization."""

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

            # TODO: Support longer tokens here
            if ch in isolated_tokens:
                yield buffer
                yield ch
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


class TokenReader:
    """TokenReader reads through a list of tokens, like an iterator. But it can also peek ahead, and you
    can save and store your 'place' in the token list via the 'index' member."""

    def __init__(self, tokens: List[str]) -> None:
        self.tokens = tokens
        self.index = 0

    def is_end_of_tokens(self):
        """True if get_token() and peek_token() will return None."""
        return self.index >= len(self.tokens)

    def get_token(self, skip_space: bool = True) -> Optional[str]:
        """Returns the next token, and advances one token in the list. Returns None if
        the end of tokens has been reached."""

        if skip_space:
            while self.index < len(self.tokens) and self.tokens[self.index].isspace():
                self.index += 1

        if self.index >= len(self.tokens):
            return None

        token = self.tokens[self.index]
        self.index += 1
        return token

    def get_cleaned_token(self) -> Optional[str]:
        token = self.get_token()
        if token:
            return clean_token(token)

        return None

    def get_cleaned_token_sequence(self, stop_tokens: Set[str]) -> Optional[str]:
        buffer = ""
        while True:
            token = self.get_token(skip_space=False)
            if token is None:
                break
            if token in stop_tokens:
                self.index -= 1
                break
            if token.startswith('"'):
                if buffer:
                    self.index -= 1
                else:
                    buffer = token
                break
            buffer += token
        return buffer if buffer else None

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
