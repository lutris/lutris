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
import sysconfig
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
        # lutris.version comes with the package itself and translates nothing
        self.assertEqual(loaded.split(), ["lutris", "lutris.util", "lutris.util.textdomain", "lutris.version"])

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
    def setUp(self) -> None:
        self.root = pathlib.Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.source = self.root / "locale"
        self.source.mkdir()
        self.cache = self.root / "cache"
        self.enterContext(mock.patch.dict(os.environ, XDG_CACHE_HOME=str(self.cache)))

    def write_catalog(self, name: str, body: str) -> pathlib.Path:
        path = self.source / name
        path.write_text('msgid ""\nmsgstr "Content-Type: text/plain; charset=UTF-8\\n"\n\n' + body)
        return path

    def test_compiles_catalogs(self):
        self.write_catalog("fr.po", 'msgid "Change"\nmsgstr "Modifier"\n')
        locale_dir = textdomain.compile_source_catalogs(self.source)
        assert locale_dir is not None
        self.assertTrue((locale_dir / "fr/LC_MESSAGES/lutris.mo").is_file())

    @unittest.skipIf(os.geteuid() == 0, "root ignores directory permissions")
    def test_builds_from_read_only_package(self) -> None:
        self.write_catalog("fr.po", 'msgid "Change"\nmsgstr "Modifier"\n')
        self.source.chmod(0o500)
        self.addCleanup(self.source.chmod, 0o700)
        locale_dir = textdomain.compile_source_catalogs(self.source)
        assert locale_dir is not None
        self.assertTrue(locale_dir.is_relative_to(self.cache))

    def test_checkouts_do_not_share_catalogs(self):
        """Two checkouts of differing age must each get their own translation."""
        older = self.write_catalog("fr.po", 'msgid "Change"\nmsgstr "FROM-A"\n')
        os.utime(older, (1000, 1000))

        other_source = self.root / "other"
        other_source.mkdir()
        (other_source / "fr.po").write_text(
            'msgid ""\nmsgstr "Content-Type: text/plain; charset=UTF-8\\n"\n\nmsgid "Change"\nmsgstr "FROM-B"\n'
        )

        textdomain.compile_source_catalogs(other_source)
        locale_dir = textdomain.compile_source_catalogs(self.source)
        assert locale_dir is not None
        translation = gettext.translation("lutris", localedir=str(locale_dir), languages=["fr"])
        self.assertEqual(translation.gettext("Change"), "FROM-A")

    @unittest.skipIf(os.geteuid() == 0, "root ignores directory permissions")
    def test_unwritable_cache_is_not_fatal(self) -> None:
        self.write_catalog("fr.po", 'msgid "Change"\nmsgstr "Modifier"\n')
        self.cache.mkdir(mode=0o500)
        self.addCleanup(self.cache.chmod, 0o700)
        reported = io.StringIO()
        with contextlib.redirect_stderr(reported):
            self.assertIsNone(textdomain.compile_source_catalogs(self.source))
        self.assertIn("Couldn't build translations", reported.getvalue())

    def test_skips_unchanged_catalogs(self):
        self.write_catalog("fr.po", 'msgid "Change"\nmsgstr "Modifier"\n')
        locale_dir = textdomain.compile_source_catalogs(self.source)
        assert locale_dir is not None
        mo_path = locale_dir / "fr/LC_MESSAGES/lutris.mo"
        compiled_at = os.path.getmtime(mo_path)

        textdomain.compile_source_catalogs(self.source)
        self.assertEqual(os.path.getmtime(mo_path), compiled_at)

    def test_recompiles_edited_catalogs(self):
        po_path = self.write_catalog("fr.po", 'msgid "Change"\nmsgstr "Modifier"\n')
        locale_dir = textdomain.compile_source_catalogs(self.source)
        assert locale_dir is not None
        mo_path = locale_dir / "fr/LC_MESSAGES/lutris.mo"
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
        assert locale_dir is not None
        self.assertTrue((locale_dir / "fr/LC_MESSAGES/lutris.mo").is_file())
        self.assertFalse((locale_dir / "broken/LC_MESSAGES/lutris.mo").exists())

    def test_returns_none_without_catalogs(self):
        self.assertIsNone(textdomain.compile_source_catalogs(self.source))


class TestNeverFatal(unittest.TestCase):
    """Translation setup must never stop Lutris from starting."""

    def run_entry_point(self, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        """Run the console entry point in an isolated profile."""
        root = self.enterContext(tempfile.TemporaryDirectory())
        env = dict(os.environ, LANGUAGE="fr", XDG_CACHE_HOME=root)
        env.update(extra_env or {})
        return subprocess.run(
            [str(pathlib.Path(sysconfig.get_path("scripts")) / "lutris"), "--help"],
            capture_output=True,
            text=True,
            env=env,
            cwd=root,
        )

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
        root = pathlib.Path(self.enterContext(tempfile.TemporaryDirectory()))
        source = root / "locale"
        source.mkdir()
        (source / "fr.po").write_text('msgid ""\nmsgstr ""\n')

        def refuse_to_run(*args, **kwargs):
            raise OSError("Exec format error")

        reported = io.StringIO()
        with (
            mock.patch.dict(os.environ, XDG_CACHE_HOME=str(root / "cache")),
            mock.patch.object(textdomain.shutil, "which", return_value="/usr/bin/msgfmt"),
        ):
            with mock.patch.object(textdomain.subprocess, "run", refuse_to_run):
                with contextlib.redirect_stderr(reported):
                    self.assertIsNone(textdomain.compile_source_catalogs(source))
        self.assertIn("Exec format error", reported.getvalue())

    def test_failure_inside_the_build_is_not_fatal(self):
        """Even an unforeseen error must only cost the translations."""

        reported = io.StringIO()
        with (
            mock.patch.object(textdomain, "compile_source_catalogs", side_effect=RuntimeError),
            contextlib.redirect_stderr(reported),
        ):
            textdomain.bind_text_domain()
        self.assertIn("Couldn't set up translations", reported.getvalue())

    def test_uses_precompiled_catalogs_without_msgfmt(self) -> None:
        root = pathlib.Path(self.enterContext(tempfile.TemporaryDirectory()))
        catalog = root / "fr/LC_MESSAGES/lutris.mo"
        catalog.parent.mkdir(parents=True)
        catalog.touch()
        with (
            mock.patch.object(textdomain, "CATALOG_DIR", root),
            mock.patch.object(textdomain, "compile_source_catalogs") as compile_catalogs,
            mock.patch.object(textdomain.locale, "bindtextdomain"),
            mock.patch.object(textdomain.locale, "textdomain"),
            mock.patch.object(textdomain.gettext, "bindtextdomain") as bind_catalogs,
            mock.patch.object(textdomain.gettext, "textdomain"),
        ):
            textdomain.bind_text_domain()
        compile_catalogs.assert_not_called()
        bind_catalogs.assert_called_once_with("lutris", str(root))
