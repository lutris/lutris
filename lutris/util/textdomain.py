"""Binding of Lutris's gettext message catalogs.

This module is import-order sensitive and deliberately isolated.

bind_text_domain() has to run before any module that translates strings while it is
being imported, and a great many of them do: the option tables in lutris.sysoptions
alone resolve well over a hundred strings at import time. `from gettext import gettext
as _` captures the function, not the domain, so a string translated before the domain
is bound is resolved against the default "messages" domain and comes out untranslated
for the life of the process.

Two rules follow, and breaking either one silently untranslates part of the UI:

  * Nothing here may use _() or import gettext's translation functions.
  * Nothing here may import the rest of Lutris at module level. Importing
    lutris.config, lutris.settings or lutris.util.i18n pulls in that cascade.

Translations are also cosmetic, and this runs before Lutris can report anything
properly, so nothing here may stop Lutris from starting. Every failure reports to
stderr and leaves the interface in English.

tests/util/_test_textdomain.py enforces all of this.
"""

import gettext
import locale
import os
import shutil
import subprocess
import sys
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

# msgfmt takes milliseconds per catalog; this only bounds a hung or wedged process,
# which would otherwise hang startup before there is any window to report it in.
COMPILE_TIMEOUT_SECONDS = 60
CATALOG_DIR = Path(__file__).resolve().parents[1] / "locale"


def bind_text_domain() -> None:
    """Point gettext at Lutris's message catalogs.

    Use precompiled catalogs if bundled (as in the Flatpak). Otherwise compile
    the packaged .po files into the user's cache if gettext is installed.

    Never raises: a broken or partial install leaves Lutris running in English.
    """
    try:
        locale_dir: Path | None = CATALOG_DIR
        if not any(locale_dir.glob("*/LC_MESSAGES/lutris.mo")):
            locale_dir = compile_source_catalogs(CATALOG_DIR)

        if not locale_dir:
            return

        locale.bindtextdomain("lutris", str(locale_dir))
        gettext.bindtextdomain("lutris", str(locale_dir))
        locale.textdomain("lutris")
        gettext.textdomain("lutris")
    except Exception as ex:
        # Too early for the logger, and the terminal is where this is wanted anyway.
        sys.stderr.write("Couldn't set up translations, the interface will be in English.\nError: %s\n" % ex)


def compile_source_catalogs(source_dir: Path) -> Path | None:
    """Compile bundled .po files into a cache and return the locale directory to bind.

    Returns None if the catalogs can't be built. Only catalogs older than their .po
    file are rebuilt, so this costs a few stat calls once they are built.

    Each package location gets a separate directory so an editable install never
    reuses catalogs built from another checkout or installation.
    """
    po_paths = sorted(source_dir.glob("*.po"))
    if not po_paths:
        return None

    source_key = sha256(os.fsencode(source_dir.resolve())).hexdigest()
    cache_home = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    locale_dir = cache_home / "lutris" / "locale" / source_key
    msgfmt = shutil.which("msgfmt")
    if not msgfmt:
        if any(locale_dir.glob("*/LC_MESSAGES/lutris.mo")):
            return locale_dir
        sys.stderr.write("msgfmt not found, translations won't work. Install gettext to enable them.\n")
        return None

    try:
        locale_dir.mkdir(parents=True, exist_ok=True)
    except OSError as ex:
        sys.stderr.write("Couldn't build translations in %s: %s\n" % (locale_dir, ex))
        return None

    for po_path in po_paths:
        mo_path = locale_dir / po_path.stem / "LC_MESSAGES" / "lutris.mo"
        try:
            if mo_path.is_file() and mo_path.stat().st_mtime_ns >= po_path.stat().st_mtime_ns:
                continue
            mo_path.parent.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(dir=mo_path.parent) as temp_dir:
                output = Path(temp_dir) / mo_path.name
                compiled = subprocess.run(
                    [msgfmt, po_path, "-o", output],
                    capture_output=True,
                    text=True,
                    errors="replace",
                    timeout=COMPILE_TIMEOUT_SECONDS,
                )
                if compiled.returncode:
                    sys.stderr.write("Couldn't compile %s:\n%s" % (po_path, compiled.stderr))
                else:
                    output.replace(mo_path)
        except (OSError, subprocess.SubprocessError) as ex:
            sys.stderr.write("Couldn't build %s: %s\n" % (po_path, ex))

    return locale_dir if any(locale_dir.glob("*/LC_MESSAGES/lutris.mo")) else None
