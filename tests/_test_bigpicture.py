import os
import stat
import tempfile
import unittest
from unittest import mock

from lutris import settings
from lutris.database import categories as categories_db
from lutris.database import games as games_db
from lutris.database import schema
from lutris.game import Game
from lutris.gui import bigpicture
from lutris.util.test_config import setup_test_environment

setup_test_environment()


class FakeApplication:
    """Just enough of LutrisApplication for BigPictureMode to work with."""

    def __init__(self):
        self.window = None
        self.ready = False
        self.exited_with = None
        self.running_games = []

    def get_running_games(self):
        return self.running_games

    def is_game_running_by_id(self, game_id):
        return any(game.id == game_id for game in self.running_games)

    def on_big_picture_ready(self):
        self.ready = True

    def on_big_picture_exited(self, quit_lutris):
        self.exited_with = quit_lutris


class RecordingBigPictureMode(bigpicture.BigPictureMode):
    """Records what would be sent to the interface, rather than running one,
    and what Steam would be asked for, rather than asking it."""

    def __init__(self, application):
        super().__init__(application)
        self.sent = []
        self._steam_input = mock.Mock()

    def _send(self, message):
        self.sent.append(message)


class BigPictureTester(unittest.TestCase):
    def setUp(self):
        if os.path.exists(settings.DB_PATH):
            os.remove(settings.DB_PATH)
        schema.syncdb()


class TestLibrary(BigPictureTester):
    def test_only_installed_games_are_listed(self):
        installed_id = games_db.add_game(name="Installed", runner="linux", installed=1)
        games_db.add_game(name="Not Installed", runner="linux", installed=0)
        library = bigpicture.get_library()
        self.assertEqual([game["id"] for game in library], [installed_id])
        self.assertEqual(library[0]["name"], "Installed")

    def test_hidden_games_are_left_out(self):
        game_id = games_db.add_game(name="Secret", runner="linux", installed=1)
        hidden_id = categories_db.add_category(".hidden", no_signal=True)
        categories_db.add_game_to_category(game_id, hidden_id, no_signal=True)
        self.assertEqual(bigpicture.get_library(), [])

    def test_favorites_and_categories(self):
        game_id = games_db.add_game(name="Loved", runner="linux", installed=1)
        for name in ("favorite", "RPG"):
            category_id = categories_db.add_category(name, no_signal=True)
            categories_db.add_game_to_category(game_id, category_id, no_signal=True)
        (game,) = bigpicture.get_library()
        self.assertTrue(game["favorite"])
        self.assertEqual(game["categories"], ["RPG"])

    def test_unplayed_game_has_no_play_time_or_date(self):
        games_db.add_game(name="Fresh", runner="linux", installed=1)
        (game,) = bigpicture.get_library()
        self.assertEqual(game["playtime_text"], "")
        self.assertEqual(game["lastplayed_text"], "")
        self.assertIsNone(game["cover"])

    def test_played_game_has_play_time_and_date(self):
        games_db.add_game(name="Played", runner="linux", installed=1, playtime=2.5, lastplayed=1700000000)
        (game,) = bigpicture.get_library()
        self.assertEqual(game["playtime"], 2.5)
        self.assertNotEqual(game["playtime_text"], "")
        self.assertEqual(game["lastplayed"], 1700000000)
        self.assertNotEqual(game["lastplayed_text"], "")


