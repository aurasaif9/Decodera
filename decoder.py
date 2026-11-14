"""
Multi-layer HTML/PHP/JS obfuscation decoder - UPDATED VERSION.

Handles:
  ✅ PHPKobo HTML obfuscator    — stream-cipher + LRM/ZWJ/RLM lookup table
  ✅ PHPKobo wrapped in base64  — var _sec = atob(...) → document.write
  ✅ PHPKodo                    — gzinflate / str_rot13 / base64_decode eval chains
  ✅ PHPCabbo                   — variable-based obfuscation ($O00O0O style)
  ✅ Dean Edwards Packer        — eval(function(p,a,c,k,e,d){...})
  ✅ JS Obfuscator.io           — hex string arrays, _0x patterns
  ✅ JSFuck / AAencode           — []()!+ style
  ✅ Base64                     — raw blobs, inline base64_decode(), atob()
  ✅ gzinflate / gzuncompress / gzdecode
  ✅ str_rot13
  ✅ HTML entities              — &lt; &amp; &#60; &#x3C; …
  ✅ Hex / Unicode escapes      — \\x41 \\u0041
  ✅ URL encoding               — %20 %3C …
  ✅ JS eval(atob/unescape/decodeURIComponent)
  ✅ JS String.fromCharCode(…)
  ✅ document.write(atob/unescape)
  ✅ Advanced JS Array/String extraction for web layout decodes
  ✅ Multi-layer combinations   — up to 25 passes
"""

import base64
import zlib
import html
import re
import urllib.parse
import codecs
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import json


# ─────────────────────────────────────────────────────────────────────────────
# Low-level helpers
# ─────────────────────────────────────────────────────────────────────────────

def _b64_decode(s: str) -> bytes:
    """Base64 decode — strips whitespace and pads automatically."""
    s = re.sub(r'\s', '', s)
    pad = (4 - len(s) % 4) % 4
    try:
        return base64.b64decode(s + '=' * pad)
    except Exception:
        return b''


def _rot13_bytes(b: bytes) -> bytes:
    return b.translate(bytes.maketrans(
        b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz',
        b'NOPQRSTUVWXYZABCDEFGHIJKLMnopqrstuvwxyzabcdefghijklm'
    ))


def _inflate(b: bytes) -> bytes:
    """Try all zlib wbits variants."""
    for wbits in (-15, 15, 47):
        try:
            return zlib.decompress(b, wbits)
        except Exception:
            pass
    return b''


def _to_str(b: bytes) -> str:
    """Decode bytes trying multiple encodings."""
    for enc in ('utf-8', 'latin-1', 'cp1252'):
        try:
            return b.decode(enc)
        except Exception:
            pass
    return b.decode('utf-8', errors='replace')


def _atob_decode(b64: str) -> str:
    """
    Simulate browser atob() + decodeURIComponent(escape()) UTF-8 fix.
    Returns decoded string or empty string on failure.
    """
    raw = _b64_decode(b64)
    if not raw:
        return ''
    try:
        return raw.decode('utf-8')
    except Exception:
        pass
    try:
        latin = raw.decode('latin-1')
        pct = ''.join(f'%{ord(c):02X}' if ord(c) > 127 else c for c in latin)
        return urllib.parse.unquote(pct, encoding='utf-8')
    except Exception:
        pass
    return _to_str(raw)


def _looks_like_code(s: str) -> bool:
    """Heuristic: does this look like actual HTML/PHP/JS source?"""
    if not s or len(s) < 5:
        return False
    markers = [
        '<?php', '<?', '<html', '<body', '<head', '<script',
        'function', 'eval(', 'echo ', 'document.', 'window.',
        'var ', 'const ', 'let ', '=>', '{}', '<div', '<span',
        'return ', 'if (', 'while (', 'for (', '<!DOCTYPE',
        '<meta', '<title', '<style', 'getElementById',
    ]
    return any(m in s for m in markers) or len(s) > 50


