"""Guards the import-order constraints documented in lutris.util.textdomain."""

import ast
import contextlib
import gettext
import io
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from lutris.util import textdomain

MODULE_PATH = pathlib.Path(textdomain.__file__)

# Importing any of these drags in the cascade of modules that translate strings as
# they import, which must not happen before the text domain is bound.
FORBIDDEN_IMPORTS = ("lutris.config", "lutris.settings", "lutris.sysoptions", "lutris.util.i18n")


class TestImportIsolation(unittest.TestCase):
    """lutris.util.textdomain must stay importable before the domain is bound."""

    def test_import_pulls_in_nothing_heavy(self):
        """A fresh import must not load any module that translates at import time."""
        script = (
            "import sys, gettext\n"
            "fired = []\n"
            "orig = gettext.gettext\n"
            "gettext.gettext = lambda m: (fired.append(m), orig(m))[1]\n"
            "import lutris.util.textdomain\n"
            "print(len(fired))\n"
            "print(' '.join(sorted(m for m in sys.modules if m.startswith('lutris'))))\n"
        )
        completed = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=True,
            cwd=MODULE_PATH.parents[2],
        )
        translated, loaded = completed.stdout.splitlines()

        self.assertEqual(int(translated), 0, "strings were translated before the domain was bound")
        self.assertEqual(loaded.split(), ["lutris", "lutris.util", "lutris.util.textdomain"])

    def test_no_module_level_lutris_imports(self):
        """The forbidden imports may appear inside functions, never at module level."""
        tree = ast.parse(MODULE_PATH.read_text())
        for node in tree.body:
            for name in ast.walk(node):
                if isinstance(name, ast.ImportFrom) and name.module:
                    self.assertNotIn(name.module, FORBIDDEN_IMPORTS)
                if isinstance(name, ast.Import):
                    for alias in name.names:
                        self.assertNotIn(alias.name, FORBIDDEN_IMPORTS)

    def test_does_not_translate_anything(self):
        """No _() calls, and no import of gettext's translation functions."""
        source = MODULE_PATH.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotEqual(node.func.id, "_", "textdomain.py must not translate strings")
            if isinstance(node, ast.ImportFrom) and node.module == "gettext":
                names = [alias.name for alias in node.names]
                self.assertNotIn("gettext", names)


@unittest.skipIf(shutil.which("msgfmt") is None, "gettext is not installed")
class TestCompileSourceCatalogs(unittest.TestCase):
    def setUp(self):
        self.source = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.source, "po"))

    def write_catalog(self, name, body):
        path = os.path.join(self.source, "po", name)
        pathlib.Path(path).write_text('msgid ""\nmsgstr "Content-Type: text/plain; charset=UTF-8\\n"\n\n' + body)
        return path

    def test_compiles_catalogs(self):
        self.write_catalog("fr.po", 'msgid "Change"\nmsgstr "Modifier"\n')
        locale_dir = textdomain.compile_source_catalogs(self.source)
        self.assertTrue(os.path.exists(os.path.join(locale_dir, "fr", "LC_MESSAGES", "lutris.mo")))

    def test_builds_inside_the_source_tree(self):
        """The catalogs belong to their checkout, so they must not land in a shared cache."""
        self.write_catalog("fr.po", 'msgid "Change"\nmsgstr "Modifier"\n')
        locale_dir = textdomain.compile_source_catalogs(self.source)
        self.assertEqual(locale_dir, os.path.join(self.source, "po", "dev_locale_cache"))

    def test_checkouts_do_not_share_catalogs(self):
        """Two checkouts of differing age must each get their own translation."""
        older = self.write_catalog("fr.po", 'msgid "Change"\nmsgstr "FROM-A"\n')
        os.utime(older, (1000, 1000))

        other_source = tempfile.mkdtemp()
        os.makedirs(os.path.join(other_source, "po"))
        pathlib.Path(os.path.join(other_source, "po", "fr.po")).write_text(
            'msgid ""\nmsgstr "Content-Type: text/plain; charset=UTF-8\\n"\n\nmsgid "Change"\nmsgstr "FROM-B"\n'
        )

        textdomain.compile_source_catalogs(other_source)
        locale_dir = textdomain.compile_source_catalogs(self.source)
        translation = gettext.translation("lutris", localedir=locale_dir, languages=["fr"])
        self.assertEqual(translation.gettext("Change"), "FROM-A")

    @unittest.skipIf(os.geteuid() == 0, "root ignores directory permissions")
    def test_unwritable_source_tree_is_not_fatal(self):
        self.write_catalog("fr.po", 'msgid "Change"\nmsgstr "Modifier"\n')
        os.chmod(os.path.join(self.source, "po"), 0o500)
        try:
            reported = io.StringIO()
            with contextlib.redirect_stderr(reported):
                self.assertIsNone(textdomain.compile_source_catalogs(self.source))
            self.assertIn("Couldn't build translations", reported.getvalue())
        finally:
            os.chmod(os.path.join(self.source, "po"), 0o700)

    def test_skips_unchanged_catalogs(self):
        self.write_catalog("fr.po", 'msgid "Change"\nmsgstr "Modifier"\n')
        mo_path = os.path.join(textdomain.compile_source_catalogs(self.source), "fr", "LC_MESSAGES", "lutris.mo")
        compiled_at = os.path.getmtime(mo_path)

        textdomain.compile_source_catalogs(self.source)
        self.assertEqual(os.path.getmtime(mo_path), compiled_at)

    def test_recompiles_edited_catalogs(self):
        po_path = self.write_catalog("fr.po", 'msgid "Change"\nmsgstr "Modifier"\n')
        mo_path = os.path.join(textdomain.compile_source_catalogs(self.source), "fr", "LC_MESSAGES", "lutris.mo")
        compiled_at = os.path.getmtime(mo_path)

        os.utime(po_path, (compiled_at + 10, compiled_at + 10))
        textdomain.compile_source_catalogs(self.source)
        self.assertGreater(os.path.getmtime(mo_path), compiled_at)

    def test_broken_catalog_does_not_stop_the_others(self):
        self.write_catalog("broken.po", 'msgid "Change"\nmsgstr "unterminated\n')
        self.write_catalog("fr.po", 'msgid "Change"\nmsgstr "Modifier"\n')
        reported = io.StringIO()
        with contextlib.redirect_stderr(reported):
            locale_dir = textdomain.compile_source_catalogs(self.source)
        self.assertIn("broken.po", reported.getvalue())
        self.assertTrue(os.path.exists(os.path.join(locale_dir, "fr", "LC_MESSAGES", "lutris.mo")))
        self.assertFalse(os.path.exists(os.path.join(locale_dir, "broken", "LC_MESSAGES", "lutris.mo")))

    def test_returns_none_without_catalogs(self):
        self.assertIsNone(textdomain.compile_source_catalogs(self.source))


