"""Unit tests for StaticPackerSniffer module (TDD Red -> Green)."""

import unittest
from unittest.mock import patch, MagicMock
from src.static_sniffer import StaticPackerSniffer


class TestStaticPackerSniffer(unittest.TestCase):
    """Test StaticPackerSniffer stream extraction and header generation."""

    def setUp(self):
        self.sniffer = StaticPackerSniffer(timeout=10)

    @patch("src.static_sniffer.fetch_page_html")
    def test_sniff_successful_packed_stream(self, mock_fetch):
        """Verify successful stream discovery from packed HTML."""
        sample_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>My Test Video - Streaming Site</title>
            <meta property="og:title" content="My Test Video" />
        </head>
        <body>
            <script>
            eval(function(p,a,c,k,e,d){e=function(c){return c.toString(36)};return p}('0=\\'1://2.3/4/playlist.5\\';6=\\'1://2.3/4/1080p/video.5\\';',7,7,'source|https|surrit|com|test-uuid-999|m3u8|source1080'.split('|'),0,{}))
            </script>
        </body>
        </html>
        """
        mock_fetch.return_value = sample_html

        result = self.sniffer.sniff("https://missav.ai/mukd-572")
        self.assertIsNotNone(result)
        self.assertEqual(result.stream_url, "https://surrit.com/test-uuid-999/playlist.m3u8")
        self.assertEqual(result.title, "My Test Video")
        self.assertIn("Referer", result.headers)
        self.assertEqual(result.headers["Referer"], "https://missav.ai/mukd-572")
        self.assertIn("Origin", result.headers)
        self.assertEqual(result.headers["Origin"], "https://missav.ai")
        self.assertIn("User-Agent", result.headers)
        self.assertEqual(len(result.detected_streams), 2)

    @patch("src.static_sniffer.fetch_page_html")
    def test_sniff_no_stream_returns_none(self, mock_fetch):
        """Verify None returned when page contains no streams."""
        mock_fetch.return_value = "<html><body><h1>No video here</h1></body></html>"
        result = self.sniffer.sniff("https://example.com/no-video")
        self.assertIsNone(result)

    @patch("src.static_sniffer.fetch_page_html")
    def test_sniff_fetch_error_returns_none(self, mock_fetch):
        """Verify network or fetch exceptions are caught and return None."""
        mock_fetch.side_effect = Exception("Connection reset")
        result = self.sniffer.sniff("https://broken.site/video")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()

