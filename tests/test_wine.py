from unittest import TestCase
from lutris.runners import wine
from lutris.util.test_config import setup_test_environment


setup_test_environment()


class TestDllOverrides(TestCase):
    def test_env_format(self):
        overrides = {
            'd3dcompiler_43': 'native,builtin',
            'd3dcompiler_47': 'native,builtin',
            'dnsapi': ' builtin',
            'dwrite': ' disabled',
            'rasapi32': ' native',
        }
        env_string = wine.get_overrides_env(overrides)
        self.assertEqual(env_string, "d3dcompiler_43,d3dcompiler_47=n,b;dnsapi=b;rasapi32=n;dwrite=")
