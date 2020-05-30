import os
from unittest import TestCase
from lutris.util.graphics.glxinfo import GlxInfo

FIXTURES_PATH = os.path.join(os.path.dirname(__file__), 'fixtures')


class BaseGlxInfo(TestCase):
    fixture = None

    def setUp(self):
        output = self.read_fixture(self.fixture)
        self.glxinfo = GlxInfo(output)

    def read_fixture(self, fixture_filename):
        with open(os.path.join(FIXTURES_PATH, fixture_filename)) as fixture:
            content = fixture.read()
        return content


class TestAMDGlxInfo(BaseGlxInfo):
    fixture = 'glxinfo-amd.txt'

    """GlxInfo tests"""
    def test_can_get_name_of_display(self):
        self.assertEqual(self.glxinfo.display, ":0")
        self.assertEqual(self.glxinfo.screen, "0")
        self.assertEqual(
            self.glxinfo.opengl_version,
            "4.5 (Compatibility Profile) Mesa 19.0.0-devel - padoka PPA"
        )
        self.assertEqual(self.glxinfo.opengl_vendor, "X.Org")
        self.assertEqual(self.glxinfo.GLX_MESA_query_renderer.version, "19.0.0")


class TestNvidiaGlxInfo(BaseGlxInfo):
    """GlxInfo tests"""
    fixture = 'glxinfo-nvidia.txt'

    def test_can_get_name_of_display(self):
        self.assertEqual(self.glxinfo.display, ":0")
        self.assertEqual(self.glxinfo.screen, "0")
        self.assertEqual(self.glxinfo.opengl_version, "4.6.0 NVIDIA 415.25")
        self.assertEqual(self.glxinfo.opengl_vendor, "NVIDIA Corporation")
        with self.assertRaises(AttributeError):
            self.glxinfo.GLX_MESA_query_renderer.version  # pylint: disable=pointless-statement
