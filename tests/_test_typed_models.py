import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import msgspec

from lutris import api
from lutris.database import saved_searches


class TestSavedSearchRow(unittest.TestCase):
    def test_row_is_converted_to_typed_object(self):
        search = saved_searches._create_search({"id": 3, "name": "Installed", "search": "installed:yes"})
        self.assertEqual(search, saved_searches.SavedSearch(3, "Installed", "installed:yes"))
        self.assertEqual(search.saved_search_id, 3)

    def test_wrong_type_is_rejected(self):
        with self.assertRaises(msgspec.ValidationError):
            saved_searches._create_search({"id": "x", "name": "Installed", "search": "installed:yes"})

    def test_missing_column_is_rejected(self):
        with self.assertRaises(msgspec.ValidationError):
            saved_searches._create_search({"id": 3, "name": "Installed"})


class TestApiTypes(unittest.TestCase):
    def test_read_api_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            key_path = os.path.join(tmp, "auth-token")
            with open(key_path, "w", encoding="utf-8") as key_file:
                key_file.write("someone:secret")
            with patch.object(api, "API_KEY_FILE_PATH", key_path):
                credentials = api.read_api_key()
        self.assertEqual(credentials, api.ApiCredentials(username="someone", token="secret"))

    def test_malformed_api_key_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            key_path = os.path.join(tmp, "auth-token")
            with open(key_path, "w", encoding="utf-8") as key_file:
                key_file.write("no-separator")
            with patch.object(api, "API_KEY_FILE_PATH", key_path):
                self.assertIsNone(api.read_api_key())

    def test_token_response_requires_a_string_token(self):
        self.assertEqual(msgspec.convert({"token": "abc", "extra": 1}, api.TokenResponse).token, "abc")
        for payload in ({}, {"token": 5}, ["token"]):
            with self.assertRaises(msgspec.ValidationError):
                msgspec.convert(payload, api.TokenResponse)

    def test_connect_warns_about_an_answer_without_token(self):
        response = MagicMock()
        response.json.return_value = {"detail": "nope"}
        with patch.object(api.requests, "post", return_value=response), patch.object(api.logger, "warning") as warning:
            self.assertIsNone(api.connect("someone", "password"))
        warning.assert_called_once()
        self.assertIn("Unexpected answer", warning.call_args.args[0])
