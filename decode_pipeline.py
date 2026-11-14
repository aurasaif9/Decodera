"""Iterative static/runtime capture pipeline for obfuscated HTML."""
from __future__ import annotations

from dataclasses import dataclass, field
from advanced_decoder import decode_with_report
from runtime_decoder import decode_in_isolated_runtime


@dataclass
class PipelineReport:
    content: str
    complete: bool
    methods: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def decode_all(source: str, max_rounds: int = 8) -> PipelineReport:
    if not isinstance(source, str) or not source.strip():
        raise ValueError("source must be a non-empty string")
    if not 1 <= max_rounds <= 20:
        raise ValueError("max_rounds must be between 1 and 20")

    current = source
    methods: list[str] = []
    warnings: list[str] = []
    changed = False

    for _ in range(max_rounds):
        static = decode_with_report(current)
        if static.content != current:
            current = static.content
            changed = True
            methods.extend(static.methods)
        warnings.extend(item for item in static.warnings if item not in warnings)

        runtime = decode_in_isolated_runtime(current)
        if runtime.content != current:
            current = runtime.content
            changed = True
            methods.extend(runtime.methods)
            if runtime.complete:
                warnings = [item for item in warnings if item != "runtime eval/new Function remains"]
            continue
        warnings.extend(item for item in runtime.warnings if item not in warnings)
        break

    unresolved = bool(warnings)
    return PipelineReport(
        content=current,
        complete=changed and not unresolved,
        methods=methods,
        warnings=warnings,
    )


__all__ = ["PipelineReport", "decode_all"]
