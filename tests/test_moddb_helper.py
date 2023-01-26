import unittest

from lutris.util.log import logger
try:
    import moddb
    SKIP_TESTS = False
except ImportError:
    moddb = object
    logger.error("ModDB tests skipped")
    SKIP_TESTS = True
from lutris.util.log import logger
from lutris.util.moddb import ModDB, is_moddb_url


class ModDBHelperTests(unittest.TestCase):
    def setUp(self):
        if SKIP_TESTS:
            return
        self.mirrors_list = []
        self.page_type = self.ModDBFileObj
        self.helper_obj = ModDB(parse_page_method=self.parse)

    def with_mirror(self, url: str, capacity: float):
        self.mirrors_list.append(moddb.boxes.Mirror(url=url, capacity=capacity))
        return self

    def with_page_type(self, page_type):
        self.page_type = page_type

    def parse(self, url):
        return self.page_type(self.mirrors_list)

    if not SKIP_TESTS:
        class ModDBFileObj(moddb.pages.File):
            def __init__(self, mirrors_list):
                self.mirrors_list = mirrors_list

            def get_mirrors(self):
                return self.mirrors_list

    class ModDBSomeOtherObj:
        def __init__(self, mirrors_list):
            pass

    # ctor
    def test_ctor_default_method(self):
        if SKIP_TESTS:
            return
        hlpr = ModDB()
        self.assertEqual(hlpr.parse, moddb.parse_page)

    def test_ctor_custom_method(self):
        if SKIP_TESTS:
            return

        def custom():
            pass
        hlpr = ModDB(parse_page_method=custom)
        self.assertEqual(hlpr.parse, custom)

    # missing moddb lib handling
    def test_transform_url_missing_lib_noop(self):
        if SKIP_TESTS:
            return
        moddb_url = 'https://www.moddb.com/downloads/mirror/somethingsomething'
        hlpr = ModDB(moddb_lib=None)
        transformed = hlpr.transform_url(moddb_url)
        self.assertEqual(transformed, moddb_url)

    # transform_url
    def test_transform_url_url_is_mirror_with_www_throws(self):
        if SKIP_TESTS:
            return
        moddb_url = 'https://www.moddb.com/downloads/mirror/somethingsomething'
        with self.assertRaises(RuntimeError):
            self.helper_obj.transform_url(moddb_url)

    def test_transform_url_url_is_mirror_no_www_throws(self):
        if SKIP_TESTS:
            return
        moddb_url = 'https://moddb.com/downloads/mirror/somethingsomething'
        with self.assertRaises(RuntimeError):
            self.helper_obj.transform_url(moddb_url)

    def test_transform_url_url_match_happy_path(self):
        if SKIP_TESTS:
            return
        self \
            .with_mirror("/first_url", 12.4)

        moddb_url = 'https://moddb.com'
        transformed = self.helper_obj.transform_url(moddb_url)
        self.assertEqual(transformed, 'https://www.moddb.com/first_url')

    def test_transform_url_url_not_match_throws(self):
        if SKIP_TESTS:
            return
        self \
            .with_mirror("/first_url", 12.4)
        moddb_url = 'https://not_moddb.com'
        with self.assertRaises(RuntimeError):
            self.helper_obj.transform_url(moddb_url)

    def test_transform_url_page_type_correct_happy_path(self):
        if SKIP_TESTS:
            return
        self \
            .with_mirror("/first_url", 12.4) \
            .with_page_type(self.ModDBFileObj)
        moddb_url = 'https://moddb.com'
        transformed = self.helper_obj.transform_url(moddb_url)
        self.assertEqual(transformed, 'https://www.moddb.com/first_url')

    def test_transform_url_page_type_incorrect_throws(self):
        if SKIP_TESTS:
            return
        self \
            .with_mirror("/first_url", 12.4) \
            .with_page_type(self.ModDBSomeOtherObj)
        moddb_url = 'https://moddb.com'
        with self.assertRaises(RuntimeError):
            self.helper_obj.transform_url(moddb_url)

    def test_transform_url_single_mirror_happy_path(self):
        if SKIP_TESTS:
            return
        self \
            .with_mirror("/first_url", 12.4)
        moddb_url = 'https://moddb.com'
        transformed = self.helper_obj.transform_url(moddb_url)
        self.assertEqual(transformed, 'https://www.moddb.com/first_url')

    def test_transform_url_multiple_mirror_select_lowest_capacity(self):
        if SKIP_TESTS:
            return
        self \
            .with_mirror("/first_url", 12.4) \
            .with_mirror("/second_url", 57.4) \
            .with_mirror("/lowest_load", 0)
        moddb_url = 'https://moddb.com'
        transformed = self.helper_obj.transform_url(moddb_url)
        self.assertEqual(transformed, 'https://www.moddb.com/lowest_load')

    def test_transform_url_no_mirrors_throws(self):
        if SKIP_TESTS:
            return
        moddb_url = 'https://moddb.com'
        with self.assertRaises(RuntimeError):
            self.helper_obj.transform_url(moddb_url)

    # is_moddb_url
    def test_is_moddb_url_has_www_success(self):
        if SKIP_TESTS:
            return
        url = 'https://www.moddb.com/something'
        self.assertTrue(is_moddb_url(url))

    def test_is_moddb_url_no_slug_has_www_success(self):
        if SKIP_TESTS:
            return
        url = 'https://www.moddb.com'
        self.assertTrue(is_moddb_url(url))

    def test_is_moddb_url_no_www_success(self):
        if SKIP_TESTS:
            return
        url = 'https://moddb.com/something'
        self.assertTrue(is_moddb_url(url))

    def test_is_moddb_url_no_slug_no_www_success(self):
        if SKIP_TESTS:
            return
        url = 'https://moddb.com'
        self.assertTrue(is_moddb_url(url))

    def test_is_moddb_url_other_subdomain_failure(self):
        if SKIP_TESTS:
            return
        url = 'https://subdomain.moddb.com/something'
        self.assertFalse(is_moddb_url(url))

    def test_is_moddb_url_no_slug_other_subdomain_failure(self):
        if SKIP_TESTS:
            return
        url = 'https://subdomain.moddb.com'
        self.assertFalse(is_moddb_url(url))

    def test_is_moddb_url_random_domain_failure(self):
        if SKIP_TESTS:
            return
        url = 'https://somedomain.com/something'
        self.assertFalse(is_moddb_url(url))

    def test_is_moddb_url_no_slug_random_domain_failure(self):
        if SKIP_TESTS:
            return
        url = 'https://somedomain.com'
        self.assertFalse(is_moddb_url(url))
