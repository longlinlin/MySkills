#!/usr/bin/env python3
"""Go language support for code2flowchart — STUB (not yet implemented).

This is a template documenting what a real Go control-flow extractor
would need to handle.

To implement, a real tokenizer/parser would need to process:
- **Branching:** ``if`` / ``else if`` / ``else``; ``if`` with short statement
  (``if x := f(); x > 0 { ... }``)
- **Loops:** ``for`` is the only loop keyword — covers:
  - C-style: ``for i := 0; i < n; i++ { ... }``
  - While-style: ``for cond { ... }``
  - Infinite: ``for { ... }``
  - Range: ``for i, v := range slice { ... }``
- **Switch:** ``switch`` / ``case`` / ``default`` — no fall-through by default;
  ``fallthrough`` keyword forces explicit fall-through
- **Type switch:** ``switch v := x.(type) { case int: ... }``
  — maps to switch-like flow
- **Select:** ``select { case ch <- v: ... case <-ch: ... default: ... }``
  — non-deterministic choice; each case is a possible branch
- **Exception flow:** ``panic`` / ``recover`` — treat ``panic`` as a
  terminating branch, ``recover`` only meaningful inside ``defer``
- **Defer:** ``defer f()`` — runs at function exit; treat as annotation
  unless the deferred function contains control flow that affects the
  caller (rare)
- **Goroutines:** ``go f()`` — launches concurrent execution; treat as a
  labelled process node since the goroutine's control flow is independent
- **Exits:** ``return`` (single or multiple values)
- **Jumps:** ``break``, ``continue`` (with optional label)
- **Goto:** ``goto label`` (with ``label:`` statement) — used in error
  cleanup patterns; treat identically to C goto
- **Error patterns:** ``if err != nil { return ... }`` — a dominant idiom
  that may warrant compaction in the diagram
"""
from typing import Any

from lang_support import LanguageSupport, register


@register
class GoFlowchart(LanguageSupport):
    """Go control-flow extraction — **not yet implemented**."""

    name = "go"
    file_extensions = [".go"]
    display_name = "Go"

    def tokenize(self, code: str) -> list[Any]:
        raise NotImplementedError(
            "Go tokenizer is not yet implemented. "
            "See the class docstring for the interface contract."
        )

    def parse(self, tokens: list[Any]) -> list[Any]:
        raise NotImplementedError("Go parser is not yet implemented.")

    def build_graph(
        self,
        functions: list[Any],
        detail_level: str = "full",
    ) -> Any:
        raise NotImplementedError("Go graph builder is not yet implemented.")
