#!/usr/bin/env bash
# Lutris release smoke test - end-to-end checks of the basic features.
#
# Run this from a git checkout before each release. Everything happens inside a
# throwaway profile: HOME and the XDG directories point into a temp folder, so
# the Lutris install of the machine is never modified (except by an explicit
# --existing-profile copy, which only reads the source).
#
# Two scenarios are covered:
#
#   fresh     brand new profile: first start, empty library, adding a game,
#             launching it, exporting it
#   existing  a profile that already has a library, an old-style game config and
#             an old migration_version, i.e. what a user upgrading sees
#
# The game used for the launch checks is a small shell script, so no download,
# no Wine prefix and no GPU are involved.
#
# A display is required: every command but --version has to start the client's
# GtkApplication. Run this from a desktop session, or with
# `xvfb-run -a utils/release-smoke-test.sh` when there is none.
#
# Exit status: 0 if every check passed, 1 otherwise.

set -uo pipefail

SCRIPT_PATH=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")
SCRIPT_DIR=$(dirname "$SCRIPT_PATH")
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
LUTRIS_ENTRY="$REPO_ROOT/bin/lutris"

ORIG_ARGS=("$@")

TIMEOUT=240
KEEP=0
RUN_GUI=1
WITH_EXEC=0
SCENARIO=both
EXISTING_PROFILE=""

usage() {
    cat <<'EOF'
Lutris release smoke test (end-to-end, basic features).

Usage: utils/release-smoke-test.sh [options]

  --scenario fresh|existing|both   which profile scenario to run (default: both)
  --existing-profile DIR           also clone a real profile (~/.local/share/lutris)
                                   into the sandbox and check that it still loads
  --keep                           keep the sandbox directory and print its path
  --no-gui                         skip the "window stays up" check
  --with-exec                      also check `lutris -e`, which hangs today; see
                                   https://github.com/lutris/lutris/issues/6997
  --timeout SECONDS                per-command timeout (default: 240)
  -h, --help                       this text

Every command runs on a private D-Bus session, so a Lutris instance running on the
machine can neither receive nor answer them.

Exit status: 0 if all checks passed, 1 otherwise.
EOF
}

need_value() { # <option> <remaining-argument-count>
    if [ "${2:-0}" -lt 2 ] || [ -z "${3:-}" ]; then
        echo "error: $1 needs a value" >&2
        usage >&2
        exit 2
    fi
}

while [ $# -gt 0 ]; do
    case "$1" in
        --scenario) need_value "$1" $# "${2:-}"; SCENARIO="$2"; shift 2 ;;
        --scenario=*) SCENARIO="${1#*=}"; shift ;;
        --existing-profile) need_value "$1" $# "${2:-}"; EXISTING_PROFILE="$2"; shift 2 ;;
        --existing-profile=*) EXISTING_PROFILE="${1#*=}"; shift ;;
        --timeout) need_value "$1" $# "${2:-}"; TIMEOUT="$2"; shift 2 ;;
        --timeout=*) TIMEOUT="${1#*=}"; shift ;;
        --keep) KEEP=1; shift ;;
        --no-gui) RUN_GUI=0; shift ;;
        --with-exec) WITH_EXEC=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "error: unknown option '$1'" >&2; usage >&2; exit 2 ;;
    esac
done

case "$SCENARIO" in
    fresh|existing|both) ;;
    *) echo "error: --scenario must be fresh, existing or both" >&2; exit 2 ;;
esac

case "$TIMEOUT" in
    ''|*[!0-9]*) echo "error: --timeout needs a number of seconds" >&2; exit 2 ;;
esac

if [ "$TIMEOUT" -le 0 ]; then
    echo "error: --timeout must be at least 1 second ('timeout 0' would mean no limit)" >&2
    exit 2
fi

if [ "$(id -u)" -eq 0 ]; then
    echo "error: run the smoke test as a normal user (Lutris refuses to run as root)" >&2
    exit 2
fi

# The client is a GtkApplication, so without a display even `lutris -l -j` exits at
# once: the run would fail every check but --version. Stop here, before the sandbox
# and the private bus exist, with a message that says what to do instead.
if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ] && ! command -v xvfb-run >/dev/null 2>&1; then
    echo "error: no display, and xvfb-run is not installed" >&2
    echo "       run this from a desktop session, or install xvfb and use:" >&2
    echo "       xvfb-run -a utils/release-smoke-test.sh" >&2
    exit 2
fi

