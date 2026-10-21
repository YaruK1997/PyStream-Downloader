"""Unit tests for src.sniffer (TC-SN-01, TC-SN-02)."""

import unittest
from unittest.mock import MagicMock, patch

from src.sniffer import HeadlessStreamSniffer, SniffResult


class TestSniffer(unittest.TestCase):
    """Test HeadlessStreamSniffer (The Stream Detector Engine)."""

    def test_sniffer_initialization_and_availability(self):
        sniffer = HeadlessStreamSniffer(timeout=10, headless=True)
        self.assertEqual(sniffer.timeout, 10)
        self.assertTrue(sniffer.headless)
        self.assertTrue(sniffer.is_available())

    def test_sniff_result_dataclass(self):
        result = SniffResult(
            stream_url="https://example.com/playlist.m3u8",
            headers={"User-Agent": "TestBrowser"},
            title="Sample Video",
            detected_streams=["https://example.com/playlist.m3u8"],
        )
        self.assertEqual(result.stream_url, "https://example.com/playlist.m3u8")
        self.assertEqual(result.headers["User-Agent"], "TestBrowser")
        self.assertEqual(result.title, "Sample Video")
        self.assertEqual(len(result.detected_streams), 1)

    def test_sniffer_mock_request_interception(self):
        sniffer = HeadlessStreamSniffer(timeout=5)

        mock_p = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        mock_page.title.return_value = "Intercepted Title"

        captured_callback = None

        def mock_on(event, callback):
            nonlocal captured_callback
            if event == "request":
                captured_callback = callback

        mock_page.on.side_effect = mock_on

        def mock_goto(*args, **kwargs):
            mock_req1 = MagicMock()
            mock_req1.url = "https://cdn.example.com/api/track"
            mock_req1.headers = {"User-Agent": "UA"}

            mock_req2 = MagicMock()
            mock_req2.url = "https://cdn.example.com/media/playlist.m3u8?token=xyz"
            mock_req2.headers = {"User-Agent": "SniffedUA", "Referer": "https://example.com"}

            if captured_callback:
                captured_callback(mock_req1)
                captured_callback(mock_req2)

        mock_page.goto.side_effect = mock_goto

        with patch("playwright.sync_api.sync_playwright") as mock_sp:
            mock_sp.return_value.__enter__.return_value = mock_p
            res = sniffer.sniff("https://example.com/video")
            self.assertIsNotNone(res)
            self.assertIn("playlist.m3u8", res.stream_url)
            self.assertEqual(res.headers.get("Referer"), "https://example.com")
            self.assertEqual(res.title, "Intercepted Title")

    def test_sniffer_missing_playwright_error(self):
        sniffer = HeadlessStreamSniffer()
        with patch.dict("sys.modules", {"playwright.sync_api": None}):
            with self.assertRaises(ImportError):
                sniffer.sniff("https://example.com")


if __name__ == "__main__":
    unittest.main()

