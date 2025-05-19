"""Exception handling module"""

from gettext import gettext as _


class LutrisError(Exception):
    """Base exception for Lutris related errors"""

    def __init__(self, message, *args, **kwarg):
        super().__init__(message, *args, **kwarg)
        self.message = message
        self.is_expected = False


class MissingRuntimeComponentError(LutrisError):
    """Raised when a Lutris component isn't found, but should have been installed."""

    def __init__(self, message, component_name, *args, **kwarg):
        super().__init__(message, *args, **kwarg)
        self.component_name = component_name
        self.is_expected = True


class MisconfigurationError(LutrisError):
    """Raised for incorrect configuration or installation, like incorrect
    or missing settings, missing components, that sort of thing. This has subclasses
    that are less vague."""


class DirectoryNotFoundError(MisconfigurationError):
    """Raise this error if a directory that is required is not present."""

    def __init__(self, message=None, directory=None, *args, **kwarg):
        if not message and directory:
            message = _("The directory {} could not be found").format(directory)
        super().__init__(message, *args, **kwarg)
        self.directory = directory


class GameConfigError(MisconfigurationError):
    """Throw this error when the game configuration prevents the game from
    running properly."""


class MissingBiosError(GameConfigError):
    """Throw this error when the game requires a BIOS, but none is configured."""

    def __init__(self, message=None, *args, **kwarg):
        super().__init__(message or _("A bios file is required to run this game"), *args, **kwarg)


class AuthenticationError(LutrisError):
    """Raised when authentication to a service fails"""


class UnavailableGameError(LutrisError):
    """Raised when a game is unavailable from a service"""


class UnavailableLibrariesError(MisconfigurationError):
    def __init__(self, libraries, arch=None):
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

    def __init__(self, message=None, filename=None, *args, **kwargs):
        if not message and filename:
            message = _("The file {} could not be found").format(filename)

        super().__init__(message, *args, **kwargs)
        self.filename = filename


class MissingGameExecutableError(MissingExecutableError):
    """Raise when a game's executable can't be found is not specified."""

    def __init__(self, message=None, filename=None, *args, **kwargs):
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

    def __init__(self, message=None, *args, **kwarg):
        if not message:
            message = _("Your ESYNC limits are not set correctly.")

        super().__init__(message, *args, **kwarg)


class FsyncUnsupportedError(Exception):
    """Raised when FSYNC is enabled, but is not supported by the kernel."""

    def __init__(self, message=None, *args, **kwarg):
        if not message:
            message = _("Your kernel is not patched for fsync. Please get a patched kernel to use fsync.")

        super().__init__(message, *args, **kwarg)


class InvalidSearchTermError(ValueError):
    def __init__(self, message: str, *args, **kwargs) -> None:
        super().__init__(message, *args, **kwargs)
        self.message = message
