import logging
from unittest import TestCase

from lutris.runners.snes9x import snes9x

LOGGER = logging.getLogger(__name__)


class TestUae(TestCase):
    def test_set_option(self):
        snes9x_runner = snes9x()
        if snes9x_runner.is_installed():
            snes9x_runner.set_option("full_screen_on_open", "1")
        else:
            LOGGER.info("snes9x not installed can't run test")
