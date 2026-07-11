#!/usr/bin/env python3
"""JavaScript / TypeScript language support for code2flowchart — STUB.

This is a template documenting what a real JS/TS control-flow extractor
would need to handle.

To implement, a real tokenizer/parser would need to process:
- **Branching:** ``if`` / ``else if`` / ``else``, ternary ``? :``
- **Loops:** ``for`` (C-style), ``for...of``, ``for...in``, ``while``,
  ``do...while``
- **Switch:** ``switch`` / ``case`` / ``default`` — fall-through by default
  (unlike C which requires explicit break)
- **Exception flow:** ``try`` / ``catch`` / ``finally``, ``throw``
- **Exits:** ``return``, ``yield`` (generators)
- **Jumps:** ``break``, ``continue`` (with optional label for nested loops)
- **Arrow functions:** ``() => expr`` — treat as single expression node
  unless the body is a block
- **Async:** ``async function``, ``await``, ``for await...of``
- **Template literals:** `` `${expr}` `` — should not be confused with
  control-flow syntax
- **Optional chaining:** ``?.`` — may produce implicit nullish branches
  if short-circuit semantics are modelled
- **TypeScript specifics:** type annotations (``: string``), interfaces,
  enums — stripped during tokenization; ``as`` expressions, non-null
  assertions ``!``
"""
from typing import Any

from lang_support import LanguageSupport, register


@register
class JSFlowchart(LanguageSupport):
    """JavaScript / TypeScript control-flow extraction — **not yet implemented**."""

    name = "javascript"
    file_extensions = [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"]
    display_name = "JavaScript / TypeScript"

    def tokenize(self, code: str) -> list[Any]:
        raise NotImplementedError(
            "JavaScript tokenizer is not yet implemented. "
            "See the class docstring for the interface contract."
        )

    def parse(self, tokens: list[Any]) -> list[Any]:
        raise NotImplementedError("JavaScript parser is not yet implemented.")

    def build_graph(
        self,
        functions: list[Any],
        detail_level: str = "full",
    ) -> Any:
        raise NotImplementedError("JavaScript graph builder is not yet implemented.")
