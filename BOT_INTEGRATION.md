# Integration guide for `bot.py`

Import the report decoder alongside the legacy decoder:

```python
from advanced_decoder import decode_with_report
```

Replace `_run_decode` with a handler that calls `decode_with_report(raw)` and includes `report.complete` plus `report.warnings` in the caption. Keep `full_decode` as a fallback for legacy formats, but do not label output as fully decoded unless the report says `complete=True`.

The existing `autobet_obf.html` is a newer custom state-machine format. It intentionally contains anti-analysis checks and is not safely decodable by regex-only code. Do not execute its JavaScript in the bot process.
