#!/usr/bin/env python3
"""C/C++ language support for code2flowchart (reference implementation).

This is the default and currently the only fully-implemented language support.
It wraps the existing ``CTokenizer`` and ``CParser`` from ``code2flowchart.py``.
"""

from pathlib import Path
from typing import Any

from lang_support import LanguageSupport, register


@register
class CFlowchart(LanguageSupport):
    """C/C++ control-flow extraction via code2flowchart's built-in parser."""

    name = "c"
    file_extensions = [".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hxx"]
    display_name = "C/C++"

    def tokenize(self, code: str) -> list[Any]:
        from code2flowchart import CTokenizer

        tokenizer = CTokenizer(code)
        return list(tokenizer)

    def parse(self, tokens: list[Any]) -> list[Any]:
        from code2flowchart import CParser

        parser = CParser(tokens)
        return parser.parse_functions()

    def build_graph(
        self,
        functions: list[Any],
        detail_level: str = "full",
    ) -> Any:
        from code2flowchart import FlowBuilder, FunctionFlow

        if not functions:
            raise ValueError("no functions parsed from source")

        target = functions[0]
        builder = FlowBuilder(target.body, detail_level)
        builder.build()
        graph = builder.readout()
        graph.functions = [FunctionFlow(name=target.name,
                                         start_id=graph.start_id,
                                         end_id=graph.end_id)]
        return graph

    def validate_code(self, code: str) -> list[str]:
        warnings: list[str] = []
        # Macro-heavy code may hide control flow
        macro_lines = [l for l in code.split("\n")
                       if l.strip().startswith("#define")]
        if len(macro_lines) > 5:
            warnings.append(
                "Source has 5+ #define macros. Expand macros that hide "
                "return/goto/break before conversion, or mark them as uncertain."
            )
        # Inline assembly is not parsed
        if "__asm" in code or "__asm__" in code or "asm volatile" in code:
            warnings.append(
                "Source contains inline assembly — control flow inside asm "
                "blocks is not modelled."
            )
        # Template-heavy code may confuse the lightweight parser
        if code.count("template<") > 2:
            warnings.append(
                "Template-heavy source detected. Simplify or extract "
                "the instantiated form for better results."
            )
        return warnings


# Register C as the default fallback
_LANG = CFlowchart()
