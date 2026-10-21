"""Unit tests for src.utils (TC-UT-01, TC-UT-02)."""

import os
import tempfile
import unittest

from src.utils import check_system_dependencies, sanitize_filename, verify_mp4_integrity


class TestUtils(unittest.TestCase):
    """Test utility functions for edge cases and safety."""

    def test_sanitize_filename_standard(self):
        raw = "My Normal Video (2026)"
        self.assertEqual(sanitize_filename(raw), "My Normal Video (2026)")

    def test_sanitize_filename_forbidden_chars(self):
        raw = 'Evil / Video : Name * With ? Forbidden < Chars > | And " Quotes "'
        clean = sanitize_filename(raw)
        for char in '/:*?"<>|\\':
            self.assertNotIn(char, clean)

    def test_sanitize_filename_edge_cases(self):
        # Empty string
        self.assertEqual(sanitize_filename(""), "downloaded_video")
        # Only symbols
        self.assertEqual(sanitize_filename(":::***???"), "downloaded_video")
        # Only spaces and dots
        self.assertEqual(sanitize_filename("   ...   "), "downloaded_video")
        # Long string
        long_name = "A" * 300
        clean_long = sanitize_filename(long_name, max_length=50)
        self.assertEqual(len(clean_long), 50)

    def test_verify_mp4_integrity_valid(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            path = tf.name
            tf.write(b"\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00isommp42" + b"\x00" * 40)
            tf.flush()
        try:
            self.assertTrue(verify_mp4_integrity(path))
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_verify_mp4_integrity_invalid_or_corrupt(self):
        # Non-existent
        self.assertFalse(verify_mp4_integrity("non_existent_12345.mp4"))

        # Too small (< 32 bytes)
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            path = tf.name
            tf.write(b"too small")
            tf.flush()
        try:
            self.assertFalse(verify_mp4_integrity(path))
        finally:
            if os.path.exists(path):
                os.remove(path)

        # Large but pure garbage without any MP4 atom markers
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            path = tf.name
            tf.write(b"\xFF" * 1024)
            tf.flush()
        try:
            self.assertFalse(verify_mp4_integrity(path))
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_check_system_dependencies(self):
        deps = check_system_dependencies()
        self.assertIn("ffmpeg", deps)
        self.assertIn("ffprobe", deps)


if __name__ == "__main__":
    unittest.main()
