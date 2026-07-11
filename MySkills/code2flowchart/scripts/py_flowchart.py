#!/usr/bin/env python3
"""Python language support for code2flowchart — STUB (not yet implemented).

This is a template implementation that documents the interface contract and
outlines what a real Python control-flow extractor would need to handle.

To implement, a real tokenizer/parser would need to process:
- **Branching:** ``if`` / ``elif`` / ``else``
- **Loops:** ``for`` (iterable), ``while``, ``for``/``else``, ``while``/``else``
- **Exception flow:** ``try`` / ``except`` / ``else`` / ``finally``, ``raise``,
  ``assert`` (treat as conditional raise)
- **Context managers:** ``with`` (enter/exit flow; no explicit control-flow
  edges, but ``__exit__`` can suppress exceptions)
- **Pattern matching:** ``match`` / ``case`` (3.10+) — maps to switch-like
  control flow
- **Exits:** ``return``, ``yield``, ``yield from``
- **Jumps:** ``break``, ``continue``
- **Comprehensions:** list/dict/set/genexpr — treat as single process nodes
  (no sub-graph), but note that genexpr evaluation is lazy
- **Decorators:** strip ``@decorator`` lines; they wrap the function but
  don't add control-flow nodes
- **Async:** ``async def``, ``await``, ``async for``, ``async with`` — treat
  ``await`` as a potentially-suspending call node; ``async for``/``async with``
  map to the sync equivalents
"""
from typing import Any

from lang_support import LanguageSupport, register


@register
class PyFlowchart(LanguageSupport):
    """Python control-flow extraction — **not yet implemented**."""

    name = "python"
    file_extensions = [".py", ".pyw", ".pyi"]
    display_name = "Python"

    def tokenize(self, code: str) -> list[Any]:
        raise NotImplementedError(
            "Python tokenizer is not yet implemented. "
            "See the class docstring for the interface contract."
        )

    def parse(self, tokens: list[Any]) -> list[Any]:
        raise NotImplementedError(
            "Python parser is not yet implemented."
        )

    def build_graph(
        self,
        functions: list[Any],
        detail_level: str = "full",
    ) -> Any:
        raise NotImplementedError(
            "Python graph builder is not yet implemented."
        )