# Only --version is answered by the invoking process (do_handle_local_options); every
# other command line is forwarded to the primary instance of net.lutris.Lutris, and
# redirecting HOME and the XDG directories does not change that. So a Lutris instance
# of the machine would receive our --import and run our games against the real library.
# Re-running the whole script on a private session bus keeps every command inside it.
if [ -z "${LUTRIS_SMOKE_SESSION:-}" ]; then
    if ! command -v dbus-run-session >/dev/null 2>&1; then
        echo "error: dbus-run-session not found (it is part of the dbus package)" >&2
        exit 2
    fi
    exec env LUTRIS_SMOKE_SESSION=1 dbus-run-session -- "$SCRIPT_PATH" \
        "${ORIG_ARGS[@]+"${ORIG_ARGS[@]}"}"
fi

# ---------------------------------------------------------------------------
# Interpreter and expectations, read from the source tree
# ---------------------------------------------------------------------------

if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
    PY="$REPO_ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PY=$(command -v python3)
else
    echo "error: no python3 found" >&2
    exit 2
fi

EXPECTED_VERSION=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$REPO_ROOT/lutris/__init__.py")
EXPECTED_MIGRATION_VERSION=$(sed -n 's/^MIGRATION_VERSION = \([0-9]\{1,\}\).*/\1/p' \
    "$REPO_ROOT/lutris/migrations/__init__.py")
if [ -z "$EXPECTED_VERSION" ] || [ -z "$EXPECTED_MIGRATION_VERSION" ]; then
    echo "error: could not read the version from the source tree" >&2
    exit 2
fi

# Display: the current session, or Xvfb. The guard above guarantees that one of the
# two is usable, so the only thing left to record is which one it is.
DISP=()
DISPLAY_NOTE="this session"
if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
    DISP=(xvfb-run -a)
    DISPLAY_NOTE="xvfb-run -a"
fi

# ---------------------------------------------------------------------------
# Sandbox
# ---------------------------------------------------------------------------

SANDBOX=$(mktemp -d "${TMPDIR:-/tmp}/lutris-smoke.XXXXXX") || exit 1

cleanup() {
    if [ "$KEEP" -eq 1 ]; then
        printf '\nSandbox kept at %s\n' "$SANDBOX"
    else
        case "$SANDBOX" in
            */lutris-smoke.*) rm -rf "$SANDBOX" ;;
        esac
    fi
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

C_PASS=""; C_FAIL=""; C_SKIP=""; C_BOLD=""; C_RESET=""
if [ -t 1 ]; then
    C_PASS=$'\033[32m'; C_FAIL=$'\033[31m'; C_SKIP=$'\033[33m'
    C_BOLD=$'\033[1m'; C_RESET=$'\033[0m'
fi

PASS=0
FAIL=0
SKIP=0
FAILURES=()

ok()   { PASS=$((PASS + 1)); printf '  %s[PASS]%s %s\n' "$C_PASS" "$C_RESET" "$1"; }
skip() { SKIP=$((SKIP + 1)); printf '  %s[SKIP]%s %s%s\n' "$C_SKIP" "$C_RESET" "$1" "${2:+ - $2}"; }
fail() {
    FAIL=$((FAIL + 1)); FAILURES+=("$1")
    printf '  %s[FAIL]%s %s\n' "$C_FAIL" "$C_RESET" "$1"
    if [ -n "${2:-}" ]; then printf '         %s\n' "$2"; fi
}
section() { printf '\n%s== %s ==%s\n' "$C_BOLD" "$1" "$C_RESET"; }

expect_eq() { # <name> <expected> <actual>
    if [ "${3:-}" = "$2" ]; then ok "$1"; else fail "$1" "expected [$2], got [${3:-<empty>}]"; fi
}

expect_contains() { # <name> <haystack> <needle>
    case "${2:-}" in
        *"$3"*) ok "$1" ;;
        *) fail "$1" "output does not contain [$3]" ;;
    esac
}

expect_not_contains() { # <name> <haystack> <needle>
    case "${2:-}" in
        *"$3"*) fail "$1" "output still contains [$3]" ;;
        *) ok "$1" ;;
    esac
}

expect_file() { # <name> <path>
    if [ -s "$2" ]; then ok "$1"; else fail "$1" "missing or empty: $2"; fi
}

# ---------------------------------------------------------------------------
# Profile helpers
# ---------------------------------------------------------------------------

