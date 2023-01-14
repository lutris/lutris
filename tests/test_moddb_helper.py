import unittest
from lutris.util.moddb import downloadhelper as moddb


class ModDBHelperTests(unittest.TestCase):
  def test_is_moddb_url_has_www_success(self):
    url = 'https://www.moddb.com/something'
    self.assertTrue(moddb.is_moddb_url(url))
  
  def test_is_moddb_url_no_slug_has_www_success(self):
    url = 'https://www.moddb.com'
    self.assertTrue(moddb.is_moddb_url(url))

  def test_is_moddb_url_no_www_success(self):
    url = 'https://moddb.com/something'
    self.assertTrue(moddb.is_moddb_url(url))
  
  def test_is_moddb_url_no_slug_no_www_success(self):
    url = 'https://moddb.com'
    self.assertTrue(moddb.is_moddb_url(url))

  def test_is_moddb_url_other_subdomain_failure(self):
    url = 'https://subdomain.moddb.com/something'
    self.assertFalse(moddb.is_moddb_url(url))
  
  def test_is_moddb_url_no_slug_other_subdomain_failure(self):
    url = 'https://subdomain.moddb.com'
    self.assertFalse(moddb.is_moddb_url(url))

  def test_is_moddb_url_random_domain_failure(self):
    url = 'https://somedomain.com/something'
    self.assertFalse(moddb.is_moddb_url(url))
  
  def test_is_moddb_url_no_slug_random_domain_failure(self):
    url = 'https://somedomain.com'
    self.assertFalse(moddb.is_moddb_url(url))

