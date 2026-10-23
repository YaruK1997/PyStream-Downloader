"""FFmpeg Worker and process management."""

import functools
import os
import re
import shutil
import subprocess
from typing import Optional


@functools.lru_cache(maxsize=1)
def get_ffmpeg_hls_options() -> list[str]:
    """Detect available HLS demuxer options supported by the installed FFmpeg version.

    In modern FFmpeg (v6.1+, v7+), HLS demuxer enforces strict extension checking by default.
    Options:
      - `-allowed_segment_extensions ALL`: permits non-standard or disguised chunk extensions (.jpeg, .png, .jpg).
      - `-extension_picky 0`: ignores format/mime mismatches between probed container (mpegts) and extension (.jpeg).
      - `-allowed_extensions ALL`: allows arbitrary playlist extensions.
    Older FFmpeg releases (v5.x and below) do not recognize these flags and will fail if passed.
    """
    if not shutil.which("ffmpeg"):
        return []

    flags: list[str] = []
    try:
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-h", "demuxer=hls"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        help_text = (proc.stdout or "") + (proc.stderr or "")
        if "allowed_segment_extensions" in help_text:
            flags.extend(["-allowed_segment_extensions", "ALL"])
        if "extension_picky" in help_text:
            flags.extend(["-extension_picky", "0"])
        if "allowed_extensions" in help_text:
            flags.extend(["-allowed_extensions", "ALL"])
    except Exception:
        pass
    return flags


class FFmpegDownloader:
    """Encapsulates FFmpeg process execution, parameter assembling, and progress parsing."""

    def __init__(
        self,
        stream_url: str,
        output_path: str,
        headers: Optional[dict[str, str]] = None,
        audio_url: Optional[str] = None,
        audio_headers: Optional[dict[str, str]] = None,
        audio_codec: Optional[str] = None,
        is_hls: Optional[bool] = None,
    ):
        if not stream_url or stream_url.startswith("-"):
            raise ValueError("無效或不合法的串流網址格式 (禁止空值或以破折號開頭之參數注入)。")
        if audio_url and audio_url.startswith("-"):
            raise ValueError("無效或不合法的音訊串流網址格式 (禁止以破折號開頭之參數注入)。")
        self.stream_url = stream_url
        self.output_path = output_path
        self.headers = self._validate_and_sanitize_headers(headers)
        self.audio_url = audio_url if audio_url and audio_url != stream_url else None
        self.audio_headers = self._validate_and_sanitize_headers(audio_headers)
        self.audio_codec = (audio_codec or "aac").lower()
        self.is_hls = is_hls
        self._progress_regex = re.compile(
            r"size=\s*(\d+[kMG]?B).*?time=\s*([\d:\.]+).*?bitrate=\s*([\d\.]+kbits/s).*?speed=\s*([\d\.]+x)"
        )

    def _validate_and_sanitize_headers(
        self, headers: Optional[dict[str, str]]
    ) -> Optional[dict[str, str]]:
        """Validate HTTP headers to prevent CRLF injection attacks."""
        if not headers:
            return None

        clean_headers: dict[str, str] = {}
        for k, v in headers.items():
            if not isinstance(k, str) or not isinstance(v, str):
                continue
            # Disallow carriage return and newline characters to prevent CRLF injection
            if "\r" in k or "\n" in k or "\r" in v or "\n" in v:
                raise ValueError("偵測到不合法的 HTTP 標頭字元 (禁止包含換行符號 CRLF)。")
            clean_headers[k.strip()] = v.strip()

        return clean_headers if clean_headers else None

    def is_ffmpeg_available(self) -> bool:
        """Check if FFmpeg binary is found on system PATH."""
        return shutil.which("ffmpeg") is not None

    @staticmethod
    def is_hls_url(url: Optional[str]) -> bool:
        """Determine whether the URL points to an HLS playlist based on filename or query."""
        if not url:
            return False
        clean = url.split("?")[0].lower()
        return clean.endswith(".m3u8") or ".m3u8" in clean or "m3u8" in url.lower()

    def build_command(self) -> list[str]:
        """Assemble the FFmpeg command line with reconnect, headers, multi-stream mapping, and A/V sync flags."""
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-loglevel", "info",
        ]

        # Input 0: Video stream (or combined muxed stream)
        is_video_hls = self.is_hls or (self.is_hls is None and self.is_hls_url(self.stream_url))
        cmd.extend([
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "10",
        ])
        if not is_video_hls:
            cmd.extend(["-reconnect_at_eof", "1"])
        else:
            cmd.extend(get_ffmpeg_hls_options())

        if self.headers:
            headers_payload = "".join(f"{k}: {v}\r\n" for k, v in self.headers.items())
            cmd.extend(["-headers", headers_payload])
        cmd.extend(["-i", self.stream_url])

        # Input 1: Separate audio stream (if present)
        if self.audio_url:
            is_audio_hls = self.is_hls or (self.is_hls is None and self.is_hls_url(self.audio_url))
            cmd.extend([
                "-reconnect", "1",
                "-reconnect_streamed", "1",
                "-reconnect_delay_max", "10",
            ])
            if not is_audio_hls:
                cmd.extend(["-reconnect_at_eof", "1"])
            else:
                cmd.extend(get_ffmpeg_hls_options())

            eff_audio_headers = self.audio_headers or self.headers
            if eff_audio_headers:
                a_headers_payload = "".join(f"{k}: {v}\r\n" for k, v in eff_audio_headers.items())
                cmd.extend(["-headers", a_headers_payload])
            cmd.extend(["-i", self.audio_url])

            # Explicit stream mapping for 2 inputs
            cmd.extend([
                "-map", "0:v:0",
                "-map", "1:a:0",
            ])
            cmd.extend(["-c:v", "copy"])

            # Audio Codec Adaptation & Resampling Sync
            is_mp4 = self.output_path.lower().endswith(".mp4")
            is_aac = any(sub in self.audio_codec for sub in ("aac", "mp4a", "m4a"))

            if is_mp4 and not is_aac:
                # Non-AAC audio into MP4: transcode to AAC with audio timestamp resampling
                cmd.extend([
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-af", "aresample=async=1:first_pts=0",
                ])
            else:
                # AAC audio into MP4 or native copy
                cmd.extend([
                    "-c:a", "copy",
                    "-bsf:a", "aac_adtstoasc",
                ])
        else:
            # Single stream (muxed or standalone video)
            cmd.extend([
                "-c", "copy",
                "-bsf:a", "aac_adtstoasc",
            ])

        # Timestamp synchronization and packet interleaving protection
        cmd.extend([
            "-fflags", "+genpts",
            "-avoid_negative_ts", "make_zero",
            "-max_interleave_delta", "0",
        ])

        if self.audio_url:
            cmd.append("-shortest")

        cmd.extend([
            "-movflags", "+faststart",
            self.output_path,
        ])
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
