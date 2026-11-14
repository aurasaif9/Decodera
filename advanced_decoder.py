"""Safe, non-executing HTML deobfuscation helpers.

This module extracts common static layers without evaluating untrusted JavaScript.
It also provides an explicit completeness report so callers do not claim a file is
fully decoded when a custom runtime cipher remains.
"""
from __future__ import annotations

import base64
import html
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class DecodeReport:
    content: str
    methods: list[str] = field(default_factory=list)
    complete: bool = False
    warnings: list[str] = field(default_factory=list)


def _b64(value: str) -> Optional[str]:
    compact = re.sub(r"\s+", "", value)
    if len(compact) < 16 or not re.fullmatch(r"[A-Za-z0-9+/]*={0,2}", compact):
        return None
    try:
        raw = base64.b64decode(compact + "=" * (-len(compact) % 4), validate=False)
        text = raw.decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    return text if _looks_like_source(text) else None


def _looks_like_source(value: str) -> bool:
    markers = ("<html", "<!doctype", "<body", "<script", "<style", "function", "document.", "window.", "const ", "let ", "var ")
    return len(value) >= 20 and any(marker in value.lower() for marker in markers)


def _rc4(data: bytes, key: bytes) -> bytes:
    if not key:
        raise ValueError("RC4 key must not be empty")
    box = list(range(256))
    j = 0
    for i in range(256):
        j = (j + box[i] + key[i % len(key)]) & 255
        box[i], box[j] = box[j], box[i]
    out = bytearray()
    i = j = 0
    for byte in data:
        i = (i + 1) & 255
        j = (j + box[i]) & 255
        box[i], box[j] = box[j], box[i]
        out.append(byte ^ box[(box[i] + box[j]) & 255])
    return bytes(out)


def _decode_protected_rc4(source: str) -> Optional[tuple[str, str]]:
    """Decode the repository's older SAIF RC4 wrapper, if present."""
    token = re.search(r"\[TOKEN:\s*([A-Za-z0-9]{16})\]", source)
    array = re.search(r"\bvar\s+_A\s*=\s*\[([^\]]+)\]", source, re.I | re.S)
    if not token or not array:
        return None
    try:
        numbers = [int(item) for item in re.findall(r"\d+", array.group(1))]
        hex_text = "".join(chr(number) for number in numbers)
        ciphertext = bytes.fromhex(hex_text)
        decoded_b64 = _rc4(ciphertext, token.group(1).encode("ascii"))
        payload = base64.b64decode(decoded_b64, validate=True)
        text = urllib.parse.unquote(payload.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, base64.binascii.Error):
        return None
    return (text, "Protected RC4 wrapper") if _looks_like_source(text) else None


def _replace_static_base64(source: str) -> Optional[str]:
    changed = False

    def replace(match: re.Match[str]) -> str:
        nonlocal changed
        decoded = _b64(match.group(2))
        if decoded is None:
            return match.group(0)
        changed = True
        return match.group(1) + decoded + match.group(3)

    result = re.sub(r"(['\"])([A-Za-z0-9+/=]{24,})(\1)", replace, source)
    return result if changed and result != source else None


def _one_pass(source: str) -> tuple[Optional[str], Optional[str]]:
    rc4 = _decode_protected_rc4(source)
    if rc4:
        return rc4

    entity_decoded = html.unescape(source)
    if entity_decoded != source:
        return entity_decoded, "HTML entities"

    url_decoded = urllib.parse.unquote(source)
    if url_decoded != source and len(re.findall(r"%[0-9A-Fa-f]{2}", source)) >= 4:
        return url_decoded, "URL encoding"

    static_b64 = _replace_static_base64(source)
    if static_b64:
        return static_b64, "Static Base64 literal"

    return None, None


def decode_with_report(source: str, max_layers: int = 25) -> DecodeReport:
    """Decode static layers and report whether the result is complete.

    JavaScript is never executed. Files containing custom state-machine ciphers,
    anti-debugging gates, or unresolved eval payloads are marked incomplete.
    """
    if not isinstance(source, str) or not source.strip():
        raise ValueError("source must be a non-empty string")
    if not 1 <= max_layers <= 100:
        raise ValueError("max_layers must be between 1 and 100")

    current = source
    methods: list[str] = []
    for _ in range(max_layers):
        decoded, method = _one_pass(current)
        if decoded is None:
            break
        current = decoded
        methods.append(method or "unknown")

    unresolved = []
    if re.search(r"\beval\s*\(|new\s+Function\s*\(", current, re.I):
        unresolved.append("runtime eval/new Function remains")
    if re.search(r"anti.?debug|debugger|webdriver|HeadlessChrome", current, re.I):
        unresolved.append("anti-analysis/runtime gate remains")
    if re.search(r"_0x[0-9a-f]+|Math\.imul|fromCharCode|String\.fromCharCode", current):
        unresolved.append("custom JavaScript state-machine layer remains")

    return DecodeReport(
        content=current,
        methods=methods,
        complete=bool(methods) and not unresolved and _looks_like_source(current),
        warnings=unresolved,
    )


__all__ = ["DecodeReport", "decode_with_report"]
