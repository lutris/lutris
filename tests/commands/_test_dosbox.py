from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from lutris.runners.commands.dosbox import dosexec, makeconfig


class Test_dosexec(TestCase):
    def test_dosexec_with_config_file_nor_executable_raises_ValueError(self):
        with self.assertRaises(ValueError) as _:
            dosexec(config_file=None, executable=None)


class Test_makeconfig(TestCase):
    def setUp(self) -> None:
        self.tmp_dir = TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_makeconfig_creates_file_successfully(self):
        config_path = self.tmp_path / "dosbox.conf"
        makeconfig(
            path=config_path,
            drives={"C": r"C:\DOSGAMES"},
            commands=["C:", "CLS", "ECHO Hello world..."],
        )

        self.assertTrue(config_path.exists(), "makeconfig failed to create config at path '%s'" % (str(config_path),))
        with config_path.open("r", encoding="utf-8") as config_file:
            config_data = config_file.read()
            self.assertIn(r'mount C "C:\DOSGAMES"', config_data)
