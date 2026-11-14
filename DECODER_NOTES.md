# Decoder update notes

The target `autobet_obf.html` contains a custom JavaScript state-machine cipher with anti-analysis checks. The new `advanced_decoder.py` performs only static, non-executing transforms and returns a `DecodeReport`.

A report is marked `complete=False` when `eval`, `new Function`, anti-debugging checks, or unresolved `_0x`/`Math.imul`/`fromCharCode` logic remains. This prevents the Telegram bot from sending a file with a misleading “fully decoded” status.

The existing `decoder.py` and `bot.py` still need an integration patch to call `decode_with_report` and expose the warning list in Telegram. That integration should be added only after the current handlers are edited with a full-file patch and syntax/tests are run.
