"""Stream and format extractor module using yt-dlp with Headless Stream Sniffer fallback."""

from typing import Any, Optional

EXIT_CODE_NEED_FULL_SNIFFER = 42


class NeedsFullSnifferError(RuntimeError):
    """Raised when stream extraction requires Playwright/Chromium sniffer but it is not available in the current environment."""

    pass


class StreamDetails(tuple):
    """Container for resolved stream endpoints with backwards-compatible 3-tuple unpacking."""

    def __new__(
        cls,
        stream_url: str,
        quality_label: str,
        headers: dict[str, str],
        audio_url: Optional[str] = None,
        audio_headers: Optional[dict[str, str]] = None,
        audio_codec: Optional[str] = None,
        is_muxed: bool = False,
    ):
        instance = super().__new__(cls, (stream_url, quality_label, headers))
        instance.stream_url = stream_url
        instance.quality_label = quality_label
        instance.headers = headers
        instance.audio_url = audio_url
        instance.audio_headers = audio_headers
        instance.audio_codec = audio_codec
        instance.is_muxed = is_muxed
        return instance


class StreamExtractor:
    """Extracts metadata, formats, and direct stream URLs from video or live stream links."""

    def __init__(
        self,
        url: str,
        impersonate: Optional[str] = "chrome",
        cookies_from_browser: Optional[str] = None,
        sniff_mode: str = "auto",
        sniff_timeout: int = 15,
    ):
        self.url = url
        self.impersonate = impersonate if impersonate and impersonate.lower() not in ("none", "false", "off") else None
        self.cookies_from_browser = cookies_from_browser
        self.sniff_mode = sniff_mode.lower() if sniff_mode else "auto"
        self.sniff_timeout = max(5, sniff_timeout)
        self._raw_info: Optional[dict[str, Any]] = None
        self._sniff_result: Optional[Any] = None

    def _ensure_ytdlp(self):
        """Lazy load yt-dlp to allow friendly error handling if missing."""
        try:
            import yt_dlp
            return yt_dlp
        except ImportError:
            raise ImportError(
                "未安裝 yt-dlp 套件。請先執行: pip install -r requirements.txt 或 pip install yt-dlp"
            )

    def _build_ydl_opts(self) -> dict[str, Any]:
        """Build yt-dlp options dictionary including anti-bot impersonation and cookies."""
        ydl_opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
        }

        # Configure browser TLS impersonation (for Cloudflare anti-bot bypass)
        if self.impersonate:
            try:
                from yt_dlp.networking.impersonate import ImpersonateTarget
                ydl_opts["impersonate"] = ImpersonateTarget.from_str(self.impersonate)
                ydl_opts["extractor_args"] = {
                    "generic": {
                        "impersonate": [self.impersonate]
                    }
                }
            except (ImportError, AttributeError, ValueError, Exception):
                # Fallback to extractor_args if ImpersonateTarget cannot be imported
                ydl_opts["extractor_args"] = {
                    "generic": {
                        "impersonate": [self.impersonate]
                    }
                }

        # Configure cookies extraction from local browser
        if self.cookies_from_browser:
            ydl_opts["cookiesfrombrowser"] = (self.cookies_from_browser, None, None, None)

        return ydl_opts

    def _run_sniffer(self) -> dict[str, Any]:
        """Trigger headless browser stream sniffer for dynamic or obfuscated websites."""
        from .sniffer import HeadlessStreamSniffer

        sniffer = HeadlessStreamSniffer(timeout=self.sniff_timeout)
        if not sniffer.is_available():
            raise NeedsFullSnifferError(
                "目標網址未被 yt-dlp 原生支援，且當前環境未安裝 Playwright 或 Chromium 瀏覽器。\n"
                "若在 Docker 輕量容器中運行，將自動發送狀態碼 42 升級至完整版容器；\n"
                "若在本地原生環境，請先執行: pip install -r requirements-full.txt && playwright install chromium"
            )

        print(f"[INFO] 正在啟動無頭瀏覽器動態嗅探串流 (The Stream Detector 引擎，最長等待 {self.sniff_timeout}s)...")
        res = sniffer.sniff(self.url)
        if not res or not res.stream_url:
            raise RuntimeError(
                f"動態嗅探逾時或未在該網頁偵測到 HLS/DASH 媒體串流 (.m3u8 / .mpd)。\n"
                f"若目標需要登入或點擊驗證碼，建議手動從瀏覽器 (F12 -> Network -> 篩選 m3u8) 複製直鏈。"
            )

        self._sniff_result = res
        print(f"[SUCCESS] 成功嗅探到動態串流直鏈: {res.stream_url}")

        # Now extract formats from the sniffed stream URL using yt-dlp
        yt_dlp = self._ensure_ytdlp()
        ydl_opts = self._build_ydl_opts()
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(res.stream_url, download=False)
                if info:
                    if res.title and (not info.get("title") or info.get("title") == "untitled_stream"):
                        info["title"] = res.title
                    existing_headers = info.get("http_headers", {})
                    existing_headers.update(res.headers)
                    info["http_headers"] = existing_headers
                    return info
        except Exception:
            pass

        # Fallback info dict if yt-dlp cannot inspect the m3u8 further
        return {
            "id": "sniffed_stream",
            "title": res.title or "sniffed_stream",
            "url": res.stream_url,
            "http_headers": res.headers,
            "formats": [
                {
                    "format_id": "best",
                    "resolution": "auto",
                    "height": 1080,
                    "url": res.stream_url,
                    "ext": "mp4",
                    "http_headers": res.headers,
                }
            ],
        }

    def extract_metadata(self) -> dict[str, Any]:
        """Extract full metadata dictionary without downloading the media."""
        if self._raw_info is not None:
            return self._raw_info

        if self.sniff_mode == "always":
            self._raw_info = self._run_sniffer()
            return self._raw_info

        yt_dlp = self._ensure_ytdlp()
        ydl_opts = self._build_ydl_opts()

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self._raw_info = ydl.extract_info(self.url, download=False)
        except Exception as e:
            err_msg = str(e).lower()
            if self.sniff_mode == "auto" and (
                "unsupported url" in err_msg
                or "is not a valid url" in err_msg
                or "no video formats found" in err_msg
            ):
                print(f"[INFO] yt-dlp 無法直接識別該網址，自動啟用無頭瀏覽器動態嗅探...")
                self._raw_info = self._run_sniffer()
            else:
                raise

        return self._raw_info

    def get_title(self) -> str:
        """Get sanitized video/stream title."""
        info = self.extract_metadata()
        return info.get("title", "untitled_stream")

    def get_best_audio_format(self, formats: Optional[list[dict[str, Any]]] = None) -> Optional[dict[str, Any]]:
        """Find the best audio format matching container output standards (prefers AAC/m4a for MP4)."""
        if formats is None:
            info = self.extract_metadata()
            formats = info.get("formats", [])

        audio_candidates = []
        for fmt in formats:
            vcodec = fmt.get("vcodec", "none") or "none"
            acodec = fmt.get("acodec", "none") or "none"
            url = fmt.get("url")
            ext = fmt.get("ext", "")

            # Audio-only streams
            if vcodec == "none" and acodec != "none" and url and ext != "mhtml":
                abr = fmt.get("abr") or fmt.get("tbr") or 0
                is_aac = any(sub in acodec.lower() for sub in ("mp4a", "aac")) or ext.lower() == "m4a"
                is_drc = "-drc" in fmt.get("format_id", "").lower()
                audio_candidates.append({
                    "format": fmt,
                    "is_aac": is_aac,
                    "is_drc": is_drc,
                    "abr": float(abr),
                    "format_id": fmt.get("format_id", ""),
                })

        if not audio_candidates:
            return None

        # Prioritize AAC formats for MP4, non-DRC formats, and highest bitrate
        audio_candidates.sort(key=lambda x: (x["is_aac"], not x["is_drc"], x["abr"]), reverse=True)
        return audio_candidates[0]["format"]

    def get_available_formats(self) -> list[dict[str, Any]]:
        """Filter and return formatted resolution options suitable for user selection."""
        info = self.extract_metadata()
        formats = info.get("formats", [])

        best_audio = self.get_best_audio_format(formats)

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

            # Audio tracking: check if format needs separate audio track
            has_separate_audio = (acodec == "none" or not acodec) and (best_audio is not None)
            eff_audio_url = best_audio.get("url") if has_separate_audio else None
            eff_audio_headers = (best_audio.get("http_headers") or info.get("http_headers", {})) if has_separate_audio else None
            eff_audio_codec = best_audio.get("acodec") if has_separate_audio else acodec
            eff_audio_fmt_id = best_audio.get("format_id") if has_separate_audio else None

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
                "http_headers": fmt.get("http_headers") or info.get("http_headers", {}),
                "has_separate_audio": has_separate_audio,
                "audio_url": eff_audio_url,
                "audio_headers": eff_audio_headers,
                "audio_codec": eff_audio_codec,
                "audio_format_id": eff_audio_fmt_id,
            })

        # Sort by height descending
        valid_options.sort(key=lambda x: x["height"], reverse=True)
        return valid_options

    def get_http_headers(self, selected_format_id: Optional[str] = None) -> dict[str, str]:
        """Retrieve HTTP request headers for the selected format or stream metadata."""
        info = self.extract_metadata()
        default_headers = info.get("http_headers", {})

        formats = info.get("formats", [])
        if selected_format_id:
            for fmt in formats:
                if fmt.get("format_id") == selected_format_id or f"{fmt.get('height')}p" == selected_format_id:
                    return fmt.get("http_headers") or default_headers

        return default_headers

    def resolve_stream_details(
        self, selected_format_id: Optional[str] = None
    ) -> StreamDetails:
        """Resolve the final stream direct URL, chosen quality label, headers, and audio stream details.

        Returns a StreamDetails instance which supports backwards-compatible 3-tuple unpacking
        (stream_url, quality_label, http_headers) and attribute access for separate audio tracks.
        """
        formats = self.get_available_formats()
        if not formats:
            info = self.extract_metadata()
            stream_url = info.get("url", self.url)
            headers = info.get("http_headers", {})
            return StreamDetails(
                stream_url=stream_url,
                quality_label="default",
                headers=headers,
                audio_url=None,
                audio_headers=None,
                audio_codec=None,
                is_muxed=True,
            )

        if selected_format_id:
            for fmt in formats:
                if fmt["format_id"] == selected_format_id or fmt["resolution"] == selected_format_id:
                    return StreamDetails(
                        stream_url=fmt["url"],
                        quality_label=fmt["resolution"],
                        headers=fmt.get("http_headers", {}),
                        audio_url=fmt.get("audio_url"),
                        audio_headers=fmt.get("audio_headers"),
                        audio_codec=fmt.get("audio_codec"),
                        is_muxed=not fmt.get("has_separate_audio", False),
                    )

        best = formats[0]
        return StreamDetails(
            stream_url=best["url"],
            quality_label=best["resolution"],
            headers=best.get("http_headers", {}),
            audio_url=best.get("audio_url"),
            audio_headers=best.get("audio_headers"),
            audio_codec=best.get("audio_codec"),
            is_muxed=not best.get("has_separate_audio", False),
        )

    def resolve_stream_url(self, selected_format_id: Optional[str] = None) -> tuple[str, str]:
        """Resolve the final stream direct URL and chosen quality label.

        Returns (stream_url, quality_label). Maintained for backwards compatibility.
        """
        stream_url, quality_label, _ = self.resolve_stream_details(selected_format_id)
        return stream_url, quality_label
