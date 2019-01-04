class LutrisError(Exception):
    """Base exception for Lutris related errors"""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class GameConfigError(LutrisError):
    """Throw this error when the game configuration prevents the game from
    running properly.
    """
