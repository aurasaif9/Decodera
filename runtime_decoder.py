"""Optional isolated runtime decoder for browser-style HTML wrappers.

The target file is not a normal Base64/RC4 wrapper: its payload is released only
by a JavaScript state machine. This module runs that JavaScript in a short-lived
Node `vm` context with browser shims, no network/process access, and a timeout.
It captures document output instead of opening a browser or executing the output
in the bot process.

This is intentionally separate from `advanced_decoder.py`: callers can choose
static-only decoding or explicitly opt into the isolated runtime path.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RuntimeDecodeReport:
    content: str
    complete: bool
    methods: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


_NODE_HARNESS = r"""
'use strict';
const fs = require('fs');
const vm = require('vm');
const source = JSON.parse(fs.readFileSync(0, 'utf8'));
const output = [];
const writes = [];
const document = {
  documentElement: { getAttribute: () => null },
  open: () => {},
  close: () => {},
  write: (value) => { const text = String(value); output.push(text); writes.push(text); },
  createTreeWalker: () => ({ nextNode: () => null }),
};
const window = { outerWidth: 1280, outerHeight: 720 };
const navigator = { userAgent: 'Mozilla/5.0 Chrome/120.0.0.0', webdriver: false };
window.window = window;
window.document = document;
window.navigator = navigator;
const sandbox = {
  window, document, navigator,
  console: { log: () => {}, warn: () => {}, error: () => {}, clear: () => {} },
  setInterval: () => 0, clearInterval: () => {}, setTimeout: () => 0, clearTimeout: () => {},
  atob: (value) => Buffer.from(String(value), 'base64').toString('latin1'),
  btoa: (value) => Buffer.from(String(value), 'latin1').toString('base64'),
  TextDecoder, TextEncoder, URL, decodeURIComponent, encodeURIComponent,
};
vm.createContext(sandbox, { name: 'decodera-isolated-html' });
try {
  vm.runInContext(source, sandbox, { timeout: 2500, displayErrors: false });
  process.stdout.write(JSON.stringify({ ok: true, output, writes }));
} catch (error) {
  process.stdout.write(JSON.stringify({ ok: false, error: String(error), output, writes }));
}
"""


def decode_in_isolated_runtime(source: str, timeout: float = 4.0) -> RuntimeDecodeReport:
    """Run a browser-style wrapper in an isolated Node VM and capture output.

    This does not claim that arbitrary JavaScript is safe. It only limits the
    bot-side exposure: no network APIs are provided, the process is separate,
    and Node's VM timeout is shorter than the subprocess timeout.
    """
    if not isinstance(source, str) or not source.strip():
        raise ValueError("source must be a non-empty string")
    if not 0.5 <= timeout <= 10:
        raise ValueError("timeout must be between 0.5 and 10 seconds")

    node = shutil.which("node")
    if not node:
        return RuntimeDecodeReport(
            content=source,
            complete=False,
            warnings=["Node.js runtime is unavailable"],
        )

    try:
        completed = subprocess.run(
            [node, "-e", _NODE_HARNESS],
            input=json.dumps(source),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return RuntimeDecodeReport(source, False, warnings=["runtime timeout"])
    except OSError as exc:
        return RuntimeDecodeReport(source, False, warnings=[f"runtime launch failed: {exc}"])

    if not completed.stdout:
        detail = completed.stderr.strip()[-300:]
        return RuntimeDecodeReport(source, False, warnings=[detail or "runtime returned no output"])

    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return RuntimeDecodeReport(source, False, warnings=["runtime returned invalid output"])

    captured = "".join(str(item) for item in result.get("output", []))
    if not captured:
        captured = "".join(str(item) for item in result.get("writes", []))
    if not captured:
        warning = result.get("error", "no document output captured")
        return RuntimeDecodeReport(source, False, warnings=[str(warning)])

    return RuntimeDecodeReport(
        content=captured,
        complete=bool(result.get("ok")) and captured != source,
        methods=["isolated browser-style JavaScript runtime"],
        warnings=[] if result.get("ok") else [str(result.get("error", "runtime failed"))],
    )


__all__ = ["RuntimeDecodeReport", "decode_in_isolated_runtime"]
