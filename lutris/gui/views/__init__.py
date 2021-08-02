"""Common values used for views"""
(
    COL_ID,
    COL_SLUG,
    COL_NAME,
    COL_ICON,
    COL_YEAR,
    COL_RUNNER,
    COL_RUNNER_HUMAN_NAME,
    COL_PLATFORM,
    COL_LASTPLAYED,
    COL_LASTPLAYED_TEXT,
    COL_INSTALLED,
    COL_INSTALLED_AT,
    COL_INSTALLED_AT_TEXT,
    COL_PLAYTIME,
    COL_PLAYTIME_TEXT,
) = list(range(15))

COLUMN_NAMES = {
    COL_NAME: "name",
    COL_YEAR: "year",
    COL_RUNNER_HUMAN_NAME: "runner",
    COL_PLATFORM: "platform",
    COL_LASTPLAYED_TEXT: "lastplayed",
    COL_INSTALLED_AT_TEXT: "installedat",
    COL_PLAYTIME_TEXT: "playtime",
}
