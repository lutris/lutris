"""Checks that translations of Pango markup strings are still valid markup."""

import gettext
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

import gi

gi.require_version("Pango", "1.0")
from gi.repository import GLib, Pango

PO_DIR = pathlib.Path(__file__).parents[1] / "po"

# GtkLabel takes <a href> links out of the markup itself; Pango would reject them.
# Only well-formed links are unwrapped, so a stray tag or a broken href still fails.
HREF_CHAR = r"(?:[^\"'<>&]|&(?:amp|lt|gt|quot|apos);|&#[0-9]+;|&#x[0-9a-fA-F]+;)"
LINK = re.compile(rf"""<a href=(["']){HREF_CHAR}*\1>(.*?)</a>""", re.DOTALL)


def is_valid_markup(text):
    try:
        Pango.parse_markup(LINK.sub(r"\2", text), -1, "\0")
    except GLib.Error:
        return False
    return True


def is_markup(msgid):
    return ("<" in msgid or "&" in msgid) and is_valid_markup(msgid)


@unittest.skipIf(shutil.which("msgfmt") is None, "gettext is not installed")
class TestTranslatedMarkup(unittest.TestCase):
    maxDiff = None

    def test_translated_markup_parses(self):
        """GTK shows an empty label rather than the English text when set_markup() fails to parse."""
        broken = []
        with tempfile.TemporaryDirectory() as tmp:
            for po_path in sorted(PO_DIR.glob("*.po")):
                mo_path = os.path.join(tmp, po_path.stem + ".mo")
                # Compiling skips fuzzy entries, which Lutris never shows either.
                subprocess.run(["msgfmt", str(po_path), "-o", mo_path], check=True, capture_output=True)
                with open(mo_path, "rb") as mo_file:
                    catalog = gettext.GNUTranslations(mo_file)._catalog
                for key, msgstr in catalog.items():
                    msgid = key[0] if isinstance(key, tuple) else key
                    msgid = msgid.rpartition("\x04")[2]
                    if msgstr and is_markup(msgid) and not is_valid_markup(msgstr):
                        broken.append(f"{po_path.name}: {msgstr!r}")
        self.assertEqual(broken, [])
