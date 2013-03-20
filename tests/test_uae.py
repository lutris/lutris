import logging
from unittest import TestCase

from lutris.runners import uae

LOGGER = logging.getLogger(__name__)


class TestUae(TestCase):

    def test_instanciate_runner(self):
        uae_runner = uae.uae()
        self.assertEqual(uae_runner.machine, "Amiga")

    def test_insert_floppies(self):
        # Two disks, one floppy drive
        config = {
            'game': {
                'disk': ['foo.adf', 'bar.adf']
            },
            'uae': {
                'nr_floppies': 1
            }
        }
        uae_runner = uae.uae(config)
        disks = uae_runner.insert_floppies()
        self.assertIn('floppy0', disks)
        self.assertNotIn('floppy1', disks)

        # Two disks, two floppy drives
        config = {
            'game': {
                'disk': ['foo.adf', 'bar.adf']
            },
            'uae': {
                'nr_floppies': 2
            }
        }
        uae_runner = uae.uae(config)
        disks = uae_runner.insert_floppies()
        self.assertIn('floppy0', disks)
        self.assertIn('floppy1', disks)

        # Zero disk, two floppy drives
        config = {
            'game': {
                'disk': []
            },
            'uae': {
                'nr_floppies': 2
            }
        }
        uae_runner = uae.uae(config)
        uae_runner.insert_floppies()
        self.assertNotIn('floppy0', uae_runner.uae_options)
        self.assertNotIn('floppy1', uae_runner.uae_options)
