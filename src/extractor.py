"""Stream and format extractor module using yt-dlp."""

from typing import Any, Optional


class StreamExtractor:
    """Extracts metadata, formats, and direct stream URLs from video or live stream links."""

    def __init__(self, url: str):
        self.url = url
        self._raw_info: Optional[dict[str, Any]] = None

    def _ensure_ytdlp(self):
        """Lazy load yt-dlp to allow friendly error handling if missing."""
        try:
            import yt_dlp
            return yt_dlp
        except ImportError:
            raise ImportError(
                "未安裝 yt-dlp 套件。請先執行: pip install -r requirements.txt 或 pip install yt-dlp"
            )

    def extract_metadata(self) -> dict[str, Any]:
        """Extract full metadata dictionary without downloading the media."""
        if self._raw_info is not None:
            return self._raw_info

        yt_dlp = self._ensure_ytdlp()
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            self._raw_info = ydl.extract_info(self.url, download=False)

        return self._raw_info

    def get_title(self) -> str:
        """Get sanitized video/stream title."""
        info = self.extract_metadata()
        return info.get("title", "untitled_stream")

    def get_available_formats(self) -> list[dict[str, Any]]:
        """Filter and return formatted resolution options suitable for user selection."""
        info = self.extract_metadata()
        formats = info.get("formats", [])

        valid_options = []
        seen_res = set()

        # Reverse iterate (higher quality usually at the end)
        for fmt in reversed(formats):
            vcodec = fmt.get("vcodec", "none")
            acodec = fmt.get("acodec", "none")
            height = fmt.get("height")
            fmt_id = fmt.get("format_id", "")
            ext = fmt.get("ext", "mp4")
            tbr = fmt.get("tbr") or 0  # Total bitrate (kbits/s)

            # Skip audio-only unless no video exists
            if vcodec == "none" or not height:
                continue

            res_label = f"{height}p"
            if res_label in seen_res:
                continue

            seen_res.add(res_label)
            valid_options.append({
                "format_id": fmt_id,
                "resolution": res_label,
                "height": height,
                "vcodec": vcodec,
                "acodec": acodec,
                "ext": ext,
                "bitrate_kbps": int(tbr),
                "url": fmt.get("url", ""),
                "protocol": fmt.get("protocol", "http"),
            })

        # Sort by height descending
        valid_options.sort(key=lambda x: x["height"], reverse=True)
        return valid_options

    def resolve_stream_url(self, selected_format_id: Optional[str] = None) -> tuple[str, str]:
        """Resolve the final stream direct URL and chosen quality label.

        Returns (stream_url, quality_label).
        """
        formats = self.get_available_formats()
        if not formats:
            # Fallback to direct URL if no formats breakdown
            info = self.extract_metadata()
            return info.get("url", self.url), "default"

        if selected_format_id:
            for fmt in formats:
                if fmt["format_id"] == selected_format_id or fmt["resolution"] == selected_format_id:
                    return fmt["url"], fmt["resolution"]

        # Default to highest quality
        best = formats[0]
        return best["url"], best["resolution"]