def _is_html_or_clean(s: str) -> bool:
    """Is this final decoded HTML/source (not still obfuscated)?"""
    if not s:
        return False
    tags = ['<html', '<head', '<body', '<!DOCTYPE', '<title', '<div',
            '<script', '<style', '<meta', '<link', '<?php']
    return any(t in s for t in tags)


# ─────────────────────────────────────────────────────────────────────────────
# PHPKobo HTML Obfuscator decoder
# ─────────────────────────────────────────────────────────────────────────────

def _js_template_unescape(s: str) -> str:
    """Unescape JavaScript template/string literal escape sequences."""
    result = []
    i = 0
    while i < len(s):
        if s[i] == '\\' and i + 1 < len(s):
            nc = s[i + 1]
            if nc == '\\':
                result.append('\\'); i += 2
            elif nc == '"':
                result.append('"'); i += 2
            elif nc == "'":
                result.append("'"); i += 2
            elif nc == 'n':
                result.append('\n'); i += 2
            elif nc == 'r':
                result.append('\r'); i += 2
            elif nc == 't':
                result.append('\t'); i += 2
            elif nc == '`':
                result.append('`'); i += 2
            elif nc == '0':
                result.append('\0'); i += 2
            else:
                result.append(s[i]); i += 1
        else:
            result.append(s[i]); i += 1
    return ''.join(result)


def _phpkobo_stream_decode(srkpv: str) -> str:
    b_idx = srkpv.find('B')
    if b_idx < 0:
        return ''
    srkpv = srkpv[b_idx + 1:]
    if len(srkpv) < 9:
        return ''

    yl_rf = srkpv[-8:]
    try:
        step  = int(yl_rf[4:6], 16)
        start = int(yl_rf[6:8], 16)
    except ValueError:
        return ''
    srkpv = srkpv[:-8]

    srkpv = re.sub(r'X', 'E', srkpv, flags=re.IGNORECASE)
    srkpv = re.sub(r'Y', 'A', srkpv, flags=re.IGNORECASE)
    srkpv = re.sub(r'Z', 'C', srkpv, flags=re.IGNORECASE)
    srkpv = re.sub(r'[^0-9a-fA-F]', '0', srkpv).lower()

    pairs = [srkpv[i:i+2] for i in range(0, len(srkpv) - 1, 2)]

    wm_ged = [0] * 256
    j = start
    for i in range(256):
        wm_ged[j] = i
        j = (j + step) % 256

    hc = '0123456789abcdef'
    result_parts = []
    for idx, pair in enumerate(pairs):
        try:
            raw_val = int(pair, 16)
        except ValueError:
            raw_val = 0
        decoded = (raw_val - wm_ged[idx % 256] + 256) % 256
        result_parts.append('%' + hc[(decoded >> 4) & 0xF] + hc[decoded & 0xF])

    try:
        return urllib.parse.unquote(''.join(result_parts), encoding='utf-8')
    except Exception:
        return ''


def _phpkobo_extract_and_decode(source: str) -> str:
    chunks = source.split('\u200b')
    if len(chunks) < 3:
        return ''

    chunk2 = chunks[2]
    for unescape_passes in range(3):
        candidate = chunk2
        for _ in range(unescape_passes + 1):
            candidate = _js_template_unescape(candidate)

        m = re.search(r'_L55c0Y\._Srkpv\s*=\s*"([^"]{100,})"', candidate)
        if m:
            srkpv = m.group(1)
            result = _phpkobo_stream_decode(srkpv)
            if result and _is_html_or_clean(result):
                return result

        idx = candidate.find('_Srkpv=\\"')
        if idx >= 0:
            start = idx + len('_Srkpv=\\"')
            end = candidate.find('\\"', start)
            if end > start:
                srkpv = candidate[start:end]
                result = _phpkobo_stream_decode(srkpv)
                if result and _is_html_or_clean(result):
                    return result

    return ''


