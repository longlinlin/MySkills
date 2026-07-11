#!/usr/bin/env python3
"""Multi-language extraction framework for code2flowchart.

Provides a registration-based plugin architecture for adding new source-language
parsers. Each language extends ``LanguageSupport`` and registers itself via the
``@register`` decorator. The renderers (write_drawio, write_mermaid, write_svg,
write_png) all consume ``FlowGraph``, so new languages only need to produce
compatible graph structures — no renderer changes needed.

Usage::

    from lang_support import get, detect_from_extension

    # Auto-detect language from file extension
    lang_cls = detect_from_extension(Path("source.py"))
    # -> returns py_flowchart.PyFlowchart (stub — raises NotImplementedError)

    # Explicitly request a language
    lang_cls = get("c")
    # -> returns a wrapper around code2flowchart's CTokenizer/CParser

    support = lang_cls()
    tokens = support.tokenize(code)
    functions = support.parse(tokens)
    graph = support.build_graph(functions, detail_level="full")
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_LANGUAGE_REGISTRY: dict[str, type["LanguageSupport"]] = {}


def register(cls: type["LanguageSupport"]) -> type["LanguageSupport"]:
    """Decorator: register a ``LanguageSupport`` subclass for each of its
    ``file_extensions``."""
    for ext in cls.file_extensions:
        _LANGUAGE_REGISTRY[ext] = cls
    _LANGUAGE_REGISTRY[cls.name] = cls
    return cls


def get(lang_name: str) -> type["LanguageSupport"]:
    """Return the ``LanguageSupport`` subclass registered under *lang_name*.

    Raises ``KeyError`` if no implementation is registered.
    """
    if lang_name not in _LANGUAGE_REGISTRY:
        available = sorted(set(_LANGUAGE_REGISTRY.keys()))
        raise KeyError(
            f"no language support registered for {lang_name!r}. "
            f"Available: {available}"
        )
    return _LANGUAGE_REGISTRY[lang_name]


def detect_from_extension(path: str | Path) -> type["LanguageSupport"] | None:
    """Return the registered ``LanguageSupport`` for *path*'s suffix, or None.

    Supports compound extensions like ``.test.cpp`` (resolves to "cpp").
    """
    p = Path(path)
    # Try compound suffixes first, then simple suffix
    suffixes = p.suffixes
    for suffix in reversed(suffixes):
        ext = suffix.lower()
        if ext in _LANGUAGE_REGISTRY:
            return _LANGUAGE_REGISTRY[ext]
    return None


def list_languages() -> list[str]:
    """Return sorted list of registered language names."""
    return sorted(
        {v.name for v in _LANGUAGE_REGISTRY.values()}
    )


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class LanguageSupport(ABC):
    """Interface for adding a new source language to code2flowchart.

    Subclasses must implement ``tokenize``, ``parse``, and ``build_graph``.
    Register via the ``@register`` decorator.
    """

    name: str = ""
    """Short language name, e.g. ``"c"``, ``"python"``, ``"javascript"``."""

    file_extensions: list[str] = []
    """File extensions this language handles, e.g. ``[".c", ".h", ".cpp"]``."""

    display_name: str = ""
    """Human-readable name for messages, e.g. ``"C/C++"``."""

    @abstractmethod
    def tokenize(self, code: str) -> list[Any]:
        """Tokenize source *code* into a list of ``Token``-like objects.

        Each token must have at minimum ``text`` and ``line`` attributes.
        """
        ...

    @abstractmethod
    def parse(self, tokens: list[Any]) -> list[Any]:
        """Parse tokens into a list of ``Function``-like objects.

        Each function must have ``name``, ``header``, ``body`` (list of
        ``Statement``), and ``line`` attributes.
        """
        ...

    @abstractmethod
    def build_graph(
        self,
        functions: list[Any],
        detail_level: str = "full",
    ) -> Any:
        """Build a ``FlowGraph`` from parsed functions.

        Returns a FlowGraph-compatible object with ``nodes``, ``edges``,
        and ``functions`` attributes, ready for rendering.
        """
        ...

    def validate_code(self, code: str) -> list[str]:
        """Optional: return a list of warnings about *code* before conversion.

        Use for language-specific checks (e.g. unsupported syntax, macros that
        hide control flow, templates that need expansion).
        Override in subclasses; default returns an empty list.
        """
        return []
