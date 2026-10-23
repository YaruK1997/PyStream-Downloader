"""Unit tests for src.supervisor (TC-SV-01, TC-SV-02)."""

import unittest
from unittest.mock import MagicMock, patch

from src.downloader import FFmpegDownloader
from src.supervisor import ProcessSupervisor


class TestSupervisor(unittest.TestCase):
    """Test process supervisor retries, pause/resume, and process lifecycle."""

    def test_pause_resume_state_machine(self):
        downloader = FFmpegDownloader("url", "out.mp4")
        supervisor = ProcessSupervisor(downloader)

        # Mock process
        mock_proc = MagicMock()
        mock_proc.pid = 1234
        supervisor.current_process = mock_proc

        mock_psutil = MagicMock()
        mock_psutil_proc = MagicMock()
        mock_psutil.Process.return_value = mock_psutil_proc

        with patch.object(supervisor, "_get_psutil", return_value=mock_psutil):
            # Initially running
            self.assertFalse(supervisor.is_paused)

            # Pause
            self.assertTrue(supervisor.pause())
            self.assertTrue(supervisor.is_paused)
            mock_psutil_proc.suspend.assert_called_once()

            # Second pause call should be ignored
            self.assertFalse(supervisor.pause())

            # Resume
            self.assertTrue(supervisor.resume())
            self.assertFalse(supervisor.is_paused)
            mock_psutil_proc.resume.assert_called_once()

            # Second resume call should be ignored
            self.assertFalse(supervisor.resume())

    def test_supervisor_crash_and_max_retries(self):
        downloader = FFmpegDownloader("url", "out.mp4")
        supervisor = ProcessSupervisor(downloader, max_retries=2)

        # Mock downloader.start_process returning a failing process
        mock_failing_proc = MagicMock()
        mock_failing_proc.stderr = iter([])
        mock_failing_proc.wait.return_value = 1  # Crash exit code

        with patch.object(downloader, "start_process", return_value=mock_failing_proc):
            with patch("time.sleep"):  # Speed up test by bypassing sleep
                success = supervisor.run(enable_hotkey=False)
                self.assertFalse(success)
                # Verify it attempted max_retries + 1 times (initial + 2 retries = 3 attempts)
                self.assertEqual(downloader.start_process.call_count, 3)

    def test_supervisor_normal_exit(self):
        downloader = FFmpegDownloader("url", "out.mp4")
        supervisor = ProcessSupervisor(downloader, max_retries=3)

        mock_success_proc = MagicMock()
        mock_success_proc.stderr = iter(["time=00:00:10.00"])
        mock_success_proc.wait.return_value = 0  # Success exit code

        with patch.object(downloader, "start_process", return_value=mock_success_proc):
            success = supervisor.run(enable_hotkey=False)
            self.assertTrue(success)
            self.assertEqual(downloader.start_process.call_count, 1)


if __name__ == "__main__":
    unittest.main()
