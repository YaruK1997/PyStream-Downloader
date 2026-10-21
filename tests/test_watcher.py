"""Unit tests for src.watcher (TC-WA-01, TC-WA-02)."""

import unittest
from unittest.mock import MagicMock, patch

from src.watcher import StreamWatcher


class TestWatcher(unittest.TestCase):
    """Test live stream status watcher, polling, and anti-bot impersonation options."""

    def test_watcher_upcoming_status(self):
        watcher = StreamWatcher("https://example.com/upcoming", poll_interval=5)
        mock_ytdlp = MagicMock()
        mock_ytdlp.YoutubeDL.return_value.__enter__.return_value.extract_info.return_value = {
            "live_status": "is_upcoming",
            "title": "Upcoming Event",
        }

        with patch.dict("sys.modules", {"yt_dlp": mock_ytdlp}):
            is_live, status, info = watcher.check_status()
            self.assertFalse(is_live)
            self.assertEqual(status, "upcoming")
            self.assertEqual(info["title"], "Upcoming Event")

    def test_watcher_is_live_status(self):
        watcher = StreamWatcher("https://example.com/live", poll_interval=5)
        mock_ytdlp = MagicMock()
        mock_ytdlp.YoutubeDL.return_value.__enter__.return_value.extract_info.return_value = {
            "live_status": "is_live",
            "title": "Live Stream Right Now",
        }

        with patch.dict("sys.modules", {"yt_dlp": mock_ytdlp}):
            is_live, status, info = watcher.check_status()
            self.assertTrue(is_live)
            self.assertEqual(status, "live")

    def test_watcher_cancellation(self):
        watcher = StreamWatcher("https://example.com/stream", poll_interval=1)
        watcher.cancel()
        res = watcher.wait_until_live()
        self.assertFalse(res)

    def test_watcher_opts_impersonate_and_cookies(self):
        watcher = StreamWatcher(
            "https://example.com/stream",
            impersonate="chrome",
            cookies_from_browser="edge",
        )
        opts = watcher._build_ydl_opts()
        self.assertIn("impersonate", opts)
        self.assertEqual(opts["cookiesfrombrowser"], ("edge", None, None, None))


if __name__ == "__main__":
    unittest.main()
