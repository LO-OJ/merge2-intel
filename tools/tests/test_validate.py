from __future__ import annotations

import unittest

import validate


class TestValidateHelpers(unittest.TestCase):
    def test_dates(self):
        self.assertTrue(validate.valid_date("2026-11-03"))
        self.assertFalse(validate.valid_date("2026-13-01"))
        self.assertFalse(validate.valid_date("2026/11/03"))

    def test_urls(self):
        self.assertTrue(validate.valid_url("https://example.com/a?b=1"))
        self.assertTrue(validate.valid_url("http://example.com"))
        self.assertFalse(validate.valid_url("javascript:alert(1)"))
        self.assertFalse(validate.valid_url("example.com"))

    def test_secret_pattern(self):
        self.assertTrue(validate.SECRET_RE.search("sk-" + "a" * 24))
        self.assertFalse(validate.SECRET_RE.search("sk-short"))

    def test_clean_entity_keeps_public_fields(self):
        # build.clean is exercised indirectly; validate must not require _file
        game = {"id": "demo", "name": "Demo", "publisher": "X", "role": "self"}
        errors = []
        warnings = []
        validate.validate_games([game], errors, warnings)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
