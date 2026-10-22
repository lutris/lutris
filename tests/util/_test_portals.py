"""Tests for TrashPortal's fallback to g_file_trash_async() and its reporting
of files that could not be trashed at all."""

import os
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from gi.repository import Gio, GLib

from lutris.util.portals import TrashPortal


class _FakeAsyncResult:
    """Stands in for the Gio.AsyncResult our fakes hand to their callbacks."""


class _FakeProxyFactory:
    """Stands in for Gio.DBusProxy.new_for_bus(), handing out 'proxy' - which
    may be None, as it is when no Trash portal is available."""

    def __init__(self, proxy):
        self.proxy = proxy

    def __call__(self, *args):
        args[-1](self, _FakeAsyncResult())

    def new_for_bus_finish(self, result):
        return self.proxy


class _FakePortalProxy:
    """Stands in for the Trash portal proxy; 'results' gives the code TrashFile
    returns for each successive call, where 0 means failure."""

    def __init__(self, results):
        self.results = list(results)
        self.attempted = []
        self._last_result = None

    def call_with_unix_fd_list(self, method, params, flags, timeout, fds_in, cancellable, callback, user_data):
        self.attempted.append(user_data)
        self._last_result = self.results.pop(0)
        callback(self, _FakeAsyncResult(), user_data)

    def call_with_unix_fd_list_finish(self, result):
        return ((self._last_result,), None)


class _FakeGFile:
    def __init__(self, path, failures):
        self.path = path
        self.failures = failures

    def trash_async(self, priority, cancellable, callback, user_data):
        callback(self, _FakeAsyncResult(), user_data)

    def trash_finish(self, result):
        if self.path in self.failures:
            raise GLib.Error("No suitable trash directory found", "g-io-error-quark", 0)
        return True


class _FakeFileFactory:
    """Stands in for Gio.File.new_for_path(), recording which paths the
    fallback was actually used on."""

    def __init__(self, failures=()):
        self.failures = set(failures)
        self.attempted = []

    def __call__(self, path):
        self.attempted.append(path)
        return _FakeGFile(path, self.failures)


class TestTrashPortal(TestCase):
    def setUp(self):
        self.tmp_dir = TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        # Our fakes invoke their callbacks immediately, so the reporting
        # callbacks must run immediately too rather than at idle time.
        patcher = patch("lutris.util.portals.schedule_at_idle", new=lambda func, *args: func(*args))
        patcher.start()
        self.addCleanup(patcher.stop)

    def make_files(self, *names):
        paths = []
        for name in names:
            path = os.path.join(self.tmp_dir.name, name)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("to be trashed")
            paths.append(path)
        return paths

    def run_portal(self, paths, proxy=None, fallback_failures=()):
        """Runs a TrashPortal against fakes, and returns the Gio.File factory
        (for the paths the fallback was used on), the completion callbacks it
        made, and the errors it reported."""
        file_factory = _FakeFileFactory(fallback_failures)
        completions = []
        errors = []
        with (
            patch.object(Gio.DBusProxy, "new_for_bus", new=_FakeProxyFactory(proxy)),
            patch.object(Gio.File, "new_for_path", new=file_factory),
        ):
            TrashPortal(
                paths,
                completion_function=lambda: completions.append(True),
                error_function=errors.append,
            )
        return file_factory, completions, errors

    def test_no_portal_falls_back_for_every_file(self):
        paths = self.make_files("one", "two")
        file_factory, completions, errors = self.run_portal(paths)
        self.assertEqual(file_factory.attempted, paths)
        self.assertEqual(completions, [True])
        self.assertEqual(errors, [])

    def test_portal_refusal_falls_back(self):
        paths = self.make_files("one")
        proxy = _FakePortalProxy([0])
        file_factory, completions, errors = self.run_portal(paths, proxy=proxy)
        self.assertEqual(proxy.attempted, paths)
        self.assertEqual(file_factory.attempted, paths)
        self.assertEqual(completions, [True])
        self.assertEqual(errors, [])

    def test_portal_success_skips_the_fallback(self):
        paths = self.make_files("one", "two")
        proxy = _FakePortalProxy([1, 1])
        file_factory, completions, errors = self.run_portal(paths, proxy=proxy)
        self.assertEqual(proxy.attempted, paths)
        self.assertEqual(file_factory.attempted, [])
        self.assertEqual(completions, [True])
        self.assertEqual(errors, [])

    def test_failed_fallback_reports_an_error(self):
        paths = self.make_files("one")
        _, completions, errors = self.run_portal(paths, fallback_failures=paths)
        self.assertEqual(completions, [])
        self.assertEqual(len(errors), 1)
        self.assertIn(paths[0], str(errors[0]))
        self.assertIn("could not be moved to the trash", str(errors[0]))

    def test_failure_does_not_abort_the_remaining_files(self):
        paths = self.make_files("one", "two", "three")
        file_factory, completions, errors = self.run_portal(paths, fallback_failures=[paths[1]])
        self.assertEqual(file_factory.attempted, paths)
        self.assertEqual(completions, [])
        self.assertEqual(len(errors), 1)
        # Only the file that failed is named, not the ones we did trash.
        self.assertIn(paths[1], str(errors[0]))
        self.assertNotIn(paths[0], str(errors[0]))
        self.assertNotIn(paths[2], str(errors[0]))

    def test_multiple_failures_are_reported_together(self):
        paths = self.make_files("one", "two", "three")
        _, completions, errors = self.run_portal(paths, fallback_failures=[paths[0], paths[2]])
        self.assertEqual(completions, [])
        self.assertEqual(len(errors), 1)
        self.assertIn(paths[0], str(errors[0]))
        self.assertIn(paths[2], str(errors[0]))
        self.assertNotIn(paths[1], str(errors[0]))