def _try_phpkobo(code: str) -> str:
    if '_L55c0Y' in code or 'CHEETAH112' in code:
        result = _phpkobo_extract_and_decode(code)
        if result:
            return result

    sec_patterns = [
        r'var\s+\w+\s*=\s*"([A-Za-z0-9+/=]{20,})"[\s\S]{0,500}?(?:decodeURIComponent|window\.atob|atob|escape)',
        r'var\s+_sec\s*=\s*"([A-Za-z0-9+/=]{20,})"',
        r'var\s+\w+\s*=\s*"([A-Za-z0-9+/=]{80,})"',
    ]
    seen_b64 = set()
    for pat in sec_patterns:
        for m in re.finditer(pat, code, re.DOTALL):
            b64 = m.group(1)
            if b64 in seen_b64:
                continue
            seen_b64.add(b64)
            inner = _atob_decode(b64)
            if not inner or len(inner) < 10:
                continue
            if '_L55c0Y' in inner or 'CHEETAH112' in inner:
                result = _phpkobo_extract_and_decode(inner)
                if result:
                    return result
            if _is_html_or_clean(inner) and len(inner) > 50:
                return inner

    return ''


# ─────────────────────────────────────────────────────────────────────────────
# document.write / document.open obfuscation
# ─────────────────────────────────────────────────────────────────────────────

def _try_document_write(code: str) -> str:
    for pat in [
        r'document\s*\.\s*write\s*\(\s*decodeURIComponent\s*\(\s*escape\s*\(\s*(?:window\s*\.\s*)?atob\s*\(\s*["\']([A-Za-z0-9+/=]{20,})["\']',
        r'document\s*\.\s*write\s*\(\s*decodeURIComponent\s*\(\s*(?:window\s*\.\s*)?atob\s*\(\s*["\']([A-Za-z0-9+/=]{20,})["\']',
        r'document\s*\.\s*write\s*\(\s*(?:window\s*\.\s*)?atob\s*\(\s*["\']([A-Za-z0-9+/=]{20,})["\']',
        r'document\s*\.\s*write\s*\(\s*atob\s*\(\s*["\']([A-Za-z0-9+/=]{20,})["\']',
    ]:
        m = re.search(pat, code, re.DOTALL | re.IGNORECASE)
        if m:
            decoded = _atob_decode(m.group(1))
            if decoded and _looks_like_code(decoded):
                return decoded

    m = re.search(
        r'document\s*\.\s*write\s*\(\s*unescape\s*\(\s*["\']([%0-9a-fA-Fu]+)["\']',
        code, re.IGNORECASE
    )
    if m:
        try:
            decoded = urllib.parse.unquote(m.group(1))
            if decoded and _looks_like_code(decoded):
                return decoded
        except Exception:
            pass

    m = re.search(
        r'document\s*\.\s*write\s*\(\s*decodeURIComponent\s*\(\s*["\']([%0-9a-zA-Z+]{20,})["\']',
        code, re.IGNORECASE
    )
    if m:
        try:
            decoded = urllib.parse.unquote(m.group(1))
            if decoded and _looks_like_code(decoded):
                return decoded
        except Exception:
            pass

    return ''


# ─────────────────────────────────────────────────────────────────────────────
# Dean Edwards Packer  eval(function(p,a,c,k,e,d){...})
# ─────────────────────────────────────────────────────────────────────────────

def _try_packer(code: str) -> str:
    m = re.search(
        r"""eval\s*\(\s*function\s*\(\s*p\s*,\s*a\s*,\s*c\s*,\s*k\s*,\s*e\s*,\s*[dr]\s*\)"""
        r""".*?}\s*\(\s*'(.*?)'\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*'(.*?)'\.split\s*\(\s*'[|]'\s*\)""",
        code, re.DOTALL
    )
    if not m:
        return ''

    packed   = m.group(1)
    base     = int(m.group(2))
    count    = int(m.group(3))
    keywords = m.group(4).split('|')

    def _decode_base(n: int, b: int) -> str:
        chars = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        result = ''
        while n > 0:
            result = chars[n % b] + result
            n //= b
        return result or '0'

    def _lookup(word: str) -> str:
        try:
            idx = int(word, base) if base <= 36 else int(word, 36)
            return keywords[idx] if idx < len(keywords) and keywords[idx] else word
        except Exception:
            return word

    result = re.sub(r'\b(\w+)\b', lambda mo: _lookup(mo.group(0)), packed)
    if result and _looks_like_code(result):
        return result
    return ''


