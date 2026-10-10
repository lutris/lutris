from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from lutris.util import joypad

# A standard gamepad, as reported by evdev
DEVICE_INFO = SimpleNamespace(bustype=3, vendor=0x045E, product=0x028E, version=0x0110)


class FakeControllerDB:
    def __init__(self, mappings):
        self.controllers = mappings

    def __getitem__(self, guid):
        return self.controllers[guid]


class TestGetControllerMappings(TestCase):
    def _device(self):
        return SimpleNamespace(info=DEVICE_INFO)

    def test_returns_nothing_without_devices(self):
        with (
            patch.object(joypad, "get_devices", return_value=[]),
            patch.object(joypad, "GameControllerDB") as controller_db,
        ):
            self.assertEqual(joypad.get_controller_mappings(), [])

        controller_db.assert_not_called()

    def test_returns_nothing_when_the_controller_database_is_missing(self):
        with (
            patch.object(joypad, "get_devices", return_value=[self._device()]),
            patch.object(joypad, "GameControllerDB", side_effect=OSError("Path to gamecontrollerdb.txt not provided")),
        ):
            self.assertEqual(joypad.get_controller_mappings(), [])

    def test_returns_nothing_when_the_controller_database_is_corrupt(self):
        error = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

        with (
            patch.object(joypad, "get_devices", return_value=[self._device()]),
            patch.object(joypad, "GameControllerDB", side_effect=error),
        ):
            self.assertEqual(joypad.get_controller_mappings(), [])

    def test_returns_the_mapping_of_a_known_device(self):
        device = self._device()
        guid = joypad.get_sdl_identifier(device.info)
        controller_db = FakeControllerDB({guid: "a:b,c:d"})

        with (
            patch.object(joypad, "get_devices", return_value=[device]),
            patch.object(joypad, "GameControllerDB", return_value=controller_db),
        ):
            self.assertEqual(joypad.get_controller_mappings(), [(device, "a:b,c:d")])

    def test_ignores_devices_missing_from_the_database(self):
        with (
            patch.object(joypad, "get_devices", return_value=[self._device()]),
            patch.object(joypad, "GameControllerDB", return_value=FakeControllerDB({})),
        ):
            self.assertEqual(joypad.get_controller_mappings(), [])
