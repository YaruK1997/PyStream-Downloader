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

    @patch("src.static_sniffer.StaticPackerSniffer.sniff", return_value=None)
    def test_unsupported_url_triggers_sniffer_auto_fallback(self, mock_static_sniff):
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

    @patch("src.static_sniffer.StaticPackerSniffer.sniff", return_value=None)
    def test_unsupported_url_raises_needs_full_sniffer_when_unavailable(self, mock_static_sniff):
        from src.extractor import NeedsFullSnifferError
        extractor = StreamExtractor("https://missav.ai/gvh-852", sniff_mode="auto")
        with patch("src.sniffer.HeadlessStreamSniffer.is_available", return_value=False):
            with patch("yt_dlp.YoutubeDL.extract_info", side_effect=Exception("ERROR: Unsupported URL")):
                with self.assertRaises(NeedsFullSnifferError):
                    extractor.extract_metadata()

    def test_extractor_missing_ytdlp_error(self):
        extractor = StreamExtractor("https://example.com/test")
        with patch.dict("sys.modules", {"yt_dlp": None}):
            with self.assertRaises(ImportError):
                extractor._ensure_ytdlp()

    def test_separate_audio_stream_matching(self):
        extractor = StreamExtractor("https://example.com/test_video")
        mock_raw = {
            "title": "YouTube 1080p Video",
            "formats": [
                {
                    "format_id": "137",
                    "height": 1080,
                    "vcodec": "avc1.640028",
                    "acodec": "none",
                    "tbr": 4500,
                    "url": "http://video1080.googlevideo.com/videoplayback",
                    "http_headers": {"User-Agent": "VideoUA"},
                },
                {
                    "format_id": "140",
                    "height": None,
                    "vcodec": "none",
                    "acodec": "mp4a.40.2",
                    "ext": "m4a",
                    "abr": 128,
                    "url": "http://audio140.googlevideo.com/videoplayback",
                    "http_headers": {"User-Agent": "AudioUA"},
                },
                {
                    "format_id": "251",
                    "height": None,
                    "vcodec": "none",
                    "acodec": "opus",
                    "ext": "webm",
                    "abr": 160,
                    "url": "http://audio251.googlevideo.com/videoplayback",
                },
            ],
        }
        extractor._raw_info = mock_raw

        formats = extractor.get_available_formats()
        self.assertEqual(len(formats), 1)
        fmt = formats[0]
        self.assertTrue(fmt["has_separate_audio"])
        self.assertEqual(fmt["audio_format_id"], "140")
        self.assertEqual(fmt["audio_url"], "http://audio140.googlevideo.com/videoplayback")
        self.assertEqual(fmt["audio_headers"], {"User-Agent": "AudioUA"})

        # Test resolve_stream_details
        details = extractor.resolve_stream_details("1080p")
        self.assertEqual(details.stream_url, "http://video1080.googlevideo.com/videoplayback")
        self.assertEqual(details.audio_url, "http://audio140.googlevideo.com/videoplayback")
        self.assertEqual(details.audio_codec, "mp4a.40.2")
        self.assertFalse(details.is_muxed)

        # Backwards compatibility: 3-tuple unpacking
        url, q, headers = details
        self.assertEqual(url, "http://video1080.googlevideo.com/videoplayback")
        self.assertEqual(q, "1080p")
        self.assertEqual(headers, {"User-Agent": "VideoUA"})

    def test_muxed_stream_does_not_attach_separate_audio(self):
        extractor = StreamExtractor("https://example.com/test_video")
        mock_raw = {
            "title": "Muxed Stream",
            "formats": [
                {
                    "format_id": "22",
                    "height": 720,
                    "vcodec": "avc1",
                    "acodec": "mp4a",
                    "url": "http://muxed.m3u8",
                }
            ],
        }
        extractor._raw_info = mock_raw
        formats = extractor.get_available_formats()
        self.assertEqual(len(formats), 1)
        self.assertFalse(formats[0]["has_separate_audio"])
        self.assertIsNone(formats[0]["audio_url"])

        details = extractor.resolve_stream_details()
        self.assertTrue(details.is_muxed)
        self.assertIsNone(details.audio_url)

    @patch("src.static_sniffer.StaticPackerSniffer.sniff")
    @patch("src.sniffer.HeadlessStreamSniffer.sniff")
    def test_extractor_static_packer_sniffer_tier2(self, mock_headless, mock_static):
        """Verify Tier 2 static sniffer runs and prevents unnecessary headless browser startup."""
        from src.sniffer import SniffResult
        mock_static.return_value = SniffResult(
            stream_url="https://surrit.com/packed/playlist.m3u8",
            headers={"Referer": "https://packed.com"},
            title="Static Packed Video",
            detected_streams=["https://surrit.com/packed/playlist.m3u8"],
        )
        extractor = StreamExtractor("https://packed.com/video")
        info = extractor._run_sniffer()
        self.assertEqual(info["url"], "https://surrit.com/packed/playlist.m3u8")
        self.assertEqual(info["title"], "Static Packed Video")
        mock_static.assert_called_once()
        mock_headless.assert_not_called()

    @patch("src.static_sniffer.StaticPackerSniffer.sniff")
    @patch("src.sniffer.HeadlessStreamSniffer.sniff")
    @patch("src.sniffer.HeadlessStreamSniffer.is_available")
    def test_extractor_tier2_to_tier3_fallback(self, mock_is_avail, mock_headless, mock_static):
        """Verify fallback from Tier 2 (Static) to Tier 3 (Headless) when static returns None."""
        from src.sniffer import SniffResult
        mock_static.return_value = None
        mock_is_avail.return_value = True
        mock_headless.return_value = SniffResult(
            stream_url="https://headless.com/playlist.m3u8",
            headers={"User-Agent": "Browser"},
            title="Dynamic Video",
            detected_streams=["https://headless.com/playlist.m3u8"],
        )
        extractor = StreamExtractor("https://dynamic.com/video")
        info = extractor._run_sniffer()
        self.assertEqual(info["url"], "https://headless.com/playlist.m3u8")
        mock_static.assert_called_once()
        mock_headless.assert_called_once()


if __name__ == "__main__":
    unittest.main()
