#!/usr/bin/env python3
"""通过主转换器提供 C/C++ 适配，复用相同的预处理、解析和建图逻辑。"""

from typing import Any

from lang_support import LanguageSupport, register


@register
class CFlowchart(LanguageSupport):
    """使用主转换器的轻量解析器提取 C/C++ 可见控制流。"""

    name = "c"
    file_extensions = [".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hxx"]
    display_name = "C/C++"

    def tokenize(self, code: str) -> list[Any]:
        from code2flowchart import CTokenizer, select_preprocessor_branches

        selected = select_preprocessor_branches(code)
        return CTokenizer(selected).tokenize()

    def parse(self, tokens: list[Any]) -> list[Any]:
        from code2flowchart import CParser

        parser = CParser(tokens)
        return parser.parse_functions()

    def build_graph(
        self,
        functions: list[Any],
        detail_level: str = "standard",
    ) -> Any:
        from code2flowchart import build_graph

        if not functions:
            raise ValueError("no functions parsed from source")

        return build_graph(functions, detail_level)

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
