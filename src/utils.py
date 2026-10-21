"""Utility functions for PyStream-Downloader.

Includes filename sanitization, dependency checking, and MP4 container verification.
"""

import os
import re
import shutil


def sanitize_filename(name: str, max_length: int = 200) -> str:
    """Sanitize a string for safe usage as a file name across Windows, Linux, and macOS.

    Removes invalid characters: \\ / : * ? " < > |
    """
    if not name:
        return "downloaded_video"

    # Replace forbidden characters with underscore
    sanitized = re.sub(r'[\\/*?:"<>|]', "_", name)
    # Replace whitespace and control characters with single space
    sanitized = re.sub(r"\s+", " ", sanitized).strip()

    # If only separators or underscores remain, fallback
    if not re.sub(r"[._\-\s]", "", sanitized):
        return "downloaded_video"

    # Remove leading/trailing dots or spaces (invalid on Windows)
    sanitized = sanitized.strip(". ")

    if not sanitized:
        sanitized = "downloaded_video"

    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip(". ")

    return sanitized


def verify_mp4_integrity(filepath: str) -> bool:
    """Verify that an MP4 file exists, is not empty, and has basic valid structure.

    Checks for presence of standard MP4 box identifiers ('ftyp', 'moov', or 'mdat').
    """
    if not os.path.exists(filepath):
        return False

    size = os.path.getsize(filepath)
    if size < 32:  # An MP4 header must be at least 24-32 bytes
        return False

    try:
        with open(filepath, "rb") as f:
            header = f.read(4096)
            # Check for common MP4 brand/box markers
            markers = [b"ftyp", b"moov", b"mdat", b"isom", b"mp42"]
            if any(marker in header for marker in markers):
                return True

            # If not in first 4096 bytes (e.g. large file with trailing moov), read end of file
            if size > 4096:
                f.seek(max(0, size - 4096))
                tail = f.read(4096)
                if b"moov" in tail:
                    return True

            return False
    except (OSError, IOError):
        return False


def check_system_dependencies() -> dict[str, bool]:
    """Check availability of external tools and core packages."""
    return {
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "ffprobe": shutil.which("ffprobe") is not None,
    }
