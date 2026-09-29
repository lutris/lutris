"""Bridge module for invoking heroic-gogdl.

gogdl is a tool from the Heroic Games Launcher project that downloads
GOG games directly from GOG's depot/CDN system. It is shipped as a
Lutris runtime component — the pre-built binary is downloaded and
updated via the standard runtime update system.

This module handles:
- Locating the gogdl binary from the runtime directory
- Auth token conversion between Lutris and gogdl formats
- Subprocess invocation with progress parsing
- Reading back refreshed tokens after gogdl operations
"""

import json
import os
import re
import subprocess
import threading
import time

from lutris import settings
from lutris.util.log import logger

# Where the runtime system installs gogdl
GOGDL_DIR = os.path.join(settings.RUNTIME_DIR, "gogdl")

# Auth config file written for gogdl
GOGDL_AUTH_PATH = os.path.join(settings.CACHE_DIR, "gogdl-auth.json")

# GOG client ID (same for both Lutris and gogdl)
GOG_CLIENT_ID = "46899977096215655"

# Regex to parse gogdl progress output
PROGRESS_RE = re.compile(
    r"= Progress: (?P<percent>[\d.]+) (?P<written>\d+)/(?P<total>\d+),"
    r" Running for: (?P<elapsed>\S+), ETA: (?P<eta>\S+)"
)
SPEED_RE = re.compile(r"\+ Download\t- (?P<raw_speed>[\d.]+) MiB/s \(raw\)")


def _get_gogdl_binary():
    """Return the path to the gogdl binary from the runtime directory."""
    binary = os.path.join(GOGDL_DIR, "gogdl")
    if os.path.isfile(binary) and os.access(binary, os.X_OK):
        return binary
    raise FileNotFoundError(
        "gogdl runtime component not found. "
        "Please update your Lutris runtime (Preferences > Global Options > Update Runtime)."
    )


def _write_auth_config():
    """Read Lutris's GOG token and write it in gogdl's expected format."""
    from lutris.services.gog import GOGService

    service = GOGService()
    token = service.load_token()

    token_age = service.get_token_age()
    login_time = time.time() - token_age

    if token_age > 2600:
        service.request_token(refresh_token=token["refresh_token"])
        token = service.load_token()
        login_time = time.time()

    gogdl_auth = {
        GOG_CLIENT_ID: {
            "access_token": token["access_token"],
            "refresh_token": token["refresh_token"],
            "expires_in": token.get("expires_in", 3600),
            "loginTime": login_time,
        }
    }

    os.makedirs(os.path.dirname(GOGDL_AUTH_PATH), exist_ok=True)
    with open(GOGDL_AUTH_PATH, "w", encoding="utf-8") as f:
        json.dump(gogdl_auth, f)

    return GOGDL_AUTH_PATH


def _read_back_token():
    """After a gogdl invocation, check if the token was refreshed and
    update Lutris's token file accordingly."""
    if not os.path.exists(GOGDL_AUTH_PATH):
        return

    with open(GOGDL_AUTH_PATH, encoding="utf-8") as f:
        gogdl_auth = json.load(f)

    creds = gogdl_auth.get(GOG_CLIENT_ID)
    if not creds:
        return

    from lutris.services.gog import GOGService

    service = GOGService()
    try:
        current_token = service.load_token()
    except Exception:
        return

    if creds.get("access_token") != current_token.get("access_token"):
        updated_token = dict(current_token)
        updated_token["access_token"] = creds["access_token"]
        updated_token["refresh_token"] = creds["refresh_token"]
        updated_token["expires_in"] = creds.get("expires_in", 3600)
        with open(service.token_path, "w", encoding="utf-8") as f:
            json.dump(updated_token, f)
        logger.info("Updated Lutris GOG token from gogdl refresh")


def _build_command(command, game_id, path, platform="windows", lang=None, dlcs=None):
    """Build the gogdl command line arguments."""
    binary = _get_gogdl_binary()
    auth_path = _write_auth_config()

    cmd = [
        binary,
        "--auth-config-path",
        auth_path,
        command,
        str(game_id),
    ]

    if command != "info":
        cmd.extend(["--path", path])

    cmd.extend(["--platform", platform])

    if lang:
        cmd.extend(["--lang", lang])

    if dlcs is True:
        cmd.append("--with-dlcs")
    elif dlcs is False:
        cmd.append("--skip-dlcs")
    elif isinstance(dlcs, str) and dlcs:
        # `--dlcs <ids>` only filters which DLCs to include; gogdl still gates
        # on `--with-dlcs` before consulting ownership, so both must be passed.
        cmd.extend(["--with-dlcs", "--dlcs", dlcs])

    return cmd


