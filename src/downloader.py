"""FFmpeg Worker and process management."""

import os
import re
import shutil
import subprocess
from typing import Optional


class FFmpegDownloader:
    """Encapsulates FFmpeg process execution, parameter assembling, and progress parsing."""

    def __init__(self, stream_url: str, output_path: str):
        if not stream_url or stream_url.startswith("-"):
            raise ValueError("無效或不合法的串流網址格式 (禁止空值或以破折號開頭之參數注入)。")
        self.stream_url = stream_url
        self.output_path = output_path
        self._progress_regex = re.compile(
            r"size=\s*(\d+[kMG]?B).*?time=\s*([\d:\.]+).*?bitrate=\s*([\d\.]+kbits/s).*?speed=\s*([\d\.]+x)"
        )

    def is_ffmpeg_available(self) -> bool:
        """Check if FFmpeg binary is found on system PATH."""
        return shutil.which("ffmpeg") is not None

    def build_command(self) -> list[str]:
        """Assemble the FFmpeg command line with reconnect and stream copy parameters."""
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-loglevel", "info",
            "-reconnect", "1",
            "-reconnect_at_eof", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "10",
            "-i", self.stream_url,
            "-c", "copy",  # Direct stream copy (no re-encoding)
            "-bsf:a", "aac_adtstoasc",  # Fix AAC bitstream filter for MP4 container
            "-movflags", "+faststart",
            self.output_path,
        ]
        return cmd

    def start_process(self) -> subprocess.Popen:
        """Spawn the FFmpeg process."""
        if not self.is_ffmpeg_available():
            raise FileNotFoundError(
                "系統找不到 'ffmpeg' 可執行檔。請下載安裝 FFmpeg 並將其加入系統環境變數 PATH 中。"
            )

        # Ensure destination directory exists
        out_dir = os.path.dirname(os.path.abspath(self.output_path))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        cmd = self.build_command()

        # On Windows, create subprocess with proper flags
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        return process

    def parse_progress(self, line: str) -> Optional[dict]:
        """Parse an FFmpeg stderr progress log line."""
        match = self._progress_regex.search(line)
        if match:
            size, time_str, bitrate, speed = match.groups()
            return {
                "size": size.strip(),
                "time": time_str.strip(),
                "bitrate": bitrate.strip(),
                "speed": speed.strip(),
            }

        # Fallback simpler regex if bitrate or speed is missing
        time_match = re.search(r"time=\s*([\d:\.]+)", line)
        if time_match:
            return {
                "size": "N/A",
                "time": time_match.group(1).strip(),
                "bitrate": "N/A",
                "speed": "N/A",
            }

        return None
