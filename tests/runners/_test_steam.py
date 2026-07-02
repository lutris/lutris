"""Tests for the Steam runner's reaper-based running-state tracking."""

import signal
from contextlib import contextmanager
from unittest import TestCase
from unittest.mock import MagicMock, PropertyMock, patch

from lutris.util.test_config import setup_test_environment

setup_test_environment()

from lutris.runners import steam  # noqa: E402  (must follow setup_test_environment)


@contextmanager
def make_runner(appid="440", runner_config=None):
    """Yield a Steam runner built through its real __init__ (so new instance
    state can't be silently missed by the fixture), with config access stubbed
    so no real config/DB/disk is touched.

    appid and runner_config are exposed via patched property reads.
    """
    runner = steam.steam()  # real __init__, config=None
    game_config = {"appid": appid}
    with (
        patch.object(steam.steam, "game_config", new_callable=PropertyMock, return_value=game_config),
        patch.object(
            steam.steam,
            "runner_config",
            new_callable=PropertyMock,
            return_value=runner_config or {},
        ),
    ):
        yield runner


def fake_appmanifest(states):
    manifest = MagicMock()
    manifest.states = states
    manifest.appmanifest_path = "/steamapps/appmanifest_440.acf"
    return manifest


class FilterGamePidsTest(TestCase):
    """filter_game_pids tracks the game by Steam's reaper PID (primary) with the
    appmanifest AppRunning flag as a secondary signal."""

    def test_reaper_pid_tracked_when_running(self):
        with make_runner() as runner:
            with (
                patch.object(steam.Runner, "filter_game_pids", return_value=set()),
                patch.object(steam, "get_steam_game_pids", return_value=[5555]),
            ):
                pids = runner.filter_game_pids(candidate_pids=set(), game_uuid="u", game_folder="/g")
        self.assertEqual(pids, {5555})

    def test_appmanifest_fallback_when_no_reaper(self):
        with make_runner() as runner:
            with (
                patch.object(steam.Runner, "filter_game_pids", return_value=set()),
                patch.object(steam, "get_steam_game_pids", return_value=[]),
                patch.object(runner, "_game_is_alive_in_steam", return_value=True),
                patch.object(runner, "_get_steam_pid_int", return_value=4242),
            ):
                pids = runner.filter_game_pids(candidate_pids=set(), game_uuid="u", game_folder="/g")
        self.assertEqual(pids, {4242})

    def test_empty_when_not_running(self):
        with make_runner() as runner:
            with (
                patch.object(steam.Runner, "filter_game_pids", return_value=set()),
                patch.object(steam, "get_steam_game_pids", return_value=[]),
                patch.object(runner, "_game_is_alive_in_steam", return_value=False),
            ):
                pids = runner.filter_game_pids(candidate_pids=set(), game_uuid="u", game_folder="/g")
        self.assertEqual(pids, set())

    def test_base_pids_preserved(self):
        with make_runner() as runner:
            with (
                patch.object(steam.Runner, "filter_game_pids", return_value={999}),
                patch.object(steam, "get_steam_game_pids", return_value=[5555]),
            ):
                pids = runner.filter_game_pids(candidate_pids={999}, game_uuid="u", game_folder="/g")
        self.assertEqual(pids, {999, 5555})

    def test_no_appid_is_noop(self):
        with make_runner(appid="") as runner:
            with (
                patch.object(steam.Runner, "filter_game_pids", return_value={5}),
                patch.object(steam, "get_steam_game_pids", return_value=[5555]),
            ):
                pids = runner.filter_game_pids(candidate_pids={5}, game_uuid="u", game_folder="/g")
        self.assertEqual(pids, {5})


