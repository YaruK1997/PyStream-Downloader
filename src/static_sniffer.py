"""Static stream sniffer utilizing TLS impersonation (curl_cffi) and packed script decoders."""

import re
from typing import Optional
from urllib.parse import urlparse

from .sniffer import SniffResult
from .packer import extract_m3u8_from_html

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def extract_page_title(html: str) -> str:
    """Extract page title from OpenGraph metadata or title tag."""
    if not html:
        return "untitled_stream"

    # 1. Try og:title
    og_match = re.search(r'<meta\s+[^>]*property=["\']og:title["\']\s+[^>]*content=["\'](.*?)["\']', html, re.IGNORECASE)
    if not og_match:
        og_match = re.search(r'<meta\s+[^>]*content=["\'](.*?)["\']\s+[^>]*property=["\']og:title["\']', html, re.IGNORECASE)
    if og_match and og_match.group(1).strip():
        return og_match.group(1).strip()

    # 2. Try title tag
    title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    if title_match and title_match.group(1).strip():
        clean_title = re.sub(r"\s+", " ", title_match.group(1)).strip()
        return clean_title

    return "untitled_stream"


def fetch_page_html(
    url: str,
    impersonate: Optional[str] = "chrome120",
    timeout: int = 15,
    headers: Optional[dict[str, str]] = None,
) -> str:
    """Fetch target webpage HTML content using curl_cffi TLS impersonation or standard HTTP fallback."""
    req_headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    if headers:
        req_headers.update(headers)

    # 1. Try curl_cffi with browser TLS impersonation (bypasses Cloudflare Turnstile/WAF)
    try:
        from curl_cffi import requests
        resp = requests.get(
            url,
            headers=req_headers,
            impersonate=impersonate or "chrome120",
            timeout=timeout,
            allow_redirects=True,
        )
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass

    # 2. Fallback to standard urllib.request
    import urllib.request
    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


class StaticPackerSniffer:
    """Sniffs streaming playlists by parsing and unpacking obfuscated client-side JavaScript.
    
    Operates without starting a heavy Chromium browser instance and circumvents
    Cloudflare Turnstile challenges via TLS impersonation.
    """

    def __init__(self, timeout: int = 15, impersonate: Optional[str] = "chrome120"):
        self.timeout = max(5, timeout)
        self.impersonate = impersonate or "chrome120"

    def sniff(self, url: str) -> Optional[SniffResult]:
        """Fetch target page, unpack JavaScript, and return detected stream playlist."""
        try:
            html = fetch_page_html(url, impersonate=self.impersonate, timeout=self.timeout)
        except Exception:
            return None

        m3u8_urls = extract_m3u8_from_html(html)
        if not m3u8_urls:
            return None

        title = extract_page_title(html)

        # Parse origin for CORS headers
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else url

        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Referer": url,
            "Origin": origin,
        }

        return SniffResult(
            stream_url=m3u8_urls[0],
            headers=headers,
            title=title,
            detected_streams=m3u8_urls,
        )