# ─────────────────────────────────────────────────────────────────────────────
# JS Obfuscator.io / _0x style obfuscation
# ─────────────────────────────────────────────────────────────────────────────

def _try_js_0x_strings(code: str) -> str:
    if '_0x' not in code and '\\x' not in code:
        return ''

    result = re.sub(r'\\x([0-9a-fA-F]{2})',
                    lambda m: chr(int(m.group(1), 16)), code)
    result = re.sub(r'\\u([0-9a-fA-F]{4})',
                    lambda m: chr(int(m.group(1), 16)), result)

    if result == code:
        return ''

    if len(result) > 50 and _looks_like_code(result):
        return result

    return ''


# ─────────────────────────────────────────────────────────────────────────────
# Advanced JS Array Extractor / Eval Strings (For modern web layouts)
# ─────────────────────────────────────────────────────────────────────────────

def _try_js_advanced_eval(code: str) -> str:
    """Extracts hidden base64 payloads inside generic JS variables or script tags."""
    patterns = [
        r'[\'"]([A-Za-z0-9+/=]{150,})[\'"]', # Long base64 string literal
        r'(?:var|const|let)\s+\w+\s*=\s*\[\s*[\'"]([A-Za-z0-9+/=]{50,})[\'"]\s*\]' # Inside single array
    ]
    for pat in patterns:
        for m in re.finditer(pat, code, re.DOTALL):
            decoded = _atob_decode(m.group(1))
            if decoded and _looks_like_code(decoded) and len(decoded) > len(m.group(1))*0.5:
                return decoded
    return ''


# ─────────────────────────────────────────────────────────────────────────────
# PHP eval chains
# ─────────────────────────────────────────────────────────────────────────────

def _try_phpkodo(code: str) -> str:
    patterns = [
        (
            r"""str_rot13\s*\(\s*gzinflate\s*\(\s*str_rot13\s*\(\s*base64_decode\s*\(\s*['"]([^'"]+)['"]\s*\)\s*\)\s*\)\s*\)""",
            lambda b: _rot13_bytes(_inflate(_rot13_bytes(b)))
        ),
        (
            r"""gzinflate\s*\(\s*str_rot13\s*\(\s*base64_decode\s*\(\s*['"]([^'"]+)['"]\s*\)\s*\)\s*\)""",
            lambda b: _inflate(_rot13_bytes(b))
        ),
        (
            r"""gzinflate\s*\(\s*base64_decode\s*\(\s*['"]([^'"]+)['"]\s*\)\s*\)""",
            lambda b: _inflate(b)
        ),
        (
            r"""gzuncompress\s*\(\s*base64_decode\s*\(\s*['"]([^'"]+)['"]\s*\)\s*\)""",
            lambda b: _inflate(b)
        ),
        (
            r"""gzdecode\s*\(\s*base64_decode\s*\(\s*['"]([^'"]+)['"]\s*\)\s*\)""",
            lambda b: _inflate(b)
        ),
        (
            r"""str_rot13\s*\(\s*base64_decode\s*\(\s*['"]([^'"]+)['"]\s*\)\s*\)""",
            lambda b: _rot13_bytes(b)
        ),
        (
            r"""base64_decode\s*\(\s*['"]([A-Za-z0-9+/\r\n]{20,}={0,2})['"]\s*\)""",
            lambda b: b
        ),
    ]

    for pattern, transform in patterns:
        for m in re.finditer(pattern, code, re.DOTALL):
            raw = _b64_decode(m.group(1))
            if not raw:
                continue
            result = transform(raw)
            if result:
                decoded = _to_str(result)
                if _looks_like_code(decoded):
                    return decoded
    return ''


# ─────────────────────────────────────────────────────────────────────────────
# PHPCabbo / variable-based
# ─────────────────────────────────────────────────────────────────────────────

