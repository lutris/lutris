"""Exception handling module"""

from collections.abc import Iterable
from gettext import gettext as _
from typing import Any, Optional


class LutrisError(Exception):
    """Base exception for Lutris related errors"""

    def __init__(self, message: str, message_markup: str = None, *args: Any, **kwargs: Any):
        super().__init__(message, *args, **kwargs)
        self.message = message
        self.message_markup = message_markup
        self.is_expected = False


class MissingRuntimeComponentError(LutrisError):
    """Raised when a Lutris component isn't found, but should have been installed."""

    def __init__(self, message: str, component_name: str, *args: Any, **kwargs: Any):
        super().__init__(message, *args, **kwargs)
        self.component_name = component_name
        self.is_expected = True


class MisconfigurationError(LutrisError):
    """Raised for incorrect configuration or installation, like incorrect
    or missing settings, missing components, that sort of thing. This has subclasses
    that are less vague."""


class DirectoryNotFoundError(MisconfigurationError):
    """Raise this error if a directory that is required is not present."""

    def __init__(self, message: str = None, directory: str = None, *args: Any, **kwargs: Any):
        if not message and directory:
            message = _("The directory {} could not be found").format(directory)
        super().__init__(message, *args, **kwargs)
        self.directory = directory


class SymlinkNotUsableError(MisconfigurationError):
    """Raise this error if a symlink that is required is not usable."""

    def __init__(self, message: str = None, link: str = None, *args: Any, **kwarg: Any):
        if not message and link:
            message = message or _("The link {} could not be used.").format(link)
        super().__init__(message, *args, **kwarg)
        self.link = link


class GameConfigError(MisconfigurationError):
    """Throw this error when the game configuration prevents the game from
    running properly."""


class MissingBiosError(GameConfigError):
    """Throw this error when the game requires a BIOS, but none is configured."""

    def __init__(self, message: str = None, *args: Any, **kwargs: Any):
        super().__init__(message or _("A bios file is required to run this game"), *args, **kwargs)


class AuthenticationError(LutrisError):
    """Raised when authentication to a service fails"""


class UnavailableGameError(LutrisError):
    """Raised when a game is unavailable from a service"""


class UnavailableLibrariesError(MisconfigurationError):
    def __init__(self, libraries: Iterable[str], arch: Optional[str] = None):
        message = _("The following {arch} libraries are required but are not installed on your system:\n{libs}").format(
            arch=arch if arch else "", libs=", ".join(libraries)
        )
        super().__init__(message)
        self.libraries = libraries


class UnavailableRunnerError(MisconfigurationError):
    """Raised when a runner is not installed or not installed fully."""


class UnspecifiedVersionError(MisconfigurationError):
    """Raised when a version number must be specified, but was not."""


class MissingExecutableError(MisconfigurationError):
    """Raised when a program can't be located."""


class MissingMediaError(LutrisError):
    """Raised when an image file could not be found."""

    def __init__(self, message: str = None, filename: str = None, *args: Any, **kwargs: Any):
        if not message and filename:
            message = _("The file {} could not be found").format(filename)

        super().__init__(message, *args, **kwargs)
        self.filename = filename


class MissingGameExecutableError(MissingExecutableError):
    """Raise when a game's executable can't be found is not specified."""

    def __init__(self, message: str = None, filename: str = None, *args: Any, **kwargs: Any):
        if not message:
            if filename:
                message = _("The file {} could not be found").format(filename)
            else:
                message = _("This game has no executable set. The install process didn't finish properly.")

        super().__init__(message, *args, **kwargs)
        self.filename = filename


class InvalidGameMoveError(LutrisError):
    """Raised when a game can't be moved as desired; we may have to just set the location."""


class EsyncLimitError(Exception):
    """Raised when the ESYNC limit is not set correctly."""

    def __init__(self, message: str = None, *args: Any, **kwargs: Any):
        if not message:
            message = _("Your ESYNC limits are not set correctly.")

        super().__init__(message, *args, **kwargs)


class FsyncUnsupportedError(Exception):
    """Raised when FSYNC is enabled, but is not supported by the kernel."""

    def __init__(self, message: str = None, *args: Any, **kwargs: Any):
        if not message:
            message = _("Your kernel is not patched for fsync. Please get a patched kernel to use fsync.")

        super().__init__(message, *args, **kwargs)


class InvalidSearchTermError(ValueError):
    def __init__(self, message: str, *args: Any, **kwargs: Any):
        super().__init__(message, *args, **kwargs)
        self.message = message
