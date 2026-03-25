"""Database operations for user profiles and per-profile game statistics."""

import time
from typing import Dict, List, Optional

from lutris import settings
from lutris.database import sql

DEFAULT_PROFILE_ID = "default"
DEFAULT_PROFILE_NAME = "Default"


def get_all_profiles() -> List[Dict]:
    """Return all profiles ordered by creation date."""
    with sql.db_cursor(settings.DB_PATH) as cursor:
        rows = cursor.execute(
            "SELECT id, name, icon, created_at FROM profiles ORDER BY created_at ASC"
        ).fetchall()
    return [{"id": r[0], "name": r[1], "icon": r[2], "created_at": r[3]} for r in rows]


def get_profile(profile_id: str) -> Optional[Dict]:
    """Return a single profile by id, or None if not found."""
    with sql.db_cursor(settings.DB_PATH) as cursor:
        row = cursor.execute(
            "SELECT id, name, icon, created_at FROM profiles WHERE id = ?", (profile_id,)
        ).fetchone()
    if not row:
        return None
    return {"id": row[0], "name": row[1], "icon": row[2], "created_at": row[3]}


def add_profile(name: str, profile_id: Optional[str] = None, icon: str = "") -> str:
    """Create a new profile. Returns the profile id."""
    if not profile_id:
        # Generate a slug from the name + timestamp
        slug = name.lower().replace(" ", "-")
        profile_id = f"{slug}-{int(time.time())}"
    created_at = int(time.time())
    with sql.db_cursor(settings.DB_PATH) as cursor:
        cursor.execute(
            "INSERT OR IGNORE INTO profiles (id, name, icon, created_at) VALUES (?, ?, ?, ?)",
            (profile_id, name, icon, created_at),
        )
    return profile_id


def update_profile(profile_id: str, name: Optional[str] = None, icon: Optional[str] = None) -> None:
    """Update name and/or icon of an existing profile."""
    if name is not None:
        with sql.db_cursor(settings.DB_PATH) as cursor:
            cursor.execute("UPDATE profiles SET name = ? WHERE id = ?", (name, profile_id))
    if icon is not None:
        with sql.db_cursor(settings.DB_PATH) as cursor:
            cursor.execute("UPDATE profiles SET icon = ? WHERE id = ?", (icon, profile_id))


def delete_profile(profile_id: str) -> None:
    """Delete a profile and all its per-profile game stats.

    Does not delete the 'default' profile.
    """
    if profile_id == DEFAULT_PROFILE_ID:
        raise ValueError("The default profile cannot be deleted.")
    with sql.db_cursor(settings.DB_PATH) as cursor:
        cursor.execute("DELETE FROM profile_game_stats WHERE profile_id = ?", (profile_id,))
        cursor.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))


def ensure_default_profile() -> None:
    """Create the default profile if it doesn't exist yet."""
    if not get_profile(DEFAULT_PROFILE_ID):
        add_profile(DEFAULT_PROFILE_NAME, profile_id=DEFAULT_PROFILE_ID)


# --- Per-profile game statistics ---


def get_profile_game_stats(profile_id: str, game_id: int) -> Optional[Dict]:
    """Return the playtime/lastplayed for a game under a specific profile."""
    with sql.db_cursor(settings.DB_PATH) as cursor:
        row = cursor.execute(
            "SELECT playtime, lastplayed FROM profile_game_stats WHERE profile_id = ? AND game_id = ?",
            (profile_id, str(game_id)),
        ).fetchone()
    if not row:
        return None
    return {"playtime": row[0] or 0.0, "lastplayed": row[1] or 0}


def update_profile_game_stats(profile_id: str, game_id: int, playtime: float, lastplayed: int) -> None:
    """Insert or update playtime and lastplayed for a game under a profile."""
    with sql.db_cursor(settings.DB_PATH) as cursor:
        existing = cursor.execute(
            "SELECT id FROM profile_game_stats WHERE profile_id = ? AND game_id = ?",
            (profile_id, str(game_id)),
        ).fetchone()
        if existing:
            cursor.execute(
                "UPDATE profile_game_stats SET playtime = ?, lastplayed = ? WHERE profile_id = ? AND game_id = ?",
                (playtime, lastplayed, profile_id, str(game_id)),
            )
        else:
            cursor.execute(
                "INSERT INTO profile_game_stats (profile_id, game_id, playtime, lastplayed) VALUES (?, ?, ?, ?)",
                (profile_id, str(game_id), playtime, lastplayed),
            )


def get_all_profile_stats_for_game(game_id: int) -> List[Dict]:
    """Return all per-profile stats for a given game (useful for debugging/admin)."""
    with sql.db_cursor(settings.DB_PATH) as cursor:
        rows = cursor.execute(
            "SELECT profile_id, playtime, lastplayed FROM profile_game_stats WHERE game_id = ?",
            (str(game_id),),
        ).fetchall()
    return [{"profile_id": r[0], "playtime": r[1] or 0.0, "lastplayed": r[2] or 0} for r in rows]
