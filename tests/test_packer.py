"""Unit tests for Dean Edwards Packer unpacking and static stream detection (TDD Red -> Green)."""

import unittest
from src.packer import unpack_dean_edwards, find_packed_scripts, extract_m3u8_from_html


class TestPacker(unittest.TestCase):
    """Test Dean Edwards JS Packer parsing and decoding."""

    def test_unpack_dean_edwards_base36(self):
        """Verify unpacking with base 36 radix."""
        packed = r"""eval(function(p,a,c,k,e,d){e=function(c){return c.toString(36)};if(!''.replace(/^/,String)){while(c--)d[c.toString(a)]=k[c]||c.toString(a);k=[function(e){return d[e]}];e=function(){return'\\w+'};c=1};while(c--)if(k[c])p=p.replace(new RegExp('\\b'+e(c)+'\\b','g'),k[c]);return p}('3=\'2://1.0\';',4,4,'m3u8|surrit|https|source'.split('|'),0,{}))"""
        unpacked = unpack_dean_edwards(packed)
        self.assertIn("https://surrit.m3u8", unpacked)
        self.assertIn("source", unpacked)

    def test_unpack_dean_edwards_base62(self):
        """Verify unpacking with base 62 radix (including uppercase letters)."""
        # 36th token is 'A' in base 62
        packed = r"""eval(function(p,a,c,k,e,d){e=function(c){return(c<a?'':e(parseInt(c/a)))+((c=c%a)>35?String.fromCharCode(c+29):c.toString(36))};if(!''.replace(/^/,String)){while(c--)d[e(c)]=k[c]||e(c);k=[function(e){return d[e]}];e=function(){return'\\w+'};c=1};while(c--)if(k[c])p=p.replace(new RegExp('\\b'+e(c)+'\\b','g'),k[c]);return p}('d=\'c://b.a/9-8-7-6-5/4.3\';2=\'c://b.a/9-8-7-6-5/1/0.3\';',14,14,'video|720p|source720|m3u8|playlist|7718c68f|c32e|42a2|aab6|97e4fc14271b|com|surrit|https|source'.split('|'),0,{}))"""
        unpacked = unpack_dean_edwards(packed)
        self.assertIn("https://surrit.com/97e4fc14271b-aab6-42a2-c32e-7718c68f/playlist.m3u8", unpacked)
        self.assertIn("https://surrit.com/97e4fc14271b-aab6-42a2-c32e-7718c68f/720p/video.m3u8", unpacked)

    def test_unpack_invalid_or_non_packed(self):
        """Verify non-packed or malformed scripts return empty string safely."""
        self.assertEqual(unpack_dean_edwards("var a = 1;"), "")
        self.assertEqual(unpack_dean_edwards(""), "")
        self.assertEqual(unpack_dean_edwards("eval(function(){})"), "")

    def test_find_packed_scripts(self):
        """Verify extraction of multiple packed script blocks from an HTML page."""
        html = """
        <html>
        <head><title>Test</title></head>
        <body>
        <script>
        eval(function(p,a,c,k,e,d){e=function(c){return c.toString(36)};return p}('0=1;',2,2,'a|b'.split('|'),0,{}))
        </script>
        <div>Some content</div>
        <script>
        eval(function(p,a,c,k,e,d){e=function(c){return c.toString(36)};return p}('0=2;',3,3,'x|y|z'.split('|'),0,{}))
        </script>
        </body>
        </html>
        """
        scripts = find_packed_scripts(html)
        self.assertEqual(len(scripts), 2)

    def test_extract_m3u8_from_html(self):
        """Verify end-to-end extraction of m3u8 URLs from packed HTML."""
        html = """
        <html>
        <script>
        eval(function(p,a,c,k,e,d){e=function(c){return c.toString(36)};return p}('0=\\'1://2.3/4/5.6\\';',7,7,'source|https|surrit|com|uuid123|playlist|m3u8'.split('|'),0,{}))
        </script>
        </html>
        """
        urls = extract_m3u8_from_html(html)
        self.assertEqual(len(urls), 1)
        self.assertEqual(urls[0], "https://surrit.com/uuid123/playlist.m3u8")


if __name__ == "__main__":
    unittest.main()

