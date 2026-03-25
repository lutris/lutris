"""Profile management for Lutris multi-user support.

Each profile has its own:
- Wine prefixes   (~/.local/share/lutris/profiles/{id}/wine-prefixes/{game_slug}/)
- Save game dirs  (~/.local/share/lutris/profiles/{id}/saves/{game_slug}/)
- Config overrides(~/.local/share/lutris/profiles/{id}/games/{configpath}.yml)
- Playtime and lastplayed statistics

Game installations and runners are shared across all profiles.
"""

import os
from typing import Optional

from lutris import settings
from lutris.database.profiles import (
    DEFAULT_PROFILE_ID,
    add_profile,
    ensure_default_profile,
    get_all_profiles,
    get_profile,
)
from lutris.util.log import logger

# Setting key used to persist the active profile across sessions.
_CURRENT_PROFILE_SETTING = "current_profile"


class ProfileManager:
    """Singleton that tracks the currently active profile and exposes
    per-profile directory helpers."""

    _instance: Optional["ProfileManager"] = None

    def __init__(self) -> None:
        self._profile_id: str = DEFAULT_PROFILE_ID

    # ------------------------------------------------------------------
    # Singleton access
    # ------------------------------------------------------------------

    @classmethod
    def get_instance(cls) -> "ProfileManager":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.load_current()
        return cls._instance

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def load_current(self) -> None:
        """Read the active profile from lutris.conf. Falls back to 'default'."""
        ensure_default_profile()
        saved = settings.read_setting(_CURRENT_PROFILE_SETTING)
        if saved and get_profile(saved):
            self._profile_id = saved
        else:
            self._profile_id = DEFAULT_PROFILE_ID
        os.makedirs(self.get_profile_dir(), exist_ok=True)
        logger.debug("Active profile: %s", self._profile_id)

    # ------------------------------------------------------------------
    # Active profile
    # ------------------------------------------------------------------

    @property
    def current_profile_id(self) -> str:
        return self._profile_id

    def switch(self, profile_id: str) -> None:
        """Switch the active profile and persist the choice."""
        if not get_profile(profile_id):
            raise ValueError(f"Profile '{profile_id}' does not exist.")
        self._profile_id = profile_id
        settings.write_setting(_CURRENT_PROFILE_SETTING, profile_id)
        os.makedirs(self.get_profile_dir(), exist_ok=True)
        logger.info("Switched to profile: %s", profile_id)

    def create_profile(self, name: str, icon: str = "") -> str:
        """Create a new profile and switch to it. Returns the new profile id."""
        profile_id = add_profile(name, icon=icon)
        os.makedirs(self.get_profile_dir(profile_id), exist_ok=True)
        return profile_id

    def get_all_profiles(self):
        return get_all_profiles()

    # ------------------------------------------------------------------
    # Directory helpers
    # ------------------------------------------------------------------

    def get_profile_dir(self, profile_id: Optional[str] = None) -> str:
        """Root directory for a profile's per-user data."""
        pid = profile_id or self._profile_id
        return os.path.join(settings.PROFILES_DIR, pid)

    def get_wine_prefix_path(self, game_slug: str, profile_id: Optional[str] = None) -> str:
        """Return the Wine prefix directory for *game_slug* under this profile.

        The directory is not created here; WinePrefixManager will do that on
        first launch.
        """
        return os.path.join(self.get_profile_dir(profile_id), "wine-prefixes", game_slug)

    def get_saves_path(self, game_slug: str, profile_id: Optional[str] = None) -> str:
        """Return the saves directory for *game_slug* under this profile."""
        path = os.path.join(self.get_profile_dir(profile_id), "saves", game_slug)
        os.makedirs(path, exist_ok=True)
        return path

    def get_profile_games_config_dir(self, profile_id: Optional[str] = None) -> str:
        """Directory that stores per-profile game config overrides."""
        return os.path.join(self.get_profile_dir(profile_id), "games")

    def get_profile_game_config_path(self, configpath: str, profile_id: Optional[str] = None) -> str:
        """Return the path to a profile-level config override YAML for a game."""
        return os.path.join(self.get_profile_games_config_dir(profile_id), f"{configpath}.yml")


# ---------------------------------------------------------------------------
# Module-level convenience helpers
# ---------------------------------------------------------------------------


def get_profile_manager() -> ProfileManager:
    """Return the global ProfileManager singleton."""
    return ProfileManager.get_instance()
