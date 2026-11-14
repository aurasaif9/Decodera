import base64

from advanced_decoder import decode_with_report
from runtime_decoder import decode_in_isolated_runtime


def test_static_base64_is_decoded_and_reported_complete():
    payload = '<!doctype html><html><body>ok</body></html>'
    encoded = base64.b64encode(payload.encode()).decode()
    report = decode_with_report(f'<script>const data = "{encoded}";</script>')

    assert payload in report.content
    assert "Static Base64 literal" in report.methods
    assert report.complete is True
    assert report.warnings == []


def test_runtime_obfuscation_is_not_claimed_complete_by_static_decoder():
    report = decode_with_report(
        '<script>var _0xabc = String.fromCharCode(60,104); eval(_0xabc);</script>'
    )

    assert report.complete is False
    assert report.warnings
    assert "custom JavaScript state-machine layer remains" in report.warnings


def test_isolated_runtime_captures_document_output_when_node_is_available():
    source = '<script>document.write("<html><body>runtime</body></html>");</script>'
    report = decode_in_isolated_runtime(source)

    if report.warnings == ["Node.js runtime is unavailable"]:
        return
    assert report.complete is True
    assert "runtime" in report.content
