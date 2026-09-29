"""Tests for the Steam Family service."""

import unittest

from lutris.services.steamfamily import SteamFamilyService


class TestSteamFamilyAccessToken(unittest.TestCase):
    def test_extract_access_token(self):
        self.assertEqual(
            SteamFamilyService.extract_access_token({"data": {"webapi_token": "test-token"}}),
            "test-token",
        )

    def test_extract_access_token_rejects_invalid_payloads(self):
        invalid_payloads = [
            [],
            {"data": []},
            {"data": {}},
            {"data": {"webapi_token": 123}},
            {"response": {"webapi_token": "test-token"}},
        ]

        for token_data in invalid_payloads:
            with self.subTest(token_data=token_data):
                self.assertEqual(SteamFamilyService.extract_access_token(token_data), "")
