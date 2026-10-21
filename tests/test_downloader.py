"""Unit tests for src.downloader (TC-DL-01, TC-DL-02, TC-DL-03)."""

import unittest
from unittest.mock import MagicMock, patch

from src.downloader import FFmpegDownloader


class TestDownloader(unittest.TestCase):
    """Test FFmpeg command line builder, progress regex parsing, and header injection defense."""

    def test_build_command_structure(self):
        dl = FFmpegDownloader("http://stream.m3u8", "C:/output/video.mp4")
        cmd = dl.build_command()

        self.assertEqual(cmd[0], "ffmpeg")
        self.assertIn("-reconnect", cmd)
        self.assertIn("-reconnect_streamed", cmd)
        self.assertIn("-reconnect_delay_max", cmd)
        self.assertIn("-c", cmd)
        self.assertIn("copy", cmd)
        self.assertIn("-movflags", cmd)
        self.assertIn("+faststart", cmd)
        self.assertEqual(cmd[-1], "C:/output/video.mp4")

    def test_build_command_with_headers(self):
        headers = {
            "User-Agent": "Mozilla/5.0 TestBrowser",
            "Referer": "https://stream.example.com/",
        }
        dl = FFmpegDownloader("http://stream.m3u8", "C:/output/video.mp4", headers=headers)
        cmd = dl.build_command()

        self.assertIn("-headers", cmd)
        idx = cmd.index("-headers")
        header_payload = cmd[idx + 1]
        self.assertIn("User-Agent: Mozilla/5.0 TestBrowser\r\n", header_payload)
        self.assertIn("Referer: https://stream.example.com/\r\n", header_payload)
        # Ensure -headers appears before -i
        i_idx = cmd.index("-i")
        self.assertLess(idx, i_idx)

    def test_header_crlf_injection_defense(self):
        # Injected CRLF in value
        with self.assertRaises(ValueError):
            FFmpegDownloader(
                "http://stream.m3u8",
                "out.mp4",
                headers={"User-Agent": "SafeUA\r\nX-Injected-Header: evil"},
            )
        # Injected newline in key
        with self.assertRaises(ValueError):
            FFmpegDownloader(
                "http://stream.m3u8",
                "out.mp4",
                headers={"Bad\nHeader": "Value"},
            )

    def test_parse_progress_normal(self):
        dl = FFmpegDownloader("url", "out.mp4")
        sample_line = "frame=  240 fps= 60 q=-1.0 size=    4096kB time=00:00:15.20 bitrate=2207.9kbits/s speed=1.01x"
        res = dl.parse_progress(sample_line)
        self.assertIsNotNone(res)
        self.assertEqual(res["size"], "4096kB")
        self.assertEqual(res["time"], "00:00:15.20")
        self.assertEqual(res["bitrate"], "2207.9kbits/s")
        self.assertEqual(res["speed"], "1.01x")

    def test_parse_progress_fallback(self):
        dl = FFmpegDownloader("url", "out.mp4")
        sample_line = "Writing header... time=00:00:05.10"
        res = dl.parse_progress(sample_line)
        self.assertIsNotNone(res)
        self.assertEqual(res["time"], "00:00:05.10")

    def test_parse_progress_non_progress(self):
        dl = FFmpegDownloader("url", "out.mp4")
        sample_line = "Input #0, hls, from 'http://example.com/live.m3u8':"
        res = dl.parse_progress(sample_line)
        self.assertIsNone(res)

    def test_missing_ffmpeg_raises_error(self):
        dl = FFmpegDownloader("url", "out.mp4")
        with patch.object(dl, "is_ffmpeg_available", return_value=False):
            with self.assertRaises(FileNotFoundError):
                dl.start_process()

    def test_argument_injection_prevention(self):
        with self.assertRaises(ValueError):
            FFmpegDownloader("-preset ultrafast", "out.mp4")
        with self.assertRaises(ValueError):
            FFmpegDownloader("", "out.mp4")

    def test_build_command_with_separate_audio_aac(self):
        dl = FFmpegDownloader(
            stream_url="http://video.m3u8",
            output_path="C:/output/video.mp4",
            headers={"User-Agent": "VideoUA"},
            audio_url="http://audio.m3u8",
            audio_headers={"User-Agent": "AudioUA"},
            audio_codec="mp4a.40.2",
        )
        cmd = dl.build_command()

        # Both inputs should be present
        self.assertEqual(cmd.count("-i"), 2)
        idx_v = cmd.index("-i")
        self.assertEqual(cmd[idx_v + 1], "http://video.m3u8")
        idx_a = cmd.index("-i", idx_v + 2)
        self.assertEqual(cmd[idx_a + 1], "http://audio.m3u8")

        # Mapping
        self.assertIn("-map", cmd)
        self.assertIn("0:v:0", cmd)
        self.assertIn("1:a:0", cmd)

        # Video copy, AAC audio copy
        self.assertIn("-c:v", cmd)
        self.assertIn("-c:a", cmd)
        a_idx = cmd.index("-c:a")
        self.assertEqual(cmd[a_idx + 1], "copy")
        self.assertIn("-bsf:a", cmd)
        self.assertIn("aac_adtstoasc", cmd)

        # Sync flags
        self.assertIn("-fflags", cmd)
        self.assertIn("+genpts", cmd)
        self.assertIn("-avoid_negative_ts", cmd)
        self.assertIn("make_zero", cmd)
        self.assertIn("-max_interleave_delta", cmd)
        self.assertIn("0", cmd)
        self.assertIn("-shortest", cmd)

    def test_build_command_with_separate_audio_opus_into_mp4(self):
        dl = FFmpegDownloader(
            stream_url="http://video.m3u8",
            output_path="C:/output/video.mp4",
            audio_url="http://audio_opus.webm",
            audio_codec="opus",
        )
        cmd = dl.build_command()

        # Non-AAC into MP4 should transcode to AAC with resample sync
        self.assertIn("-c:a", cmd)
        a_idx = cmd.index("-c:a")
        self.assertEqual(cmd[a_idx + 1], "aac")
        self.assertIn("-b:a", cmd)
        self.assertEqual(cmd[cmd.index("-b:a") + 1], "192k")
        self.assertIn("-af", cmd)
        self.assertIn("aresample=async=1:first_pts=0", cmd)

    def test_audio_argument_injection_defense(self):
        with self.assertRaises(ValueError):
            FFmpegDownloader(
                stream_url="http://valid.com",
                output_path="out.mp4",
                audio_url="-i malicious",
            )

    def test_is_hls_url_detection(self):
        self.assertTrue(FFmpegDownloader.is_hls_url("https://example.com/playlist.m3u8"))
        self.assertTrue(FFmpegDownloader.is_hls_url("https://example.com/live/master.m3u8?token=xyz"))
        self.assertTrue(FFmpegDownloader.is_hls_url("https://example.com/stream_m3u8"))
        self.assertFalse(FFmpegDownloader.is_hls_url("https://example.com/video.mp4"))
        self.assertFalse(FFmpegDownloader.is_hls_url("https://example.com/audio.webm"))
        self.assertFalse(FFmpegDownloader.is_hls_url(""))
        self.assertFalse(FFmpegDownloader.is_hls_url(None))

    def test_hls_stream_omits_reconnect_at_eof(self):
        dl = FFmpegDownloader("https://example.com/video.m3u8", "out.mp4")
        cmd = dl.build_command()
        self.assertNotIn("-reconnect_at_eof", cmd)

    def test_non_hls_stream_includes_reconnect_at_eof(self):
        dl = FFmpegDownloader("https://example.com/live_stream.ts", "out.mp4")
        cmd = dl.build_command()
        self.assertIn("-reconnect_at_eof", cmd)
        self.assertIn("1", cmd)

    def test_get_ffmpeg_hls_options_mocked(self):
        from src.downloader import get_ffmpeg_hls_options

        mock_help = (
            "Demuxer hls [Apple HTTP Live Streaming]:\n"
            "  -allowed_extensions <string>\n"
            "  -allowed_segment_extensions <string>\n"
            "  -extension_picky <boolean>\n"
        )
        with patch("subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_proc.stdout = mock_help
            mock_proc.stderr = ""
            mock_run.return_value = mock_proc

            # Clear cache for testing
            get_ffmpeg_hls_options.cache_clear()
            opts = get_ffmpeg_hls_options()

            self.assertIn("-allowed_segment_extensions", opts)
            self.assertIn("ALL", opts)
            self.assertIn("-extension_picky", opts)
            self.assertIn("0", opts)
            self.assertIn("-allowed_extensions", opts)
            get_ffmpeg_hls_options.cache_clear()


if __name__ == "__main__":
    unittest.main()
