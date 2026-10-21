"""Self-verification test suite for Stage 2 (Architecture & Implementation).

Runs isolated unit and functional self-checks across all Stage 2 modules.
Outputs test assertions and generates logs for docs/self_check.log.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.downloader import FFmpegDownloader
from src.extractor import StreamExtractor
from src.supervisor import ProcessSupervisor
from src.utils import sanitize_filename, verify_mp4_integrity
from src.watcher import StreamWatcher


class TestStage2SelfCheck(unittest.TestCase):
    """Stage 2 self-verification test cases."""

    def test_01_sanitize_filename(self):
        """Verify filename sanitization across special characters."""
        raw = '  Test / Video : Live * Stream ? <2026> | "New" .mp4  '
        clean = sanitize_filename(raw)
        self.assertNotIn("/", clean)
        self.assertNotIn(":", clean)
        self.assertNotIn("*", clean)
        self.assertNotIn("?", clean)
        self.assertNotIn("<", clean)
        self.assertNotIn(">", clean)
        self.assertNotIn("|", clean)
        self.assertNotIn('"', clean)
        self.assertTrue(len(clean) > 0)
        # Empty fallback
        self.assertEqual(sanitize_filename(""), "downloaded_video")
        self.assertEqual(sanitize_filename(":::"), "downloaded_video")

    def test_02_mp4_integrity_checker(self):
        """Verify MP4 container header validation."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            tf_path = tf.name
            # Write a mock MP4 header containing ftyp box (36 bytes + padding)
            tf.write(b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2mp41\x00\x00\x00\x08free" + b"\x00" * 32)
            tf.flush()

        try:
            self.assertTrue(verify_mp4_integrity(tf_path))
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

        # Test non-existent file
        self.assertFalse(verify_mp4_integrity("non_existent_file.mp4"))

        # Test empty file
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf_empty:
            empty_path = tf_empty.name
        try:
            self.assertFalse(verify_mp4_integrity(empty_path))
        finally:
            if os.path.exists(empty_path):
                os.remove(empty_path)

    def test_03_ffmpeg_command_builder(self):
        """Verify FFmpeg command assembly with reconnection parameters."""
        downloader = FFmpegDownloader(
            stream_url="https://example.com/live/master.m3u8",
            output_path="C:/Downloads/video.mp4",
        )
        cmd = downloader.build_command()
        self.assertEqual(cmd[0], "ffmpeg")
        self.assertIn("-reconnect", cmd)
        self.assertIn("1", cmd)
        self.assertIn("-reconnect_streamed", cmd)
        self.assertIn("-c", cmd)
        self.assertIn("copy", cmd)
        self.assertIn("-movflags", cmd)
        self.assertIn("+faststart", cmd)
        self.assertEqual(cmd[-1], "C:/Downloads/video.mp4")

    def test_04_progress_parsing(self):
        """Verify regex parsing of FFmpeg progress output."""
        downloader = FFmpegDownloader("url", "out.mp4")
        line = "frame=  120 fps= 30 q=-1.0 size=   15360kB time=00:01:42.50 bitrate=1228.8kbits/s speed=1.02x"
        prog = downloader.parse_progress(line)
        self.assertIsNotNone(prog)
        self.assertEqual(prog["time"], "00:01:42.50")
        self.assertEqual(prog["speed"], "1.02x")
        self.assertEqual(prog["bitrate"], "1228.8kbits/s")

    def test_05_extractor_format_filtering(self):
        """Verify format parsing and sorting by resolution."""
        extractor = StreamExtractor("https://example.com/video")
        mock_info = {
            "title": "Mock Live Stream",
            "formats": [
                {"format_id": "137", "height": 1080, "vcodec": "avc1", "acodec": "mp4a", "tbr": 4500, "url": "http://1080p.m3u8"},
                {"format_id": "136", "height": 720, "vcodec": "avc1", "acodec": "mp4a", "tbr": 2500, "url": "http://720p.m3u8"},
                {"format_id": "140", "height": None, "vcodec": "none", "acodec": "mp4a", "tbr": 128, "url": "http://audio.m3u8"},
            ]
        }
        extractor._raw_info = mock_info
        formats = extractor.get_available_formats()
        self.assertEqual(len(formats), 2)
        self.assertEqual(formats[0]["resolution"], "1080p")
        self.assertEqual(formats[1]["resolution"], "720p")

        url, res = extractor.resolve_stream_url("720p")
        self.assertEqual(url, "http://720p.m3u8")
        self.assertEqual(res, "720p")

    def test_06_watcher_status_transitions(self):
        """Verify stream watcher status detection logic."""
        watcher = StreamWatcher("https://example.com/upcoming", poll_interval=5)
        # Mocking yt_dlp extract_info
        mock_ytdlp = MagicMock()
        mock_ytdlp.YoutubeDL.return_value.__enter__.return_value.extract_info.return_value = {
            "live_status": "is_upcoming",
            "title": "Upcoming Stream"
        }
        with patch.dict("sys.modules", {"yt_dlp": mock_ytdlp}):
            is_live, status, info = watcher.check_status()
            self.assertFalse(is_live)
            self.assertEqual(status, "upcoming")

        # Now mock live status
        mock_ytdlp.YoutubeDL.return_value.__enter__.return_value.extract_info.return_value = {
            "live_status": "is_live",
            "title": "Live Now"
        }
        with patch.dict("sys.modules", {"yt_dlp": mock_ytdlp}):
            is_live, status, info = watcher.check_status()
            self.assertTrue(is_live)
            self.assertEqual(status, "live")

    def test_07_supervisor_pause_resume_mock(self):
        """Verify supervisor pause and resume toggling."""
        downloader = FFmpegDownloader("url", "out.mp4")
        supervisor = ProcessSupervisor(downloader)

        # Mock current process
        mock_proc = MagicMock()
        mock_proc.pid = 99999
        supervisor.current_process = mock_proc

        # Mock psutil
        mock_psutil = MagicMock()
        mock_psutil_proc = MagicMock()
        mock_psutil.Process.return_value = mock_psutil_proc

        with patch.object(supervisor, "_get_psutil", return_value=mock_psutil):
            self.assertFalse(supervisor.is_paused)
            self.assertTrue(supervisor.pause())
            self.assertTrue(supervisor.is_paused)
            mock_psutil_proc.suspend.assert_called_once()

            self.assertTrue(supervisor.resume())
            self.assertFalse(supervisor.is_paused)
            mock_psutil_proc.resume.assert_called_once()


if __name__ == "__main__":
    unittest.main()