class TestNeverFatal(unittest.TestCase):
    """Translation setup must never stop Lutris from starting."""

    def run_entry_point(self, extra_env=None):
        """Run bin/lutris far enough to bind the domain, and report how it went."""
        # bin/lutris drops /home* from sys.path unless this is set, which hides gi
        # whenever it comes from a virtualenv under /home, as it does on CI.
        env = dict(os.environ, LANGUAGE="fr", LUTRIS_ALLOW_LOCAL_PYTHON_PACKAGES="1")
        env.update(extra_env or {})
        root = MODULE_PATH.parents[2]
        return subprocess.run(
            [sys.executable, str(root / "bin" / "lutris"), "--help"],
            capture_output=True,
            text=True,
            env=env,
            cwd=root,
        )

    def test_truncated_optional_settings_is_not_fatal(self):
        """A botched install can leave optional_settings.py without LOCALE_DIR."""
        generated = MODULE_PATH.parents[1] / "optional_settings.py"
        self.assertFalse(generated.exists(), "this tree has a generated optional_settings.py")
        generated.write_text('"""Truncated by a botched install"""\n')
        try:
            completed = self.run_entry_point()
        finally:
            generated.unlink()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Run a game directly", completed.stdout)
        self.assertIn("Couldn't set up translations", completed.stderr)

    def test_missing_msgfmt_is_not_fatal(self):
        """gettext may simply not be installed."""
        completed = self.run_entry_point({"PATH": ""})
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("msgfmt not found", completed.stderr)
        self.assertIn("Run a game directly", completed.stdout)

    def test_non_executable_msgfmt_counts_as_missing(self):
        """shutil.which rejects a non-executable msgfmt, so it never reaches subprocess."""
        fake_bin = tempfile.mkdtemp()
        unrunnable = os.path.join(fake_bin, "msgfmt")
        pathlib.Path(unrunnable).write_text("not an executable")
        os.chmod(unrunnable, 0o644)
        completed = self.run_entry_point({"PATH": fake_bin})
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("msgfmt not found", completed.stderr)
        self.assertIn("Run a game directly", completed.stdout)

    def test_msgfmt_raising_is_not_fatal(self):
        """Covers the handler for subprocess itself failing to run msgfmt.

        Both msgfmt and the call are faked, so this holds without gettext installed.
        """
        source = tempfile.mkdtemp()
        os.makedirs(os.path.join(source, "po"))
        pathlib.Path(os.path.join(source, "po", "fr.po")).write_text('msgid ""\nmsgstr ""\n')

        def refuse_to_run(*args, **kwargs):
            raise OSError("Exec format error")

        reported = io.StringIO()
        with mock.patch.object(textdomain.shutil, "which", return_value="/usr/bin/msgfmt"):
            with mock.patch.object(textdomain.subprocess, "run", refuse_to_run):
                with contextlib.redirect_stderr(reported):
                    self.assertIsNone(textdomain.compile_source_catalogs(source))
        self.assertIn("Exec format error", reported.getvalue())

    def test_failure_inside_the_build_is_not_fatal(self):
        """Even an unforeseen error must only cost the translations."""

        def explode(_source_path: str) -> str | None:
            raise RuntimeError("something nobody anticipated")

        boom = textdomain.compile_source_catalogs
        textdomain.compile_source_catalogs = explode
        try:
            reported = io.StringIO()
            with contextlib.redirect_stderr(reported):
                textdomain.bind_text_domain("/any/source/tree")
            self.assertIn("Couldn't set up translations", reported.getvalue())
        finally:
            textdomain.compile_source_catalogs = boom

    def test_unreadable_locale_dir_is_not_fatal(self):
        """bindtextdomain itself may reject what it is handed."""
        reported = io.StringIO()
        with contextlib.redirect_stderr(reported):
            textdomain.bind_text_domain(None)  # no source tree, nothing to bind
        self.assertEqual(reported.getvalue(), "")
