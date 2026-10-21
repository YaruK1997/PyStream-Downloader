"""Unit tests for src.cli argument parsing and interactive selections."""

import unittest

from src import __version__
from src.cli import parse_arguments


class TestCLI(unittest.TestCase):
    """Test CLI argument parsing and default fallbacks."""

    def test_parse_arguments_defaults(self):
        args = parse_arguments(["https://example.com/live"])
        self.assertEqual(args.url, "https://example.com/live")
        self.assertEqual(args.output, "./downloads")
        self.assertEqual(args.poll_interval, 15)
        self.assertEqual(args.max_retries, 5)
        self.assertFalse(args.wait)
        self.assertFalse(args.no_pause)
        self.assertEqual(args.impersonate, "chrome")
        self.assertIsNone(args.cookies_from_browser)

    def test_parse_arguments_custom(self):
        custom = [
            "https://example.com/live",
            "-q", "720p",
            "-o", "D:/Recordings",
            "--wait",
            "--poll-interval", "30",
            "--max-retries", "10",
            "--no-pause",
            "--impersonate", "firefox",
            "--cookies-from-browser", "chrome",
        ]
        args = parse_arguments(custom)
        self.assertEqual(args.quality, "720p")
        self.assertEqual(args.output, "D:/Recordings")
        self.assertTrue(args.wait)
        self.assertEqual(args.poll_interval, 30)
        self.assertEqual(args.max_retries, 10)
        self.assertTrue(args.no_pause)
        self.assertEqual(args.impersonate, "firefox")
        self.assertEqual(args.cookies_from_browser, "chrome")

    def test_version_string(self):
        self.assertEqual(__version__, "1.1.0")


if __name__ == "__main__":
    unittest.main()
