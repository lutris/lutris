"""The errors the backend's calls raise. Each is a LutrisError, whose message is
meant for the user."""

from lutris.exceptions import LutrisError, MisconfigurationError
from lutris.runners import InvalidRunnerError, RunnerInstallationError

__all__ = ["InvalidRunnerError", "LutrisError", "MisconfigurationError", "RunnerInstallationError"]
