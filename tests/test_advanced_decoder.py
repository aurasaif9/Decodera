import base64

from advanced_decoder import decode_with_report


def test_static_base64_is_decoded_and_reported_complete():
    payload = '<!doctype html><html><body>ok</body></html>'
    encoded = base64.b64encode(payload.encode()).decode()
    report = decode_with_report(f'<script>const data = "{encoded}";</script>')

    assert payload in report.content
    assert "Static Base64 literal" in report.methods
    assert report.complete is True
    assert report.warnings == []


def test_runtime_obfuscation_is_not_claimed_complete():
    report = decode_with_report(
        '<script>var _0xabc = String.fromCharCode(60,104); eval(_0xabc);</script>'
    )

    assert report.complete is False
    assert report.warnings
    assert "custom JavaScript state-machine layer remains" in report.warnings