class KeepGameAliveTest(TestCase):
    """beat() asks keep_game_alive() whether to keep monitoring even though the
    launcher thread has exited -- covering the launch window and game lifetime."""

    def test_alive_while_thread_running(self):
        with make_runner() as runner:
            with patch.object(steam, "get_steam_game_pids", return_value=[]):
                # game_thread still running -> always keep monitoring
                self.assertTrue(runner.keep_game_alive(set(), game_thread_running=True))

    def test_alive_while_reaper_present(self):
        with make_runner() as runner:
            with patch.object(steam, "get_steam_game_pids", return_value=[5555]):
                self.assertTrue(runner.keep_game_alive({5555}, game_thread_running=False))
            self.assertTrue(runner._steam_reaper_seen)

    def test_alive_during_launch_window_before_reaper(self):
        with make_runner() as runner:
            # Thread exited, reaper not up yet, never seen -> stay alive (grace)
            with patch.object(steam, "get_steam_game_pids", return_value=[]):
                self.assertTrue(runner.keep_game_alive(set(), game_thread_running=False))

    def test_quit_after_reaper_seen_then_gone(self):
        with make_runner() as runner:
            with patch.object(steam, "get_steam_game_pids", return_value=[5555]):
                runner.keep_game_alive({5555}, game_thread_running=False)  # sees reaper
            # Expire the per-beat reaper cache so the next call re-scans.
            runner._reaper_pids_cache_at = 0.0
            with patch.object(steam, "get_steam_game_pids", return_value=[]):
                # reaper gone after having been seen -> game genuinely quit
                self.assertFalse(runner.keep_game_alive(set(), game_thread_running=False))

    def test_quit_after_grace_expires(self):
        with make_runner() as runner:
            runner._launch_monitor_start = 0.0  # far in the past
            with (
                patch.object(steam, "get_steam_game_pids", return_value=[]),
                patch.object(steam.time, "monotonic", return_value=runner.launch_grace_seconds + 1),
            ):
                self.assertFalse(runner.keep_game_alive(set(), game_thread_running=False))

    def test_grace_window_uses_configured_value(self):
        # A custom launch_grace_seconds option overrides the default.
        with make_runner(runner_config={"launch_grace_seconds": "10"}) as runner:
            self.assertEqual(runner.launch_grace_seconds, 10)
            runner._launch_monitor_start = 0.0
            with (
                patch.object(steam, "get_steam_game_pids", return_value=[]),
                patch.object(steam.time, "monotonic", return_value=5),  # within 10s window
            ):
                self.assertTrue(runner.keep_game_alive(set(), game_thread_running=False))
            with (
                patch.object(steam, "get_steam_game_pids", return_value=[]),
                patch.object(steam.time, "monotonic", return_value=11),  # past 10s window
            ):
                runner._reaper_pids_cache_at = 0.0
                self.assertFalse(runner.keep_game_alive(set(), game_thread_running=False))

    def test_grace_default_and_invalid_fallback(self):
        with make_runner() as runner:  # no option set
            self.assertEqual(runner.launch_grace_seconds, steam.DEFAULT_LAUNCH_GRACE_SECONDS)
        # Non-numeric and non-positive values both fall back to the default and
        # both emit a warning (the two invalid cases are treated identically).
        with make_runner(runner_config={"launch_grace_seconds": "notanumber"}) as runner:
            with self.assertLogs(steam.logger, level="WARNING"):
                self.assertEqual(runner.launch_grace_seconds, steam.DEFAULT_LAUNCH_GRACE_SECONDS)
        with make_runner(runner_config={"launch_grace_seconds": "-5"}) as runner:
            with self.assertLogs(steam.logger, level="WARNING"):
                self.assertEqual(runner.launch_grace_seconds, steam.DEFAULT_LAUNCH_GRACE_SECONDS)

    def test_false_without_appid(self):
        with make_runner(appid="") as runner:
            self.assertFalse(runner.keep_game_alive({5555}, game_thread_running=False))


class ForceStopGameTest(TestCase):
    """force_stop_game must terminate the game's reaper, never the Steam client."""

    def test_sigterms_reaper_not_steam(self):
        with make_runner() as runner:
            with (
                patch.object(runner, "_get_steam_pid_int", return_value=4242),
                patch.object(steam, "get_steam_game_pids", return_value=[5555]),
                patch.object(steam, "kill_processes") as kill,
            ):
                # game_pids includes Steam's own PID (from appmanifest fallback) -- must be spared
                runner.force_stop_game([4242, 5555])
                kill.assert_called_once()
                sig, pids = kill.call_args[0]
                self.assertEqual(sig, signal.SIGTERM)
                self.assertIn(5555, pids)
                self.assertNotIn(4242, pids)

    def test_no_kill_when_nothing_to_stop(self):
        with make_runner() as runner:
            with (
                patch.object(runner, "_get_steam_pid_int", return_value=4242),
                patch.object(steam, "get_steam_game_pids", return_value=[]),
                patch.object(steam, "kill_processes") as kill,
            ):
                runner.force_stop_game([4242])  # only Steam's PID -> nothing to kill
                kill.assert_not_called()