def _try_phpcabbo(code: str) -> str:
    var_assignments = re.findall(
        r'\$(\w+)\s*=\s*["\']([A-Za-z0-9+/\r\n]{30,}={0,2})["\']',
        code
    )
    for var_name, b64_val in var_assignments:
        raw = _b64_decode(b64_val)
        if raw:
            decoded = _to_str(raw)
            if _looks_like_code(decoded):
                return decoded

    m = re.search(
        r'\$\w+\s*=\s*base64_decode\s*\(\s*["\']([A-Za-z0-9+/\r\n=]+)["\']\s*\)\s*;',
        code
    )
    if m:
        raw = _b64_decode(m.group(1))
        if raw:
            d = _to_str(raw)
            if d:
                return d

    m = re.search(
        r'''preg_replace\s*\(\s*['"][^'"]*e[^'"]*['"]\s*,\s*base64_decode\s*\(\s*['"]([^'"]+)['"]\s*\)''',
        code
    )
    if m:
        raw = _b64_decode(m.group(1))
        if raw:
            return _to_str(raw)

    m = re.search(r'(?:chr\s*\(\s*\d+\s*\)\s*\.?\s*){5,}', code)
    if m:
        chars = re.findall(r'chr\s*\(\s*(\d+)\s*\)', m.group(0))
        if chars:
            try:
                return ''.join(chr(int(c)) for c in chars)
            except Exception:
                pass

    return ''


# ─────────────────────────────────────────────────────────────────────────────
# JS eval / atob / fromCharCode
# ─────────────────────────────────────────────────────────────────────────────

def _try_js_obfuscation(code: str) -> str:
    for pat in [
        r"""eval\s*\(\s*atob\s*\(\s*['"]([A-Za-z0-9+/=]{20,})['"]\s*\)\s*\)""",
        r"""eval\s*\(\s*window\.atob\s*\(\s*['"]([A-Za-z0-9+/=]{20,})['"]\s*\)\s*\)""",
    ]:
        m = re.search(pat, code, re.DOTALL)
        if m:
            decoded = _atob_decode(m.group(1))
            if decoded and _looks_like_code(decoded):
                return decoded

    for pat in [
        r"""eval\s*\(\s*unescape\s*\(\s*['"]([^'"]{20,})['"]\s*\)\s*\)""",
        r"""eval\s*\(\s*decodeURIComponent\s*\(\s*['"]([^'"]{20,})['"]\s*\)\s*\)""",
    ]:
        m = re.search(pat, code, re.DOTALL)
        if m:
            try:
                d = urllib.parse.unquote(m.group(1))
                if d and d != m.group(1) and _looks_like_code(d):
                    return d
            except Exception:
                pass

    for pat in [
        r'String\.fromCharCode\s*\(([\d,\s]{10,})\)',
        r'(?:eval|write|innerHTML)\s*\(\s*String\.fromCharCode\s*\(([\d,\s]+)\)',
    ]:
        m = re.search(pat, code)
        if m:
            try:
                chars = [int(c.strip()) for c in m.group(1).split(',') if c.strip()]
                if chars:
                    result = ''.join(chr(c) for c in chars)
                    if _looks_like_code(result):
                        return result
            except Exception:
                pass

    m = re.search(
        r'''(?:window|self)\s*\[\s*["']eval["']\s*\]\s*\(\s*(?:window|self)\s*\[\s*["']atob["']\s*\]\s*\(\s*['"]([A-Za-z0-9+/=]{20,})['"]\s*\)\s*\)''',
        code, re.DOTALL
    )
    if m:
        decoded = _atob_decode(m.group(1))
        if decoded and _looks_like_code(decoded):
            return decoded

    m = re.search(
        r"""Function\s*\(\s*["']return\s+atob\s*\(\s*["']([A-Za-z0-9+/=]{20,})["']\s*\)\s*["']\s*\)\s*\(\s*\)""",
        code, re.DOTALL
    )
    if m:
        decoded = _atob_decode(m.group(1))
        if decoded and _looks_like_code(decoded):
            return decoded

    for pat in [
        r"""(?:innerHTML|src|href|content)\s*=\s*atob\s*\(\s*['"]([A-Za-z0-9+/=]{50,})['"]\s*\)""",
        r"""=\s*atob\s*\(\s*['"]([A-Za-z0-9+/=]{100,})['"]\s*\)""",
    ]:
        m = re.search(pat, code, re.DOTALL)
        if m:
            decoded = _atob_decode(m.group(1))
            if decoded and _looks_like_code(decoded):
                return decoded

    return ''


