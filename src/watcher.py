"""Live stream status watcher and polling module."""

import time
from typing import Any, Callable, Optional


class StreamWatcher:
    """Monitors upcoming, scheduled, or offline live streams and polls until they go live."""

    def __init__(
        self,
        url: str,
        poll_interval: int = 15,
        impersonate: Optional[str] = "chrome",
        cookies_from_browser: Optional[str] = None,
    ):
        self.url = url
        self.poll_interval = max(5, poll_interval)
        self.impersonate = impersonate if impersonate and impersonate.lower() not in ("none", "false", "off") else None
        self.cookies_from_browser = cookies_from_browser
        self._is_cancelled = False

    def cancel(self):
        """Cancel ongoing wait loop."""
        self._is_cancelled = True

    def _build_ydl_opts(self) -> dict[str, Any]:
        """Build yt-dlp options dictionary including anti-bot impersonation and cookies."""
        ydl_opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": False,
        }

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
                ydl_opts["extractor_args"] = {
                    "generic": {
                        "impersonate": [self.impersonate]
                    }
                }

        if self.cookies_from_browser:
            ydl_opts["cookiesfrombrowser"] = (self.cookies_from_browser, None, None, None)

        return ydl_opts

    def check_status(self) -> tuple[bool, str, dict]:
        """Check current live status of the URL.

        Returns (is_live: bool, status_label: str, info_dict: dict).
        """
        try:
            import yt_dlp
        except ImportError:
            raise ImportError("未安裝 yt-dlp 套件。請先執行: pip install -r requirements.txt")

        ydl_opts = self._build_ydl_opts()

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                if not info:
                    return False, "offline", {}

                live_status = info.get("live_status")
                # Possible values in yt-dlp: 'is_live', 'is_upcoming', 'was_live', 'not_live', None
                if live_status == "is_live" or info.get("is_live") is True:
                    return True, "live", info
                elif live_status == "is_upcoming":
                    return False, "upcoming", info
                elif live_status == "was_live":
                    return True, "vod_recorded", info
                else:
                    # If it's a regular on-demand video or active direct stream
                    return True, "active", info

        except Exception as e:
            err_msg = str(e).lower()
            if "live event will begin" in err_msg or "premieres in" in err_msg:
                return False, "upcoming", {"error": str(e)}
            return False, "offline", {"error": str(e)}

    def wait_until_live(self, on_tick: Optional[Callable[[int, int], None]] = None) -> bool:
        """Poll the stream status until it becomes live or is cancelled.

        on_tick(countdown_remaining: int, attempt_count: int) -> None
        Returns True when stream goes live, False if cancelled or aborted.
        """
        attempt = 1
        while not self._is_cancelled:
            is_live, status, info = self.check_status()
            if is_live:
                return True

            # Countdown loop
            for remaining in range(self.poll_interval, 0, -1):
                if self._is_cancelled:
                    return False
                if on_tick:
                    on_tick(remaining, attempt)
                time.sleep(1)

            attempt += 1

        return False