class SteamGamePidsHelperTest(TestCase):
    def test_empty_appid_returns_empty(self):
        self.assertEqual(steam.get_steam_game_pids(""), [])

    def _fake_proc(self, procs):
        """Build patches simulating /proc with the given {pid: cmdline} map."""
        import builtins

        listdir = patch.object(steam.os, "listdir", return_value=list(procs.keys()))

        real_open = builtins.open

        def fake_open(path, *args, **kwargs):
            for pid, cmdline in procs.items():
                if path == steam.os.path.join("/proc", pid, "cmdline"):
                    from io import BytesIO

                    return BytesIO(cmdline.replace(" ", "\x00").encode() + b"\x00")
            return real_open(path, *args, **kwargs)

        return listdir, patch.object(builtins, "open", side_effect=fake_open)

    def test_matches_exact_appid(self):
        procs = {
            "100": "reaper SteamLaunch AppId=440 -- /path/tf.sh",
            "200": "some other process",
        }
        listdir, opener = self._fake_proc(procs)
        with listdir, opener:
            self.assertEqual(steam.get_steam_game_pids("440"), [100])

    def test_does_not_match_appid_prefix_collision(self):
        # appid 440 must NOT match a reaper for 4400 or 44012 (substring guard).
        procs = {
            "300": "reaper SteamLaunch AppId=4400 -- /path/x.sh",
            "301": "reaper SteamLaunch AppId=44012 -- /path/y.sh",
        }
        listdir, opener = self._fake_proc(procs)
        with listdir, opener:
            self.assertEqual(steam.get_steam_game_pids("440"), [])

    def test_requires_reaper_in_cmdline(self):
        # A non-reaper process mentioning the appid must not match.
        procs = {"400": "steamwebhelper SteamLaunch AppId=440 something"}
        listdir, opener = self._fake_proc(procs)
        with listdir, opener:
            self.assertEqual(steam.get_steam_game_pids("440"), [])


class SteamPidIntTest(TestCase):
    def test_string_pid_converted(self):
        with make_runner() as runner:
            with patch.object(steam, "get_steam_pid", return_value="1234"):
                self.assertEqual(runner._get_steam_pid_int(), 1234)

    def test_none_pid(self):
        with make_runner() as runner:
            with patch.object(steam, "get_steam_pid", return_value=None):
                self.assertIsNone(runner._get_steam_pid_int())


class GetSteamPidTest(TestCase):
    """get_steam_pid() narrows system.get_pid()'s str | list[str] | None to a
    plain Optional[str] (Steam is single-instance, so at most one PID)."""

    def test_string_passthrough(self):
        with patch.object(steam.system, "get_pid", return_value="1234"):
            self.assertEqual(steam.get_steam_pid(), "1234")

    def test_none(self):
        with patch.object(steam.system, "get_pid", return_value=None):
            self.assertIsNone(steam.get_steam_pid())

    def test_list_narrowed_to_first(self):
        with patch.object(steam.system, "get_pid", return_value=["1234", "5678"]):
            self.assertEqual(steam.get_steam_pid(), "1234")

    def test_empty_list(self):
        with patch.object(steam.system, "get_pid", return_value=[]):
            self.assertIsNone(steam.get_steam_pid())


class GameAliveTest(TestCase):
    def test_app_running_is_alive(self):
        with make_runner() as runner:
            with patch.object(runner, "_get_cached_appmanifest", return_value=fake_appmanifest(["AppRunning"])):
                self.assertTrue(runner._game_is_alive_in_steam())

    def test_fully_installed_only_is_not_alive(self):
        with make_runner() as runner:
            with patch.object(runner, "_get_cached_appmanifest", return_value=fake_appmanifest(["Fully Installed"])):
                self.assertFalse(runner._game_is_alive_in_steam())

    def test_no_manifest_is_not_alive(self):
        with make_runner() as runner:
            with patch.object(runner, "_get_cached_appmanifest", return_value=None):
                self.assertFalse(runner._game_is_alive_in_steam())


class CachedAppmanifestTest(TestCase):
    def test_path_resolved_once_then_reused(self):
        with make_runner() as runner:
            manifest = fake_appmanifest(["AppRunning"])
            with patch.object(runner, "get_appmanifest", return_value=manifest) as get_am:
                first = runner._get_cached_appmanifest()
                self.assertIs(first, manifest)
                with patch.object(steam, "AppManifest", return_value=manifest) as AM:
                    second = runner._get_cached_appmanifest()
                    AM.assert_called_once_with("/steamapps/appmanifest_440.acf")
                get_am.assert_called_once()
                self.assertIs(second, manifest)
