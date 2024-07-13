from __future__ import annotations

from typing import Callable, Iterable, List, Optional


def clean_token(to_clean: Optional[str]) -> str:
    """Removes quotes from a token, if they are present; if they are not, this strips whitespace
    off the token."""
    if to_clean is None:
        return ""

    if to_clean.startswith('"'):
        return to_clean[1:-1] if to_clean.endswith('"') else to_clean[1:]

    return to_clean.strip()


def tokenize_search(text: str, isolated_tokens: Iterable[str]) -> List[str]:
    """Iterates through a text and breaks in into tokens. Every character of the text is present
    in exactly one token returned, all in order, so the original text can be reconstructed by concatenating the
    tokens.

    Tokens are separated by whitespace, but also certain characters (isolated_characters) are kept as separate tokens.
    Double-quoted text are protected from further tokenization."""

    isolating_chars = set(ch for tok in isolated_tokens for ch in tok)
    isolated_tokens = sorted(isolated_tokens, key=lambda tok: -len(tok))

    def basic_tokenize():
        tokens = []
        buffer = ""
        it = iter(text)
        while True:
            ch = next(it, None)
            if ch is None:
                break

            if ch.isspace() != buffer.isspace():
                tokens.append(buffer)
                buffer = ""

            if ch == '"':
                tokens.append(buffer)

                buffer = ch
                while True:
                    ch = next(it, None)
                    if ch is None:
                        break

                    buffer += ch

                    if ch == '"':
                        break

                tokens.append(buffer)
                buffer = ""
                continue

            buffer += ch
        tokens.append(buffer)
        return tokens

    def split_isolated_tokens(tokens: List[str]) -> None:
        token_index = 0
        while token_index < len(tokens):
            token = tokens[token_index]
            if not token.startswith('"'):
                char_index = 0
                while char_index < len(token):
                    if token[char_index] in isolating_chars:
                        for candidate in isolated_tokens:
                            if token[char_index:].startswith(candidate):
                                tokens[token_index] = token[:char_index]
                                token_index += 1
                                tokens.insert(token_index, candidate)
                                token = token[(char_index + len(candidate)) :]
                                token_index += 1
                                tokens.insert(token_index, token)
                                char_index = -1  # start again with reduced token!
                                break
                    char_index += 1
            token_index += 1

    # Since we blindly return empty buffers, we must now filter them out
    basic = basic_tokenize()
    split_isolated_tokens(basic)
    return [t for t in basic if len(t)]


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
        the end of tokens has been reached. If 'skip_space' is true, this skips over
        whitespace tokens first (which means it can consume multiple tokens!)"""

        if skip_space:
            while self.index < len(self.tokens) and self.tokens[self.index].isspace():
                self.index += 1

        if self.index >= len(self.tokens):
            return None

        token = self.tokens[self.index]
        self.index += 1
        return token

    def get_cleaned_token(self) -> Optional[str]:
        """Returns the next token, skipping whitespace tokens. This method cleans the token
        with clean_token() if it is not None."""

        token = self.get_token()
        if token:
            return clean_token(token)

        return None

    def get_cleaned_token_sequence(self, stop_function: Callable[[TokenReader], bool]) -> Optional[str]:
        """This reads token until the end of tokens, or until a stop token is reached;
        that stop token is not consumed. The tokens are concatenated, including white-space
        between them, and returns. Whitespace around the tokens is stripped.

        Returns None if we reach the end of tokens before any non-whitespace token.

        If this first non-whitespace token is quoted, then this token is cleaned and returned,
        and we stop with that.

        Thus, if the token reader starts before quoted text, we return that text unquoted, and if
        not we return all text up to but not including a 'stop_tokens' token."""

        buffer = ""
        while True:
            peeked = self.peek_token()
            if peeked is None:
                break

            if peeked.startswith('"'):
                if not buffer:
                    buffer = self.get_token()
                break

            if stop_function(self):
                break

            buffer += self.get_token(skip_space=False) or ""
        return clean_token(buffer) if buffer else None

    def peek_token(self) -> Optional[str]:
        """Returns the next token, or None if the end of tokens has been reached. However,
        will not advance - repeated calls return the same token."""

        saved_index = self.index
        token = self.get_token()
        self.index = saved_index
        return token

    def peek_tokens(self, count: int) -> List[str]:
        """Returns the next 'count' tokens, or as many as are present before
        the end of tokens has been reached. However, this will not advance - repeated calls
        return the same tokens."""

        peeked = []

        saved_index = self.index
        for _i in range(0, count):
            token = self.get_token()
            if not token:
                break
            peeked.append(token)
        self.index = saved_index
        return peeked

    def consume(self, candidate: str) -> bool:
        """If the next token is 'candidate', consumes it and returns True;
        if not returns False and leaves the token reader as it was."""

        saved_index = self.index
        token = self.get_token()
        if candidate and token == candidate:
            return True

        self.index = saved_index
        return False