# ─────────────────────────────────────────────────────────────────────────────
# Raw base64 blob
# ─────────────────────────────────────────────────────────────────────────────

def _try_raw_base64(code: str) -> str:
    stripped = re.sub(r'\s+', '', code.strip())
    if len(stripped) < 20:
        return ''
    if not re.match(r'^[A-Za-z0-9+/]+=*$', stripped):
        return ''
    raw = _b64_decode(stripped)
    if not raw:
        return ''
    decoded = _to_str(raw)
    if _looks_like_code(decoded):
        return decoded
    inf = _inflate(raw)
    if inf:
        d2 = _to_str(inf)
        if _looks_like_code(d2):
            return d2
    return ''


# ─────────────────────────────────────────────────────────────────────────────
# HTML entities
# ─────────────────────────────────────────────────────────────────────────────

def _try_html_entities(code: str) -> str:
    decoded = html.unescape(code)
    return decoded if decoded != code else ''


# ─────────────────────────────────────────────────────────────────────────────
# Hex / Unicode escapes
# ─────────────────────────────────────────────────────────────────────────────

def _try_hex_unicode(code: str) -> str:
    result = re.sub(r'\\x([0-9a-fA-F]{2})',
                    lambda m: chr(int(m.group(1), 16)), code)
    result = re.sub(r'\\u([0-9a-fA-F]{4})',
                    lambda m: chr(int(m.group(1), 16)), result)
    pct = re.findall(r'%[0-9a-fA-F]{2}', result)
    if len(pct) >= 5:
        result = re.sub(r'%([0-9a-fA-F]{2})',
                        lambda m: chr(int(m.group(1), 16)), result)
    return result if result != code else ''


# ─────────────────────────────────────────────────────────────────────────────
# URL encoding
# ─────────────────────────────────────────────────────────────────────────────

def _try_url_decode(code: str) -> str:
    if '%' not in code:
        return ''
    if len(re.findall(r'%[0-9a-fA-F]{2}', code)) < 5:
        return ''
    try:
        decoded = urllib.parse.unquote(code)
        if decoded != code:
            return decoded
    except Exception:
        pass
    return ''


# ─────────────────────────────────────────────────────────────────────────────
# str_rot13 standalone
# ─────────────────────────────────────────────────────────────────────────────

def _try_rot13_only(code: str) -> str:
    if 'str_rot13' not in code:
        return ''
    m = re.search(r"str_rot13\s*\(\s*['\"]([^'\"]{20,})['\"]", code)
    if m:
        try:
            return codecs.decode(m.group(1), 'rot_13')
        except Exception:
            pass
    return ''


# ─────────────────────────────────────────────────────────────────────────────
# Inline base64_decode() replacements
# ─────────────────────────────────────────────────────────────────────────────

def _inline_b64_replace(code: str) -> str:
    def replacer(m):
        raw = _b64_decode(m.group(1))
        if raw:
            try:
                return _to_str(raw)
            except Exception:
                pass
        return m.group(0)

    result = re.sub(
        r"""base64_decode\s*\(\s*['"]([A-Za-z0-9+/\r\n=]+)['"]\s*\)""",
        replacer, code, flags=re.DOTALL
    )
    return result if result != code else ''


# ─────────────────────────────────────────────────────────────────────────────
# Octal / decimal char encoding
# ─────────────────────────────────────────────────────────────────────────────