profile_reset() { # <scenario-name>
    P_ROOT="$SANDBOX/$1"
    P_HOME="$P_ROOT/home"
    P_WORK="$P_ROOT/work"
    P_GAMES="$P_ROOT/games"
    P_LOGS="$P_ROOT/logs"
    mkdir -p "$P_HOME" "$P_WORK" "$P_GAMES" "$P_LOGS"

    export HOME="$P_HOME"
    export XDG_DATA_HOME="$P_HOME/.local/share"
    export XDG_CONFIG_HOME="$P_HOME/.config"
    export XDG_CACHE_HOME="$P_HOME/.cache"
    # bin/lutris drops sys.path entries under /home unless this is set; without
    # it a checkout living in a venv under $HOME cannot import its dependencies.
    export LUTRIS_ALLOW_LOCAL_PYTHON_PACKAGES=1
    unset LUTRIS_SKIP_INIT

    P_DATA="$XDG_DATA_HOME/lutris"
    P_CACHE="$XDG_CACHE_HOME/lutris"
    P_CONF="$P_DATA/lutris.conf"
    P_DB="$P_DATA/pga.db"
}

# The manual GUI pass needs one profile that has never been opened, otherwise item 1 of
# the checklist cannot see a real first start: empty library, first runtime download,
# default services. Nothing in the automated checks touches this profile, and the helper
# scripts live next to it rather than inside it.
prepare_first_run_profile() {
    local root="$SANDBOX/first-run"
    mkdir -p "$root/home" "$root/games"

    cat > "$root/games/fake-game.sh" <<'EOF'
#!/bin/sh
echo "fake game running"
printf '%s\n' "$(date +%s)" > "$(dirname "$0")/launched.marker"
EOF
    cat > "$root/games/sleepy.sh" <<'EOF'
#!/bin/sh
echo "fake sleepy game running"
printf '%s\n' "$(date +%s)" > "$(dirname "$0")/launched.marker"
sleep 30
EOF
    chmod +x "$root/games/fake-game.sh" "$root/games/sleepy.sh"
}

# Run the real entry point in the current profile.
# stdout -> $1, stderr -> $1.stderr, exit status -> $RC
lutris_run() {
    local log="$1"; shift
    ( cd "$P_WORK" && timeout "$TIMEOUT" "${DISP[@]+"${DISP[@]}"}" \
        "$PY" "$LUTRIS_ENTRY" "$@" ) >"$log" 2>"$log.stderr"
    RC=$?
    return 0
}

db_query() { # <sql>
    "$PY" - "$P_DB" "$1" <<'PY'
import sqlite3
import sys

with sqlite3.connect(sys.argv[1]) as con:
    for row in con.execute(sys.argv[2]):
        print(row[0])
PY
}

game_count() { # <path-to-json-list>
    "$PY" - "$1" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as json_file:
    print(len(json.load(json_file)))
PY
}