class TestMessages(BigPictureTester):
    def test_ready_sends_strings_and_library_and_hides_the_window(self):
        games_db.add_game(name="A Game", runner="linux", installed=1)
        application = FakeApplication()
        mode = RecordingBigPictureMode(application)
        mode._handle_message({"type": "ready"})
        self.assertEqual([message["type"] for message in mode.sent], ["init", "library"])
        self.assertIn("Play", mode.sent[0]["strings"])
        self.assertEqual(len(mode.sent[0]["sounds"]["dirs"]), 2)
        self.assertEqual(len(mode.sent[1]["games"]), 1)
        self.assertTrue(application.ready)

    def test_library_carries_the_state_of_running_games(self):
        game_id = games_db.add_game(name="A Game", runner="linux", installed=1)
        application = FakeApplication()
        running = Game(game_id)
        running.state = Game.STATE_RUNNING
        application.running_games = [running]
        mode = RecordingBigPictureMode(application)
        mode._send_library()
        self.assertEqual(mode.sent[0]["games"][0]["state"], "running")

    def test_set_favorite(self):
        game_id = games_db.add_game(name="A Game", runner="linux", installed=1)
        mode = RecordingBigPictureMode(FakeApplication())
        mode._handle_message({"type": "set_favorite", "id": game_id, "favorite": True})
        self.assertTrue(Game(game_id).is_favorite)
        mode._handle_message({"type": "set_favorite", "id": game_id, "favorite": False})
        self.assertFalse(Game(game_id).is_favorite)

    def test_sound_pack_choice_is_remembered_and_sent_back(self):
        mode = RecordingBigPictureMode(FakeApplication())
        with mock.patch.object(settings, "write_setting") as write_setting:
            mode._handle_message({"type": "set_sound_pack", "pack": "retro"})
        write_setting.assert_called_once_with(bigpicture.SOUND_PACK_SETTING, "retro")
        with mock.patch.object(settings, "read_setting", return_value="retro"):
            mode._handle_message({"type": "ready"})
        self.assertEqual(mode.sent[0]["sounds"]["pack"], "retro")

    def test_start_animation_plays_unless_switched_off(self):
        self.assertEqual(bigpicture.get_command("/bin/bp"), ["/bin/bp"])
        mode = RecordingBigPictureMode(FakeApplication())
        with mock.patch.object(settings, "write_setting") as write_setting:
            mode._handle_message({"type": "set_splash", "enabled": False})
        write_setting.assert_called_once_with(bigpicture.SPLASH_SETTING, False)
        with mock.patch.object(settings, "read_bool_setting", return_value=False):
            self.assertEqual(bigpicture.get_command("/bin/bp"), ["/bin/bp", "--no-splash"])

    def test_stopping_a_game_that_is_not_running_corrects_the_interface(self):
        mode = RecordingBigPictureMode(FakeApplication())
        mode._handle_message({"type": "stop", "id": "42"})
        self.assertEqual(mode.sent, [{"type": "game_state", "id": "42", "state": "stopped", "status": ""}])

    def test_stopping_a_launch_that_is_waiting_cancels_it(self):
        mode = RecordingBigPictureMode(FakeApplication())
        mode.pending_launches.add("42")
        mode._handle_message({"type": "stop", "id": "42"})
        self.assertNotIn("42", mode.pending_launches)
        self.assertEqual(mode.sent[-1]["state"], "stopped")

    def test_failed_launch_is_reported(self):
        game_id = games_db.add_game(name="A Game", runner="linux", installed=1)
        mode = RecordingBigPictureMode(FakeApplication())
        with mock.patch.object(Game, "launch", side_effect=RuntimeError("it broke")):
            mode._handle_message({"type": "launch", "id": game_id})
        self.assertEqual(mode.sent[0], {"type": "error", "message": "it broke"})
        self.assertEqual(mode.sent[1]["state"], "stopped")


