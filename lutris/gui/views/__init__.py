"""Common values used for views"""

(
    COL_ID,
    COL_SLUG,
    COL_NAME,
    COL_SORTNAME,
    COL_MEDIA_PATHS,
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
    COL_MODIFIED_AT,
    COL_MODIFIED_AT_TEXT,
) = list(range(18))

COLUMN_NAMES = {
    COL_NAME: "name",
    COL_YEAR: "year",
    COL_RUNNER_HUMAN_NAME: "runner",
    COL_PLATFORM: "platform",
    COL_LASTPLAYED_TEXT: "lastplayed",
    COL_INSTALLED_AT_TEXT: "installedat",
    COL_PLAYTIME_TEXT: "playtime",
    COL_MODIFIED_AT_TEXT: "modifiedat",
}