class GogdlProgress:
    """Tracks the latest progress state from gogdl output."""

    def __init__(self):
        self.percent = 0.0
        self.written = 0
        self.total = 0
        self.speed_mib = 0.0
        self.eta = ""

    def parse_line(self, line):
        """Parse a single line of gogdl output. Returns True if progress was updated."""
        match = PROGRESS_RE.search(line)
        if match:
            self.percent = float(match.group("percent"))
            self.written = int(match.group("written"))
            self.total = int(match.group("total"))
            self.eta = match.group("eta")
            return True

        match = SPEED_RE.search(line)
        if match:
            self.speed_mib = float(match.group("raw_speed"))
            return True

        return False


def run_gogdl(command, game_id, path, platform="windows", lang=None, dlcs=None, progress_callback=None):
    """Run a gogdl command as a subprocess.

    Args:
        command: "download", "update", "repair", or "info"
        game_id: GOG product ID
        path: Installation path
        platform: "windows" or "linux"
        lang: Language code
        dlcs: True (all), False (none), or comma-separated DLC ID string
        progress_callback: Called with (GogdlProgress) on progress updates
    Returns:
        For "info": parsed JSON dict
        For other commands: None on success
    Raises:
        FileNotFoundError: if gogdl runtime component is not installed
        RuntimeError: if gogdl fails (with gogdl's error output as the message)
    """
    cmd = _build_command(command, game_id, path, platform, lang, dlcs)

    env = os.environ.copy()
    config_path = os.path.join(settings.CACHE_DIR, "gogdl")
    os.makedirs(config_path, exist_ok=True)
    env["GOGDL_CONFIG_PATH"] = config_path

    logger.info("Running gogdl: %s", " ".join(cmd))

    if command == "info":
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=60)
        _read_back_token()
        if result.returncode != 0:
            error_msg = result.stderr.strip() or "gogdl info failed (exit code %d)" % result.returncode
            logger.error("gogdl info failed: %s", error_msg)
            raise RuntimeError(error_msg)
        return json.loads(result.stdout)

    # For download/update/repair, stream stderr for progress
    progress = GogdlProgress()
    error_lines = []

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)

    def read_stderr():
        for line in process.stderr:
            line = line.rstrip()
            if not line:
                continue
            logger.debug("[gogdl stderr] %s", line)
            if progress.parse_line(line) and progress_callback:
                progress_callback(progress)
            if "ERROR" in line:
                error_lines.append(line)

    def read_stdout():
        for line in process.stdout:
            line = line.rstrip()
            if not line:
                continue
            logger.debug("[gogdl stdout] %s", line)
            if progress.parse_line(line) and progress_callback:
                progress_callback(progress)

    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    stdout_thread = threading.Thread(target=read_stdout, daemon=True)
    stderr_thread.start()
    stdout_thread.start()

    process.wait()
    stderr_thread.join(timeout=5)
    stdout_thread.join(timeout=5)

    _read_back_token()

    if process.returncode != 0:
        if error_lines:
            error_msg = "\n".join(error_lines)
        else:
            error_msg = "gogdl %s failed (exit code %d)" % (command, process.returncode)
        logger.error("gogdl %s failed: %s", command, error_msg)
        raise RuntimeError(error_msg)


LINUX_MANIFEST_FILENAME = ".gogdl-linux-manifest"


def _find_manifest(game_id, install_dir, runner):
    """Return the on-disk path to the gogdl manifest for this install, or None.

    The Linux native download manager writes `.gogdl-linux-manifest` inside
    the install directory (nested one level under an installDirectory
    subfolder named after the game's display name), while the v2 (Windows)
    manager writes to a shared cache dir keyed by game id alone."""
    if runner == "linux":
        if not install_dir or not os.path.isdir(install_dir):
            return None
        direct = os.path.join(install_dir, LINUX_MANIFEST_FILENAME)
        if os.path.exists(direct):
            return direct
        for entry in os.listdir(install_dir):
            candidate = os.path.join(install_dir, entry, LINUX_MANIFEST_FILENAME)
            if os.path.exists(candidate):
                return candidate
        return None
    win_manifest = os.path.join(settings.CACHE_DIR, "gogdl", "heroic_gogdl", "manifests", str(game_id))
    return win_manifest if os.path.exists(win_manifest) else None


def is_depot_installed(game_id, install_dir, runner):
    """Check if a game was installed via gogdl depot. Both install_dir and
    runner are required: Linux native installs can only be detected from the
    install directory, while Windows installs are tracked by game id."""
    return _find_manifest(game_id, install_dir, runner) is not None


def clear_stale_manifest(game_id, install_dir, runner):
    """Remove any gogdl manifest associated with this install.

    Used before a fresh `download` to ensure gogdl doesn't skip work because
    a previous interrupted install left a manifest behind."""
    manifest = _find_manifest(game_id, install_dir, runner)
    if manifest:
        os.remove(manifest)
        logger.debug("Cleared stale gogdl manifest at %s", manifest)
