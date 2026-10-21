"""Unit tests for src.downloader (TC-DL-01, TC-DL-02, TC-DL-03)."""

import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
