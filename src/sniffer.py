"""Headless browser dynamic stream sniffer module using Playwright."""

from dataclasses import dataclass, field
import os
from typing import Callable, Optional


@dataclass
class SniffResult:
    """Encapsulates captured stream URL, headers, and metadata."""

    stream_url: str
    headers: dict[str, str] = field(default_factory=dict)
    title: str = "untitled_stream"
    detected_streams: list[str] = field(default_factory=list)


class HeadlessStreamSniffer:
    """Sniffs dynamic HLS/DASH media streams (.m3u8/.mpd) using headless Chromium."""

    # Stream extensions and MIME indicators
    STREAM_EXTENSIONS = (".m3u8", ".mpd")

    def __init__(self, timeout: int = 15, headless: bool = True):
        self.timeout = max(5, timeout)
        self.headless = headless

    def is_available(self) -> bool:
        """Check if Playwright and Chromium executable are available."""
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                return bool(p.chromium.executable_path and os.path.exists(p.chromium.executable_path))
        except (ImportError, Exception):
            return False

    def sniff(
        self,
        url: str,
        user_agent: Optional[str] = None,
        on_detected: Optional[Callable[[str], None]] = None,
    ) -> Optional[SniffResult]:
        """Launch headless browser, navigate to URL, and intercept media playlist requests.

        Returns SniffResult if a valid stream URL is intercepted, otherwise None.
        """
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
        except ImportError:
            raise ImportError(
                "未安裝 playwright 套件。請先執行: pip install playwright && playwright install chromium"
            )

        detected_urls: list[str] = []
        captured_headers: dict[str, str] = {}
        captured_title = "untitled_stream"

        with sync_playwright() as p:
            # Launch Chromium with anti-bot evasion arguments
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]
            browser = p.chromium.launch(headless=self.headless, args=launch_args)

            context_kwargs = {
                "viewport": {"width": 1280, "height": 720},
                "locale": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            }
            if user_agent:
                context_kwargs["user_agent"] = user_agent

            context = browser.new_context(**context_kwargs)
            page = context.new_page()

            def on_request(request):
                req_url = request.url
                # Clean URL without query params for extension checking
                clean_url = req_url.split("?")[0].lower()
                if any(clean_url.endswith(ext) or ext in clean_url for ext in self.STREAM_EXTENSIONS):
                    if req_url not in detected_urls:
                        detected_urls.append(req_url)
                        # Capture essential headers (User-Agent, Referer, Cookie, Origin)
                        req_headers = request.headers
                        captured_headers.update({
                            k: v for k, v in req_headers.items()
                            if k.lower() in ("user-agent", "referer", "cookie", "origin")
                        })
                        if on_detected:
                            on_detected(req_url)

            page.on("request", on_request)

            try:
                # Navigate to the page
                page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
                captured_title = page.title() or "untitled_stream"

                # Wait for player or stream requests (polling up to remaining timeout)
                elapsed = 0.0
                step = 0.5
                while elapsed < self.timeout:
                    if detected_urls:
                        # Give it an extra 1 second to capture master playlist or headers
                        page.wait_for_timeout(1000)
                        break
                    page.wait_for_timeout(int(step * 1000))
                    elapsed += step

                if page.title():
                    captured_title = page.title()

            except PlaywrightTimeoutError:
                # Page load timed out, but check if we already intercepted stream
                pass
            except Exception:
                # Fallback to whatever was captured
                pass
            finally:
                browser.close()

        if not detected_urls:
            return None

        # Prioritize master or playlist m3u8 if multiple detected
        best_url = detected_urls[0]
        for u in detected_urls:
            u_lower = u.lower()
            if "master.m3u8" in u_lower or "playlist.m3u8" in u_lower:
                best_url = u
                break

        return SniffResult(
            stream_url=best_url,
            headers=captured_headers,
            title=captured_title,
            detected_streams=detected_urls,
        )

