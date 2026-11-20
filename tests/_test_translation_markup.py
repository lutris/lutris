"""Check that translated rich text preserves well-formed markup."""

import gettext
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest
from xml.etree import ElementTree

PO_DIR = pathlib.Path(__file__).parents[1] / "po"

VOID_TAGS = re.compile(r"<(br|hr|img)(\s[^<>]*?)?(?<!/)>", re.IGNORECASE)


def is_valid_markup(text: str) -> bool:
    try:
        ElementTree.fromstring(f"<qt>{VOID_TAGS.sub(r'<\1\2/>', text)}</qt>")
    except ElementTree.ParseError:
        return False
    return True


def is_markup(msgid: str) -> bool:
    return ("<" in msgid or "&" in msgid) and is_valid_markup(msgid)


@unittest.skipIf(shutil.which("msgfmt") is None, "gettext is not installed")
class TestTranslatedMarkup(unittest.TestCase):
    maxDiff = None

    def test_translated_markup_parses(self) -> None:
        broken = []
        with tempfile.TemporaryDirectory() as tmp:
            for po_path in sorted(PO_DIR.glob("*.po")):
                mo_path = os.path.join(tmp, po_path.stem + ".mo")
                # Compiling skips fuzzy entries, which Lutris never shows either
                subprocess.run(["msgfmt", str(po_path), "-o", mo_path], check=True, capture_output=True)
                with open(mo_path, "rb") as mo_file:
                    catalog = gettext.GNUTranslations(mo_file)._catalog
                for key, msgstr in catalog.items():
                    msgid = key[0] if isinstance(key, tuple) else key
                    msgid = msgid.rpartition("\x04")[2]
                    if msgstr and is_markup(msgid) and not is_valid_markup(msgstr):
                        broken.append(f"{po_path.name}: {msgstr!r}")
        self.assertEqual(broken, [])