# Add a game to the sandbox profile the same way the client does.
seed_linux_game() { # <slug> <name> [platform]
    "$PY" - "$REPO_ROOT" "$P_GAMES" "$1" "$2" "${3:-}" <<'PY'
import os
import stat
import sys

repo, games_root, slug, name, platform = sys.argv[1:6]
sys.path.insert(0, repo)

from lutris.config import write_game_config
from lutris.database.games import add_game
from lutris.startup import init_lutris

init_lutris()

game_dir = os.path.join(games_root, slug)
os.makedirs(game_dir, exist_ok=True)
exe = os.path.join(game_dir, "fake-game.sh")
marker = os.path.join(game_dir, "launched.marker")

with open(exe, "w", encoding="utf-8") as exe_file:
    exe_file.write("#!/bin/sh\n")
    exe_file.write('echo "fake game running"\n')
    exe_file.write(f'printf "%s\\n" "$(date +%s)" > "{marker}"\n')
os.chmod(exe, os.stat(exe).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

config_path = write_game_config(slug, {"game": {"exe": exe, "args": ""}, "system": {}, "runner": {}})
game_data = {
    "name": name,
    "slug": slug,
    "runner": "linux",
    "executable": exe,
    "directory": game_dir,
    "installed": 1,
    "configpath": config_path,
}
if platform:
    game_data["platform"] = platform

add_game(**game_data)
PY
}

# Recreate the profile an upgrading user has: an old migration_version, a custom
# setting that must survive, and a runner config still using the pre-platform key.
# Seeding one below the newest runs that migration and nothing else, which keeps the
# upgrade offline: migration 13 (migrate_sortname) and 17 (retrieve_discord_appids)
# call the lutris.net API, and lutris/migrations/__init__.py does not catch their
# failures. Broader upgrade coverage comes from --existing-profile, which migrates a
# copy of a real profile.
# The fixture's E5 checks expect the model -> platform rewrite, so they describe
# migration 18. When a migration is added, extend this fixture for the new newest
# migration and move LEGACY_FIXTURE_MIGRATION with it.
LEGACY_FIXTURE_MIGRATION=18
seed_legacy_profile() {
    mkdir -p "$P_DATA/games"
    cat > "$P_CONF" <<EOF
[lutris]
migration_version = $((EXPECTED_MIGRATION_VERSION - 1))
pga_cache_path = $P_ROOT/pga-cache
hide_media = False
EOF

    "$PY" - "$REPO_ROOT" "$P_DATA" "$P_GAMES" <<'PY'
import os
import sys

repo, data_dir, games_root = sys.argv[1:4]
sys.path.insert(0, repo)

from lutris.database import schema
from lutris.database.games import add_game
from lutris.util.yaml import write_yaml_to_file

schema.syncdb()

legacy_dir = os.path.join(games_root, "legacy-emulator")
os.makedirs(legacy_dir, exist_ok=True)
write_yaml_to_file(
    {"game": {"model": "a500", "main_file": os.path.join(legacy_dir, "rom.bin")}},
    os.path.join(data_dir, "games", "legacy-emulator-1.yml"),
)
add_game(
    name="Legacy Emulator Game",
    slug="legacy-emulator",
    runner="fsuae",
    directory=legacy_dir,
    installed=1,
    configpath="legacy-emulator-1",
)
PY

    # A normal game, added before the upgrade, that must keep launching after it
    # (seeded without a platform so the backfill path is exercised too).
    seed_linux_game "smoke-existing-game" "Smoke Existing Game"
}

# ---------------------------------------------------------------------------
# Shared checks
# ---------------------------------------------------------------------------

check_profile_layout() { # <scenario>
    local missing=() dir
    for dir in "$P_DATA" "$P_DATA/games" "$P_DATA/runners" "$P_DATA/runtime" \
               "$P_DATA/banners" "$P_DATA/coverart" \
               "$P_CACHE" "$P_CACHE/installer" "$P_CACHE/shaders" "$P_CACHE/tmp"; do
        [ -d "$dir" ] || missing+=("$dir")
    done
    if [ ${#missing[@]} -eq 0 ]; then
        ok "$1/layout: profile directories created"
    else
        fail "$1/layout: profile directories created" "missing: ${missing[*]}"
    fi
}

check_db_tables() { # <scenario>
    local tables missing=() table
    tables=$(db_query "select name from sqlite_master where type='table'")
    for table in games service_games sources categories games_categories saved_searches; do
        printf '%s\n' "$tables" | grep -qx "$table" || missing+=("$table")
    done
    if [ ${#missing[@]} -eq 0 ]; then
        ok "$1/db: all schema tables present"
    else
        fail "$1/db: all schema tables present" "missing: ${missing[*]}"
    fi
}

check_logs_clean() { # <scenario>
    local bad=() log
    for log in "$P_LOGS"/*.stderr; do
        [ -f "$log" ] || continue
        if grep -q 'Traceback (most recent call last)' "$log"; then
            bad+=("$(basename "$log")")
        fi
    done
    if [ ${#bad[@]} -eq 0 ]; then
        ok "$1/logs: no Python traceback"
    else
        fail "$1/logs: no Python traceback" "found in: ${bad[*]}"
    fi
}

launch_and_check() { # <scenario> <slug> <label>
    local scenario="$1" slug="$2" label="$3"
    local marker="$P_GAMES/$slug/launched.marker"

    lutris_run "$P_LOGS/launch-$slug" "lutris:rungame/$slug"
    expect_eq "$scenario/$label: 'rungame' exits 0" 0 "$RC"
    expect_file "$scenario/$label: the game process actually ran" "$marker"
    expect_eq "$scenario/$label: playtime recorded" "1" \
        "$(db_query "select case when playtime > 0 then 1 else 0 end from games where slug='$slug'")"
    expect_eq "$scenario/$label: lastplayed recorded" "1" \
        "$(db_query "select case when lastplayed > 0 then 1 else 0 end from games where slug='$slug'")"
}

# ---------------------------------------------------------------------------
# Scenario: fresh install
# ---------------------------------------------------------------------------

scenario_fresh() {
    section "Fresh install"
    profile_reset fresh
    local scenario=fresh out gui_rc

    # F1 - version
    lutris_run "$P_LOGS/version" --version
    expect_eq "F1 version: '--version' exits 0" 0 "$RC"
    expect_eq "F1 version: prints lutris-$EXPECTED_VERSION" \
        "lutris-$EXPECTED_VERSION" "$(tail -n 1 "$P_LOGS/version")"

    # F2 - first start on an empty profile
    lutris_run "$P_LOGS/first-start" -l -j
    expect_eq "F2 library: first 'lutris -l -j' exits 0" 0 "$RC"
    expect_eq "F2 library: empty library is []" "[]" \
        "$(tr -d '[:space:]' < "$P_LOGS/first-start")"

    # F3/F4/F5 - profile layout, database, settings
    check_profile_layout "$scenario"
    expect_eq "F4 db: integrity_check" "ok" "$(db_query 'pragma integrity_check')"
    check_db_tables "$scenario"
    out=$(cat "$P_CONF" 2>/dev/null || true)
    expect_contains "F5 settings: migration_version = $EXPECTED_MIGRATION_VERSION" \
        "$out" "migration_version = $EXPECTED_MIGRATION_VERSION"
    expect_contains "F5 settings: default services enabled" "$out" "[services]"

    # F6 - runners. Every JSON runner in the checkout has to appear by name, so a
    # loader regression fails here while adding or removing a runner does not.
    lutris_run "$P_LOGS/runners" --list-runners
    out=$(cat "$P_LOGS/runners" 2>/dev/null || true)
    expect_eq "F6 runners: '--list-runners' exits 0" 0 "$RC"
    expect_contains "F6 runners: built-in 'linux' runner listed" "$out" "linux"
    expect_contains "F6 runners: built-in 'wine' runner listed" "$out" "wine"
    local json name json_count=0 missing=()
    for json in "$REPO_ROOT"/share/lutris/json/*.json; do
        [ -e "$json" ] || continue
        json_count=$((json_count + 1))
        name=$(basename "$json" .json)
        grep -qx "$name" "$P_LOGS/runners" || missing+=("$name")
    done
    if [ ${#missing[@]} -eq 0 ]; then
        ok "F6 runners: all $json_count JSON runners are listed"
    else
        fail "F6 runners: all $json_count JSON runners are listed" "missing: ${missing[*]}"
    fi

    # F7 - add a game, it shows up in the library
    seed_linux_game "smoke-fresh-game" "Smoke Fresh Game" "Linux"
    lutris_run "$P_LOGS/list-game" -l -j
    out=$(cat "$P_LOGS/list-game" 2>/dev/null || true)
    expect_eq "F7 library: listing a one-game library exits 0" 0 "$RC"
    expect_contains "F7 library: added game is listed" "$out" '"slug": "smoke-fresh-game"'
    expect_contains "F7 library: runner is reported" "$out" '"runner": "linux"'
    expect_eq "F7 library: exactly one game" "1" "$(game_count "$P_LOGS/list-game")"

    # F8/F9 - launch it end to end
    launch_and_check "$scenario" "smoke-fresh-game" "launch"

    # F10 - standalone script output
    lutris_run "$P_LOGS/script" -b smoke-fresh-game
    expect_eq "F10 script: '-b <slug>' exits 0" 0 "$RC"
    if [ -x "$P_WORK/smoke-fresh-game.sh" ]; then
        ok "F10 script: '<slug>.sh' written and executable"
    else
        fail "F10 script: '<slug>.sh' written and executable" "not found in $P_WORK"
    fi
    expect_contains "F10 script: contains the game executable" \
        "$(cat "$P_WORK/smoke-fresh-game.sh" 2>/dev/null || true)" "fake-game.sh"

    # F11 - export / import
    mkdir -p "$P_ROOT/export" "$P_ROOT/import"
    lutris_run "$P_LOGS/export" --export smoke-fresh-game --dest "$P_ROOT/export"
    expect_file "F11 export: archive created" "$P_ROOT/export/smoke-fresh-game.tar.xz"
    lutris_run "$P_LOGS/import" --import "$P_ROOT/export/smoke-fresh-game.tar.xz" \
        --dest "$P_ROOT/import"
    expect_contains "F11 import: game re-added" \
        "$(cat "$P_LOGS/import" 2>/dev/null || true)" "Added game with ID"

    # F12 - restarting is idempotent
    lutris_run "$P_LOGS/second-start" -l -j
    expect_eq "F12 restart: second startup exits 0" 0 "$RC"
    expect_eq "F12 restart: integrity_check still ok" "ok" "$(db_query 'pragma integrity_check')"
    expect_eq "F12 restart: library size is still 2 after the import" "2" \
        "$(game_count "$P_LOGS/second-start")"

    # F13 - optional: `lutris -e`
    if [ "$WITH_EXEC" -eq 1 ]; then
        mkdir -p "$P_ROOT/exec"
        lutris_run "$P_LOGS/exec" -e "/bin/sh -c 'printf ok > $P_ROOT/exec/marker'"
        expect_eq "F13 exec: 'lutris -e' returns" 0 "$RC"
        expect_file "F13 exec: the command ran" "$P_ROOT/exec/marker"
    fi

    check_logs_clean "$scenario"

    # F14 - the window starts and stays up
    if [ "$RUN_GUI" -eq 0 ]; then
        skip "F14 gui: window starts and stays up" "--no-gui"
        return
    fi
    ( cd "$P_WORK" && timeout --signal=TERM 15 "${DISP[@]+"${DISP[@]}"}" \
        "$PY" "$LUTRIS_ENTRY" -d ) >"$P_LOGS/gui" 2>"$P_LOGS/gui.stderr"
    gui_rc=$?
    if [ "$gui_rc" -eq 124 ]; then
        ok "F14 gui: window stays up for 15s"
    else
        fail "F14 gui: window stays up for 15s" "the client exited with $gui_rc"
    fi
    if grep -q 'Traceback (most recent call last)' "$P_LOGS/gui.stderr"; then
        fail "F14 gui: startup log is clean" "see $P_LOGS/gui.stderr"
    else
        ok "F14 gui: startup log is clean"
    fi
}

# ---------------------------------------------------------------------------
# Scenario: existing install (upgrade)
# ---------------------------------------------------------------------------

scenario_existing() {
    section "Existing install (upgrade)"
    # The seed below runs only the newest migration, so the fixture and the E5 checks
    # have to describe that one. When they no longer do, say it once, plainly, instead
    # of leaving two unexplained E5 failures behind.
    local newest_migration=$((EXPECTED_MIGRATION_VERSION - 1))
    if [ "$LEGACY_FIXTURE_MIGRATION" -ne "$newest_migration" ]; then
        local fix="the fixture asserts migration $LEGACY_FIXTURE_MIGRATION, the newest is $newest_migration"
        fail "existing/fixture: legacy profile matches the newest migration" \
            "$fix; update seed_legacy_profile() and E5"
    fi
    profile_reset existing
    local scenario=existing out migrated_yml
    local legacy_yml="$P_DATA/games/legacy-emulator-1.yml"

    seed_legacy_profile

    # E1/E2 - first start of the new version on an old profile
    lutris_run "$P_LOGS/upgrade-list" -l -j
    out=$(cat "$P_LOGS/upgrade-list" 2>/dev/null || true)
    expect_eq "E1 upgrade: first start exits 0" 0 "$RC"
    expect_contains "E2 library: emulator game still listed" "$out" '"slug": "legacy-emulator"'
    expect_contains "E2 library: pre-existing game still listed" "$out" '"slug": "smoke-existing-game"'
    expect_eq "E2 library: exactly two games" "2" "$(game_count "$P_LOGS/upgrade-list")"

    # E3/E4 - migrations ran, user settings untouched
    out=$(cat "$P_CONF" 2>/dev/null || true)
    expect_contains "E3 settings: migration_version bumped to $EXPECTED_MIGRATION_VERSION" \
        "$out" "migration_version = $EXPECTED_MIGRATION_VERSION"
    expect_contains "E4 settings: custom pga_cache_path preserved" \
        "$out" "pga_cache_path = $P_ROOT/pga-cache"

    # E5 - the old runner option key is migrated
    out=$(cat "$legacy_yml" 2>/dev/null || true)
    expect_contains "E5 migration: 'model' rewritten as 'platform'" "$out" "platform: a500"
    expect_not_contains "E5 migration: old 'model' key removed" "$out" "model:"

    # E6 - platform backfilled for games that had none
    expect_eq "E6 migration: linux game platform backfilled" "Linux" \
        "$(db_query "select platform from games where slug='smoke-existing-game'")"
    if [ -n "$(db_query "select coalesce(platform, '') from games where slug='legacy-emulator'")" ]; then
        ok "E6 migration: emulator game platform backfilled"
    else
        fail "E6 migration: emulator game platform backfilled" "platform is still empty"
    fi

    # E7 - migrations must not run twice: the file is left alone on the second start
    migrated_yml=$(cksum "$legacy_yml" | cut -d' ' -f1)
    lutris_run "$P_LOGS/upgrade-list-2" -l -j
    expect_eq "E7 upgrade: second start exits 0" 0 "$RC"
    expect_eq "E7 upgrade: migrated config not rewritten on restart" \
        "$migrated_yml" "$(cksum "$legacy_yml" | cut -d' ' -f1)"
    expect_contains "E7 upgrade: migration_version stays current" \
        "$(cat "$P_CONF" 2>/dev/null || true)" \
        "migration_version = $EXPECTED_MIGRATION_VERSION"

    # E8 - a game added before the upgrade still launches
    launch_and_check "$scenario" "smoke-existing-game" "upgrade"

    # E9/E10 - database still sane, no tracebacks
    expect_eq "E9 db: integrity_check" "ok" "$(db_query 'pragma integrity_check')"
    check_db_tables "$scenario"
    check_logs_clean "$scenario"
}

# ---------------------------------------------------------------------------
# Scenario: copy of a real profile (--existing-profile)
# ---------------------------------------------------------------------------

scenario_cloned_profile() {
    if [ -z "$EXISTING_PROFILE" ]; then
        return 0
    fi
    section "Copy of $EXISTING_PROFILE"

    if [ ! -d "$EXISTING_PROFILE" ]; then
        fail "clone: source profile exists" "no such directory: $EXISTING_PROFILE"
        return
    fi
    if [ ! -f "$EXISTING_PROFILE/pga.db" ]; then
        fail "clone: source profile has a database" "no pga.db in $EXISTING_PROFILE"
        return
    fi

    profile_reset clone
    mkdir -p "$P_DATA/games" "$P_DATA/runners"

    local source_db_sum
    source_db_sum=$(cksum "$EXISTING_PROFILE/pga.db" | cut -d' ' -f1)

    cp -a "$EXISTING_PROFILE/pga.db" "$P_DATA/" || fail "clone: copy pga.db"

    # lutris.conf, games/ and runners/ live in ~/.config/lutris when that folder exists,
    # and in the data directory when it does not (settings.py: CONFIG_DIR). When both
    # exist the config folder wins, which is what the client does as well.
    local config_source="$EXISTING_PROFILE"
    local legacy_config="$EXISTING_PROFILE/../../../.config/lutris"
    if [ -d "$legacy_config" ]; then
        config_source="$(cd "$legacy_config" && pwd)"
        printf '  info: using the ~/.config/lutris layout of this profile\n' >&2
    fi
    if [ -d "$config_source/games" ]; then
        cp -a "$config_source/games/." "$P_DATA/games/" || fail "clone: copy games/"
    fi
    # Runner .yml files only: the data directory also holds the downloaded Wine and
    # Proton builds, which are gigabytes and irrelevant to this check.
    if [ -d "$config_source/runners" ]; then
        find "$config_source/runners" -maxdepth 1 -name '*.yml' \
            -exec cp -a {} "$P_DATA/runners/" \; 2>/dev/null
    fi

    local source_conf=""
    if [ -f "$config_source/lutris.conf" ]; then
        source_conf="$config_source/lutris.conf"
    fi

    # A copied lutris.conf may redirect the database or the directories to the real ones
    # (lutris/settings.py and lutris/cache.py), which would make the sandboxed client
    # open, and migrate, the user's library. Drop those keys from the copy.
    if [ -n "$source_conf" ]; then
        "$PY" - "$source_conf" "$P_CONF" <<'PY'
import configparser
import sys

source, destination = sys.argv[1:3]
REDIRECTING_KEYS = ("pga_path", "cache_dir", "runner_dir", "runtime_dir", "pga_cache_path")

parser = configparser.ConfigParser(interpolation=None)
parser.read(source)
if parser.has_section("lutris"):
    for key in REDIRECTING_KEYS:
        if parser.has_option("lutris", key):
            print(
                "  info: dropped '%s = %s' from the copied lutris.conf" % (key, parser.get("lutris", key)),
                file=sys.stderr,
            )
            parser.remove_option("lutris", key)
with open(destination, "w", encoding="utf-8") as conf_file:
    parser.write(conf_file)
PY
    fi

    local before
    before=$(db_query "select count(*) from games" 2>/dev/null || echo "")
    if [ -n "$before" ]; then
        ok "clone: profile copied ($before games)"
    else
        fail "clone: profile copied" "could not count the games in the copied database"
    fi

    lutris_run "$P_LOGS/clone-list" -l -j
    expect_eq "clone: 'lutris -l -j' exits 0" 0 "$RC"
    if [ -n "$before" ]; then
        expect_eq "clone: game count unchanged after upgrade" "$before" \
            "$(db_query 'select count(*) from games' 2>/dev/null)"
    else
        skip "clone: game count unchanged after upgrade" "the copied database could not be counted"
    fi
    expect_eq "clone: integrity_check" "ok" "$(db_query 'pragma integrity_check')"
    expect_contains "clone: migration_version current" \
        "$(cat "$P_CONF" 2>/dev/null || true)" "migration_version = $EXPECTED_MIGRATION_VERSION"
    expect_eq "clone: the source database was not modified" \
        "$source_db_sum" "$(cksum "$EXISTING_PROFILE/pga.db" | cut -d' ' -f1)"
    check_logs_clean "clone"
}

# ---------------------------------------------------------------------------
# Manual GUI pass
# ---------------------------------------------------------------------------

# With --keep the sandbox survives, so the client can be opened with the test
# profiles the checks just built. Print that ready to paste.
print_profile_launchers() {
    if [ "$KEEP" -ne 1 ]; then
        return 0
    fi

    cat <<EOF

To do the GUI pass, open the client with one of the profiles:

  SMOKE=$SANDBOX
  launch() {
      env HOME="\$SMOKE/\$1/home" \\
          XDG_DATA_HOME="\$SMOKE/\$1/home/.local/share" \\
          XDG_CONFIG_HOME="\$SMOKE/\$1/home/.config" \\
          XDG_CACHE_HOME="\$SMOKE/\$1/home/.cache" \\
          LUTRIS_ALLOW_LOCAL_PYTHON_PACKAGES=1 \\
          dbus-run-session -- "$PY" "$LUTRIS_ENTRY" -d
  }
  launch first-run  # never opened: item 1 needs a real first start
  launch fresh      # automated profile: one seeded game
  launch existing   # automated profile: upgraded, two seeded games
EOF

    if [ -n "$EXISTING_PROFILE" ]; then
        printf '  launch clone      # copy of %s\n' "$EXISTING_PROFILE"
    fi

    cat <<EOF

Quit the client before opening another profile: Lutris is single-instance, and the
private bus above only belongs to that one client.
Test games: \$SMOKE/first-run/games/{fake-game.sh,sleepy.sh}
Step-by-step checklist: docs/manual-gui-checklist.rst
EOF
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

printf '%sLutris release smoke test%s\n' "$C_BOLD" "$C_RESET"
printf '  repository : %s\n' "$REPO_ROOT"
printf '  version    : %s\n' "$EXPECTED_VERSION"
printf '  python     : %s\n' "$PY"
printf '  sandbox    : %s\n' "$SANDBOX"
printf '  display    : %s\n' "$DISPLAY_NOTE"

if [ "$KEEP" -eq 1 ]; then
    prepare_first_run_profile
fi

if [ "$SCENARIO" = "both" ] || [ "$SCENARIO" = "fresh" ]; then
    scenario_fresh
fi
if [ "$SCENARIO" = "both" ] || [ "$SCENARIO" = "existing" ]; then
    scenario_existing
fi
scenario_cloned_profile

section "Summary"
printf '  %d passed, %d failed, %d skipped\n' "$PASS" "$FAIL" "$SKIP"

if [ "$FAIL" -gt 0 ]; then
    printf '\nFailed checks:\n'
    for name in ${FAILURES[@]+"${FAILURES[@]}"}; do
        printf '  - %s\n' "$name"
    done
    printf '\nPer-command logs and captured stderr are in %s\n' "$SANDBOX"
    printf 'Step-by-step GUI checks: docs/manual-gui-checklist.rst\n'
    print_profile_launchers
    exit 1
fi

cat <<'EOF'

For the release process (docs/release-guidelines.rst):

  required       this script passing
  recommended    part A of docs/manual-gui-checklist.rst
                 about 10 min, sandbox, items 1, 3, 4, 5, 6, 10
  when affected  part B of docs/manual-gui-checklist.rst
                 only when the release touches installers, services or library
                 views; about 15 min, own profile after a backup, items 2, 7, 8, 9

If part B does not apply, say so in the release pull request.
EOF

print_profile_launchers
exit 0