class TestSteamInput(BigPictureTester):
    def hold_with_steam(self, steam_pid):
        """A hold, with Steam running as the process given (or not at all),
        and the list of app IDs Steam was asked to use."""
        hold = bigpicture.SteamInputHold()
        forced = []
        patches = [
            mock.patch.object(bigpicture, "get_steam_pid", side_effect=lambda: steam_pid[0]),
            mock.patch.object(
                bigpicture, "force_steam_input_appid", side_effect=lambda appid: forced.append(appid) or True
            ),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

        return hold, forced

    def test_steam_is_told_to_keep_off_and_then_let_back(self):
        hold, forced = self.hold_with_steam(["100"])

        hold.hold(wait=True)
        hold.hold(wait=True)  # already done: not asked again

        self.assertEqual(forced, [bigpicture.STEAM_CLIENT_APPID])

        hold.release(wait=True)
        hold.release(wait=True)

        self.assertEqual(forced, [bigpicture.STEAM_CLIENT_APPID, 0])

    def test_steam_is_left_alone_when_it_is_not_running(self):
        steam_pid = [None]
        hold, forced = self.hold_with_steam(steam_pid)

        hold.hold(wait=True)
        hold.release(wait=True)

        self.assertEqual(forced, [], "asking would have started Steam")

        # Once it does run, it is told on the next occasion.
        steam_pid[0] = "100"
        hold.hold(wait=True)

        self.assertEqual(forced, [bigpicture.STEAM_CLIENT_APPID])

    def test_a_restarted_steam_is_told_again(self):
        steam_pid = ["100"]
        hold, forced = self.hold_with_steam(steam_pid)
        hold.hold(wait=True)

        steam_pid[0] = "200"
        hold.hold(wait=True)

        self.assertEqual(forced, [bigpicture.STEAM_CLIENT_APPID] * 2)

        # And a Steam that has gone needs no letting back.
        steam_pid[0] = None
        hold.release(wait=True)

        self.assertEqual(forced, [bigpicture.STEAM_CLIENT_APPID] * 2)

    def test_request_is_not_made_without_steam(self):
        with mock.patch.object(bigpicture, "get_steam_pid", return_value=None):
            with mock.patch.object(bigpicture.subprocess, "run") as run:
                self.assertFalse(bigpicture.force_steam_input_appid(7))

        run.assert_not_called()

    def test_held_in_the_interface_and_released_for_a_game(self):
        game_id = games_db.add_game(name="A Game", runner="linux", installed=1)
        application = FakeApplication()
        mode = RecordingBigPictureMode(application)
        mode._process = mock.Mock()  # as if the interface were running

        mode._update_steam_input()

        mode._steam_input.hold.assert_called_once()
        mode._steam_input.release.assert_not_called()

        running = Game(game_id)
        running.state = Game.STATE_RUNNING
        application.running_games = [running]
        mode._on_game_state_changed(running)

        mode._steam_input.release.assert_called_once()

        application.running_games = []
        mode._on_game_stopped(running)

        self.assertEqual(mode._steam_input.hold.call_count, 2)

    def test_released_before_a_game_is_launched_and_on_leaving(self):
        game_id = games_db.add_game(name="A Game", runner="linux", installed=1)
        mode = RecordingBigPictureMode(FakeApplication())
        mode._process = mock.Mock()

        with mock.patch.object(Game, "launch", return_value=True):
            mode._handle_message({"type": "launch", "id": game_id})

        mode._steam_input.release.assert_called_once_with()

        mode._cleanup()

        mode._steam_input.release.assert_called_with(wait=True)
        self.assertFalse(mode._update_steam_input(), "nothing more to do once left")


class TestExecutable(unittest.TestCase):
    def test_override_is_used_when_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "bigpicture")
            with open(path, "w", encoding="utf-8") as script:
                script.write("#!/bin/sh\n")
            with mock.patch.dict(os.environ, {"LUTRIS_BIGPICTURE": path}):
                self.assertIsNone(bigpicture.find_big_picture_executable())
                os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
                self.assertEqual(bigpicture.find_big_picture_executable(), path)

    def test_runtime_dir_is_found_when_the_environment_lacks_it(self):
        with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": "/somewhere"}):
            self.assertEqual(bigpicture.get_runtime_dir(), "/somewhere")

        with mock.patch.dict(os.environ):
            os.environ.pop("XDG_RUNTIME_DIR", None)
            with mock.patch.object(bigpicture.os.path, "isdir", return_value=True):
                self.assertEqual(bigpicture.get_runtime_dir(), "/run/user/%d" % os.getuid())

            with mock.patch.object(bigpicture.os.path, "isdir", return_value=False):
                self.assertIsNone(bigpicture.get_runtime_dir())

    def test_wayland_display_is_found_when_the_environment_lacks_it(self):
        with mock.patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-7"}):
            self.assertEqual(bigpicture.get_wayland_display("/nowhere"), "wayland-7")

        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(os.environ):
            os.environ.pop("WAYLAND_DISPLAY", None)
            self.assertIsNone(bigpicture.get_wayland_display(directory), "nothing there")
            self.assertIsNone(bigpicture.get_wayland_display(None))

            # A socket nobody listens on is a compositor that has gone.
            dead = bigpicture.socket.socket(bigpicture.socket.AF_UNIX)
            dead.bind(os.path.join(directory, "wayland-0"))
            dead.close()
            with open(os.path.join(directory, "wayland-1.lock"), "w", encoding="utf-8"):
                pass

            self.assertIsNone(bigpicture.get_wayland_display(directory))

            live = bigpicture.socket.socket(bigpicture.socket.AF_UNIX)
            self.addCleanup(live.close)
            live.bind(os.path.join(directory, "wayland-1"))
            live.listen(1)

            self.assertEqual(bigpicture.get_wayland_display(directory), "wayland-1")

    def test_default_sound_pack_is_shipped_complete(self):
        pack = os.path.join(bigpicture.get_sound_pack_dirs()[-1], "default")
        sounds = ["move", "select", "back", "tab", "open", "key", "toggle", "launch", "error"]

        for sound in sounds:
            self.assertTrue(os.path.isfile(os.path.join(pack, sound + ".ogg")), sound)

        self.assertTrue(os.path.isfile(os.path.join(pack, "pack.json")))

    def test_start_without_the_program_explains_what_to_do(self):
        mode = bigpicture.BigPictureMode(FakeApplication())
        with mock.patch.object(bigpicture, "find_big_picture_executable", return_value=None):
            with self.assertRaises(bigpicture.MissingExecutableError):
                mode.start()
        self.assertFalse(mode.is_active)