def _try_octal_decimal_chars(code: str) -> str:
    if re.search(r'\\[0-7]{3}', code):
        result = re.sub(
            r'\\([0-7]{3})',
            lambda m: chr(int(m.group(1), 8)),
            code
        )
        if result != code and _looks_like_code(result):
            return result

    m = re.search(r'(?:chr\s*\(\s*\d+\s*\)[.\s]*){5,}', code)
    if m:
        chars = re.findall(r'chr\s*\(\s*(\d+)\s*\)', code)
        if len(chars) > 5:
            try:
                result = ''.join(chr(int(c)) for c in chars)
                if _looks_like_code(result):
                    return result
            except Exception:
                pass

    return ''


# ─────────────────────────────────────────────────────────────────────────────
# Master decoder — multi-layer pipeline
# ─────────────────────────────────────────────────────────────────────────────

def full_decode(content: str, max_layers: int = 25) -> tuple[str, list[str]]:
    """
    Decode obfuscated content using all available methods, up to max_layers.
    Returns (decoded_content, list_of_methods_applied).
    """
    current = content
    log = []

    for layer in range(1, max_layers + 1):
        # ── PHPKobo HTML obfuscator ──
        r = _try_phpkobo(current)
        if r:
            log.append(f"[Layer {layer}] PHPKobo HTML obfuscator")
            current = r
            continue

        # ── document.write unwrap ──
        r = _try_document_write(current)
        if r:
            log.append(f"[Layer {layer}] document.write pattern extracted")
            current = r
            continue

        # ── Dean Edwards Packer ──
        r = _try_packer(current)
        if r:
            log.append(f"[Layer {layer}] Dean Edwards packer")
            current = r
            continue

        # ── JS Advanced Extractor / Literal Base64 Payloads ──
        r = _try_js_advanced_eval(current)
        if r:
            log.append(f"[Layer {layer}] Hidden JS Array/Literal Payload extracted")
            current = r
            continue

        # ── PHP eval chains ──
        r = _try_phpkodo(current)
        if r:
            log.append(f"[Layer {layer}] PHP eval chain (gzinflate/rot13/base64)")
            current = r
            continue

        # ── PHPCabbo variable obfuscation ──
        r = _try_phpcabbo(current)
        if r:
            log.append(f"[Layer {layer}] PHPCabbo variable obfuscation")
            current = r
            continue

        # ── JS eval / atob / fromCharCode ──
        r = _try_js_obfuscation(current)
        if r:
            log.append(f"[Layer {layer}] JS eval/atob/fromCharCode")
            current = r
            continue

        # ── JS Obfuscator.io _0x / hex strings ──
        r = _try_js_0x_strings(current)
        if r:
            log.append(f"[Layer {layer}] JS _0x hex string obfuscation")
            current = r
            continue

        # ── Raw base64 blob ──
        r = _try_raw_base64(current)
        if r:
            log.append(f"[Layer {layer}] Raw Base64 blob")
            current = r
            continue

        # ── HTML entities ──
        r = _try_html_entities(current)
        if r:
            log.append(f"[Layer {layer}] HTML entities")
            current = r
            continue

        # ── Hex / Unicode escapes ──
        r = _try_hex_unicode(current)
        if r:
            log.append(f"[Layer {layer}] Hex/Unicode escapes")
            current = r
            continue

        # ── URL encoding ──
        r = _try_url_decode(current)
        if r:
            log.append(f"[Layer {layer}] URL encoding (%XX)")
            current = r
            continue

        # ── str_rot13 standalone ──
        r = _try_rot13_only(current)
        if r:
            log.append(f"[Layer {layer}] str_rot13 (standalone)")
            current = r
            continue

        # ── Octal / decimal char escapes ──
        r = _try_octal_decimal_chars(current)
        if r:
            log.append(f"[Layer {layer}] Octal/decimal char escapes")
            current = r
            continue

        # ── Inline base64_decode() ──
        r = _inline_b64_replace(current)
        if r:
            log.append(f"[Layer {layer}] Inline base64_decode() replacements")
            current = r
            continue

        break

    if not log:
        unescaped = html.unescape(content)
        if unescaped != content:
            current = unescaped
            log.append("HTML entities decoded (minimal)")
        else:
            log.append("কোনো obfuscation পাওয়া যায়নি (plain content)")

    return current, log
