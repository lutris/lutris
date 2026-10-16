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
import glob
import locale
import os
import shutil
import subprocess
import sys

# msgfmt takes milliseconds per catalog; this only bounds a hung or wedged process,
# which would otherwise hang startup before there is any window to report it in.
COMPILE_TIMEOUT_SECONDS = 60


def bind_text_domain(source_path: str | None = None) -> None:
    """Point gettext at Lutris's message catalogs.

    A meson install generates optional_settings holding the installed locale directory.
    A source tree has no such module and no compiled catalogs, so the .po files are
    compiled into po/dev_locale_cache instead, which lets translators test their work
    with LANGUAGE= without installing. Pass the root of the source tree as source_path.

    Never raises: a broken or partial install leaves Lutris running in English.
    """
    try:
        try:
            # optional_settings does not exist if you don't use the meson build system
            from lutris import optional_settings  # type: ignore

            # A truncated optional_settings.py from a botched install raises
            # AttributeError here, which the handler below reports and survives.
            locale_dir = optional_settings.LOCALE_DIR
        except ImportError:
            locale_dir = compile_source_catalogs(source_path) if source_path else None

        if not locale_dir:
            return

        locale.bindtextdomain("lutris", locale_dir)
        gettext.bindtextdomain("lutris", locale_dir)
        locale.textdomain("lutris")
        gettext.textdomain("lutris")
    except Exception as ex:
        # Too early for the logger, and the terminal is where this is wanted anyway.
        sys.stderr.write("Couldn't set up translations, the interface will be in English.\nError: %s\n" % ex)


def compile_source_catalogs(source_path: str) -> str | None:
    """Compile po/*.po into po/dev_locale_cache and return the locale directory to bind.

    Returns None if the catalogs can't be built. Only catalogs older than their .po
    file are rebuilt, so this costs a few stat calls once they are built.

    The output belongs to the checkout it was built from, so it lives in the source
    tree (gitignored) rather than in ~/.cache: a shared cache would compare one
    checkout's .mo against another's .po and silently serve the wrong translations.
    """
    msgfmt = shutil.which("msgfmt")
    if not msgfmt:
        sys.stderr.write("msgfmt not found, translations won't work. Install gettext to enable them.\n")
        return None

    po_paths = sorted(glob.glob(os.path.join(source_path, "po", "*.po")))
    if not po_paths:
        return None

    locale_dir = os.path.join(source_path, "po", "dev_locale_cache")
    try:
        os.makedirs(locale_dir, exist_ok=True)
    except OSError as ex:
        # A source tree we can't write to; reported once rather than per catalog.
        sys.stderr.write("Couldn't build translations in %s: %s\n" % (locale_dir, ex))
        return None

    for po_path in po_paths:
        language = os.path.splitext(os.path.basename(po_path))[0]
        mo_path = os.path.join(locale_dir, language, "LC_MESSAGES", "lutris.mo")
        try:
            if os.path.exists(mo_path) and os.path.getmtime(mo_path) >= os.path.getmtime(po_path):
                continue
            os.makedirs(os.path.dirname(mo_path), exist_ok=True)
            # errors="replace": msgfmt reports in the user's locale, which need not
            # decode cleanly, and a mangled message is better than no startup.
            compiled = subprocess.run(
                [msgfmt, po_path, "-o", mo_path],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=COMPILE_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError) as ex:
            # One unusable catalog leaves that language in English; keep going so a
            # single bad file can't cost every other language its translation.
            sys.stderr.write("Couldn't build %s: %s\n" % (po_path, ex))
            continue

        if compiled.returncode:
            # A broken catalog leaves that one language untranslated; report it, as
            # whoever is editing it is the one who needs to know.
            sys.stderr.write("Couldn't compile %s:\n%s" % (po_path, compiled.stderr))

    # Nothing usable built means nothing worth binding, so the caller leaves the
    # default domain alone rather than pointing it at an empty directory.
    if not glob.glob(os.path.join(locale_dir, "*", "LC_MESSAGES", "lutris.mo")):
        return None
    return locale_dir
