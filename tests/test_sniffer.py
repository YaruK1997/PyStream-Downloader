"""Unit tests for src.sniffer (TC-SN-01, TC-SN-02)."""

import unittest
from unittest.mock import MagicMock, patch

from src.sniffer import HeadlessStreamSniffer, SniffResult, sanitize_locale


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

    def test_sniffer_sanitize_locale(self):
        self.assertEqual(sanitize_locale("zh-TW"), "zh-TW")
        self.assertEqual(sanitize_locale("zh-TW,zh;q=0.9,en-US;q=0.8"), "zh-TW")
        self.assertEqual(sanitize_locale("en-US;q=0.8"), "en-US")
        self.assertEqual(sanitize_locale(None), "zh-TW")
        self.assertEqual(sanitize_locale(""), "zh-TW")
        self.assertEqual(sanitize_locale("ja-JP$!@"), "ja-JP")

    def test_sniffer_context_locale_and_headers(self):
        sniffer = HeadlessStreamSniffer(timeout=5)
        mock_p = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        with patch("playwright.sync_api.sync_playwright") as mock_sp:
            mock_sp.return_value.__enter__.return_value = mock_p
            sniffer.sniff("https://example.com")

            # Check new_context call kwargs
            call_kwargs = mock_browser.new_context.call_args[1]
            self.assertEqual(call_kwargs["locale"], "zh-TW")
            self.assertIn("Accept-Language", call_kwargs["extra_http_headers"])
            self.assertIn("zh-TW", call_kwargs["extra_http_headers"]["Accept-Language"])

    def test_sniffer_locale_fallback_on_protocol_error(self):
        sniffer = HeadlessStreamSniffer(timeout=5)
        mock_p = MagicMock()
        mock_browser = MagicMock()
        mock_ctx1 = MagicMock()
        mock_ctx2 = MagicMock()
        mock_page2 = MagicMock()
        mock_p.chromium.launch.return_value = mock_browser

        # First call new_page fails with Protocol error (Emulation.setLocaleOverride)
        mock_ctx1.new_page.side_effect = Exception("Protocol error (Emulation.setLocaleOverride): Invalid locale name")
        mock_ctx2.new_page.return_value = mock_page2
        mock_browser.new_context.side_effect = [mock_ctx1, mock_ctx2]

        with patch("playwright.sync_api.sync_playwright") as mock_sp:
            mock_sp.return_value.__enter__.return_value = mock_p
            sniffer.sniff("https://example.com")

            # Second new_context should have locale popped
            second_call_kwargs = mock_browser.new_context.call_args_list[1][1]
            self.assertNotIn("locale", second_call_kwargs)
            self.assertIn("extra_http_headers", second_call_kwargs)

    def test_sniffer_stealth_and_player_activation(self):
        """Verify stealth script injection and player activation triggers."""
        sniffer = HeadlessStreamSniffer(timeout=5)
        mock_p = MagicMock()
        mock_browser = MagicMock()
        mock_ctx = MagicMock()
        mock_page = MagicMock()
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_ctx
        mock_ctx.new_page.return_value = mock_page

        with patch("playwright.sync_api.sync_playwright") as mock_sp:
            mock_sp.return_value.__enter__.return_value = mock_p
            sniffer.sniff("https://example.com")

            # Verify stealth script injected
            mock_page.add_init_script.assert_called()
            # Verify page.evaluate called for video playback activation
            mock_page.evaluate.assert_called()


if __name__ == "__main__":
    unittest.main()

