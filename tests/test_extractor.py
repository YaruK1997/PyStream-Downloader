"""Unit tests for src.extractor (TC-EX-01, TC-EX-02, TC-EX-03, TC-EX-04, TC-EX-05)."""

import unittest
from unittest.mock import MagicMock, patch

from src.extractor import StreamExtractor
from src.sniffer import SniffResult


class TestExtractor(unittest.TestCase):
    """Test extractor logic, format prioritization, anti-bot impersonation, and sniffer fallback."""

    def test_extract_formats_sorting(self):
        extractor = StreamExtractor("https://example.com/test_video")
        mock_raw = {
            "title": "Sample 4K Stream",
            "formats": [
                {"format_id": "4k", "height": 2160, "vcodec": "av01", "acodec": "opus", "tbr": 15000, "url": "http://4k.m3u8"},
                {"format_id": "1080p", "height": 1080, "vcodec": "avc1", "acodec": "mp4a", "tbr": 5000, "url": "http://1080p.m3u8"},
                {"format_id": "720p", "height": 720, "vcodec": "avc1", "acodec": "mp4a", "tbr": 2500, "url": "http://720p.m3u8"},
                {"format_id": "audio", "height": None, "vcodec": "none", "acodec": "mp4a", "tbr": 128, "url": "http://audio.m3u8"},
            ],
        }
        extractor._raw_info = mock_raw

        formats = extractor.get_available_formats()
        # Audio-only should be filtered out from video resolutions
        self.assertEqual(len(formats), 3)
        self.assertEqual(formats[0]["resolution"], "2160p")
        self.assertEqual(formats[1]["resolution"], "1080p")
        self.assertEqual(formats[2]["resolution"], "720p")

    def test_resolve_stream_url_explicit_and_default(self):
        extractor = StreamExtractor("https://example.com/test_video")
        extractor._raw_info = {
            "title": "Sample Stream",
            "http_headers": {"User-Agent": "TestUA/1.0", "Referer": "https://example.com/"},
            "formats": [
                {"format_id": "1080p", "height": 1080, "vcodec": "avc1", "url": "http://1080p.m3u8"},
                {"format_id": "720p", "height": 720, "vcodec": "avc1", "url": "http://720p.m3u8"},
            ],
        }

        # Resolve explicit
        url, label = extractor.resolve_stream_url("720p")
        self.assertEqual(url, "http://720p.m3u8")
        self.assertEqual(label, "720p")

        # Resolve default (best)
        url_best, label_best = extractor.resolve_stream_url(None)
        self.assertEqual(url_best, "http://1080p.m3u8")
        self.assertEqual(label_best, "1080p")

    def test_resolve_stream_details_with_headers(self):
        extractor = StreamExtractor("https://example.com/test_video")
        headers = {"User-Agent": "CustomUA", "Referer": "https://example.com"}
        extractor._raw_info = {
            "title": "Stream With Headers",
            "formats": [
                {
                    "format_id": "1080p",
                    "height": 1080,
                    "vcodec": "avc1",
                    "url": "http://1080p.m3u8",
                    "http_headers": headers,
                }
            ],
        }

        url, quality, res_headers = extractor.resolve_stream_details("1080p")
        self.assertEqual(url, "http://1080p.m3u8")
        self.assertEqual(quality, "1080p")
        self.assertEqual(res_headers, headers)

    def test_impersonate_and_cookies_ydl_opts(self):
        extractor = StreamExtractor(
            "https://example.com/test",
            impersonate="chrome",
            cookies_from_browser="firefox",
        )
        opts = extractor._build_ydl_opts()
        self.assertIn("impersonate", opts)
        self.assertIn("extractor_args", opts)
        self.assertEqual(opts["extractor_args"]["generic"]["impersonate"], ["chrome"])
        self.assertEqual(opts["cookiesfrombrowser"], ("firefox", None, None, None))

    def test_impersonate_disabled(self):
        extractor = StreamExtractor("https://example.com/test", impersonate="none")
        opts = extractor._build_ydl_opts()
        self.assertNotIn("impersonate", opts)
        self.assertNotIn("extractor_args", opts)

    def test_unsupported_url_triggers_sniffer_auto_fallback(self):
        extractor = StreamExtractor("https://missav.ai/gvh-852", sniff_mode="auto")
        mock_sniff_result = SniffResult(
            stream_url="https://surrit.com/media/playlist.m3u8",
            headers={"User-Agent": "SniffedUA", "Referer": "https://missav.ai/"},
            title="MissAV Sniffed Title",
            detected_streams=["https://surrit.com/media/playlist.m3u8"],
        )

        with patch("src.sniffer.HeadlessStreamSniffer.is_available", return_value=True):
            with patch("src.sniffer.HeadlessStreamSniffer.sniff", return_value=mock_sniff_result):
                with patch("yt_dlp.YoutubeDL.extract_info", side_effect=Exception("ERROR: Unsupported URL")):
                    info = extractor.extract_metadata()
                    self.assertIsNotNone(info)
                    self.assertEqual(info["url"], "https://surrit.com/media/playlist.m3u8")
                    self.assertEqual(info["title"], "MissAV Sniffed Title")
                    self.assertEqual(info["http_headers"]["Referer"], "https://missav.ai/")

    def test_sniff_mode_never_re_raises_unsupported_url(self):
        extractor = StreamExtractor("https://missav.ai/gvh-852", sniff_mode="never")
        with patch("yt_dlp.YoutubeDL.extract_info", side_effect=Exception("ERROR: Unsupported URL")):
            with self.assertRaises(Exception):
                extractor.extract_metadata()

    def test_extractor_missing_ytdlp_error(self):
        extractor = StreamExtractor("https://example.com/test")
        with patch.dict("sys.modules", {"yt_dlp": None}):
            with self.assertRaises(ImportError):
                extractor._ensure_ytdlp()


if __name__ == "__main__":
    unittest.main()
