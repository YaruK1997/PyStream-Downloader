"""Dean Edwards JavaScript Packer unpacker and stream URL extractor module."""

import re
from typing import Optional


DIGITS_62 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def get_base_token(val: int, radix: int) -> str:
    """Encode integer to arbitrary radix representation (up to Base 62)."""
    if radix <= 0:
        return str(val)
    if val < radix:
        return DIGITS_62[val] if val < len(DIGITS_62) else str(val)
    return get_base_token(val // radix, radix) + (DIGITS_62[val % radix] if (val % radix) < len(DIGITS_62) else str(val % radix))


def unpack_dean_edwards(packed_js: str) -> str:
    """Unpack Dean Edwards JavaScript packer: eval(function(p,a,c,k,e,d)...).
    
    Returns the unpacked JavaScript code, or an empty string if malformed.
    """
    if not packed_js or "eval(function(" not in packed_js:
        return ""

    # Match pattern: }('PACKED_TEMPLATE', RADIX, COUNT, 'WORDS'.split('|'), ...)
    # Supporting both single and double quotes, and variations in argument placement
    pattern = r"\}\('(.*?)',\s*(\d+),\s*(\d+),\s*'(.*?)'\.split\('\|'\)"
    match = re.search(pattern, packed_js, re.DOTALL)
    if not match:
        # Fallback to double quote pattern
        pattern_dq = r'\}\("(.*?)",\s*(\d+),\s*(\d+),\s*"(.*?)"\.split\("\|"\)'
        match = re.search(pattern_dq, packed_js, re.DOTALL)
        if not match:
            return ""

    p, a_str, c_str, k_str = match.groups()
    try:
        radix = int(a_str)
        count = int(c_str)
    except ValueError:
        return ""

    words = k_str.split("|")
    lookup = {}
    for i in range(count):
        token = get_base_token(i, radix)
        word = words[i] if (i < len(words) and words[i]) else token
        lookup[token] = word

    # Replace word tokens in the template using a single regex replacement
    # Word boundary \b matches alphanumeric and underscore sequences
    unpacked = re.sub(r"\b(\w+)\b", lambda m: lookup.get(m.group(1), m.group(1)), p)

    # Normalize escape sequences
    unpacked = (
        unpacked.replace(r"\'", "'")
        .replace(r'\"', '"')
        .replace(r"\/", "/")
        .replace(r"\\", "\\")
    )
    return unpacked


def find_packed_scripts(html_or_js: str) -> list[str]:
    """Search and extract all Dean Edwards packed script code blocks from text."""
    if not html_or_js:
        return []

    # Match eval(function(p,a,c,k,e,...) blocks
    pattern = r"eval\(function\(p,a,c,k,e,[rd]\).*?\}\(.*?\)\)"
    matches = re.findall(pattern, html_or_js, re.DOTALL)
    return matches


def extract_m3u8_from_html(html: str) -> list[str]:
    """Find and extract all .m3u8 streaming playlist URLs from HTML or embedded packed scripts."""
    if not html:
        return []

    found_urls: list[str] = []

    def _collect_urls(text: str):
        # Match http(s) URLs ending with or containing .m3u8
        matches = re.findall(r"https?://[^\s'\"<>]+\.m3u8[^\s'\"<>]*", text)
        for u in matches:
            clean_u = u.strip().rstrip("\\")
            if clean_u not in found_urls:
                found_urls.append(clean_u)

    # 1. First unpack any Dean Edwards packed scripts
    packed_blocks = find_packed_scripts(html)
    for block in packed_blocks:
        unpacked = unpack_dean_edwards(block)
        if unpacked:
            _collect_urls(unpacked)

    # 2. Also scan the raw HTML for direct m3u8 occurrences
    _collect_urls(html)

    # Prioritize master or playlist m3u8 if multiple detected
    found_urls.sort(
        key=lambda u: (
            "playlist.m3u8" in u.lower() or "master.m3u8" in u.lower(),
            "1080p" in u.lower(),
            "720p" in u.lower(),
        ),
        reverse=True,
    )
    return found_urls

