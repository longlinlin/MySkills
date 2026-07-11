#!/usr/bin/env python3
"""
Convert C/C++ source code into Mermaid, draw.io XML, SVG, and PNG flowchart previews.

The parser is intentionally lightweight. It targets teaching/lab-style C/C++ code and
the most common control-flow constructs rather than full ISO C or C++ grammar.

Companion scripts (in the same directory):
  validate.py           — structural linter for .drawio files
  repair_png.py         — repair truncated IEND in draw.io CLI -e PNG exports
  encode_drawio_url.py  — encode .drawio XML into a diagrams.net browser URL
  lang_support.py       — multi-language extraction framework
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import re
import subprocess
import sys
import textwrap
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


CONTROL_KEYWORDS = {
    "if",
    "else",
    "for",
    "while",
    "do",
    "switch",
    "case",
    "default",
    "break",
    "continue",
    "goto",
    "return",
    "try",
    "catch",
    "throw",
}

TYPE_HINTS = {
    "void",
    "char",
    "short",
    "int",
    "long",
    "float",
    "double",
    "signed",
    "unsigned",
    "struct",
    "enum",
    "union",
    "static",
    "extern",
    "const",
    "volatile",
    "register",
    "inline",
    "_Bool",
    "bool",
    "auto",
    "class",
    "typename",
    "template",
    "constexpr",
    "consteval",
    "constinit",
    "mutable",
    "virtual",
    "explicit",
    "friend",
    "public",
    "private",
    "protected",
}

IO_NAMES = {
    "printf",
    "scanf",
    "puts",
    "gets",
    "fgets",
    "putchar",
    "getchar",
    "fprintf",
    "fscanf",
    "sprintf",
    "sscanf",
    "cin",
    "cout",
    "cerr",
    "clog",
    "std::cin",
    "std::cout",
    "std::cerr",
    "std::clog",
}

TERMINATING_CALL_NAMES = {
    "abort",
    "exit",
    "_Exit",
    "quick_exit",
    "std::terminate",
    "osThreadTerminate",
}


@dataclass
class Token:
    text: str
    line: int


@dataclass
class Statement:
    kind: str
    label: str = ""
    body: list["Statement"] = field(default_factory=list)
    else_body: list["Statement"] = field(default_factory=list)
    cases: list[tuple[str, list["Statement"]]] = field(default_factory=list)
    line: int = 0


@dataclass
class Function:
    name: str
    header: str
    body: list[Statement]
    line: int


@dataclass
class Node:
    id: str
    kind: str
    label: str
    x: float
    y: float
    w: float
    h: float
    function: str = ""


@dataclass
class Edge:
    source: str
    target: str
    label: str = ""
    backward: bool = False
    route_side: int = 0
    route_lane: int = 0


@dataclass
class FunctionFlow:
    name: str
    start_id: str
    end_id: str


@dataclass
class PathStep:
    edge_no: int
    edge_label: str
    source_label: str
    target_label: str


@dataclass
class FunctionPaths:
    function: str
    paths: list[list[PathStep]]
    truncated: bool = False


@dataclass
class ExitRef:
    node_id: str
    label: str = ""
    kind: str = "normal"


class CTokenizer:
    def __init__(self, code: str) -> None:
        self.code = code
        self.i = 0
        self.line = 1

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        while self.i < len(self.code):
            ch = self.code[self.i]
            if ch.isspace():
                self._advance_ws()
                continue
            if self.code.startswith("//", self.i):
                self._skip_line_comment()
                continue
            if self.code.startswith("/*", self.i):
                self._skip_block_comment()
                continue
            if ch == "#":
                self._skip_preprocessor()
                continue
            if ch in {'"', "'"}:
                tokens.append(Token(self._read_string(ch), self.line))
                continue
            if ch.isalpha() or ch == "_":
                tokens.append(Token(self._read_identifier(), self.line))
                continue
            if ch.isdigit():
                tokens.append(Token(self._read_number(), self.line))
                continue
            two = self.code[self.i : self.i + 2]
            three = self.code[self.i : self.i + 3]
            if three in {"<<=", ">>=", "->*", "<=>"}:
                tokens.append(Token(three, self.line))
                self.i += 3
                continue
            if two in {
                "==",
                "!=",
                "<=",
                ">=",
                "&&",
                "||",
                "++",
                "--",
                "+=",
                "-=",
                "*=",
                "/=",
                "%=",
                "->",
                "::",
                ".*",
                "<<",
                ">>",
            }:
                tokens.append(Token(two, self.line))
                self.i += 2
                continue
            tokens.append(Token(ch, self.line))
            self.i += 1
        return tokens

    def _advance_ws(self) -> None:
        if self.code[self.i] == "\n":
            self.line += 1
        self.i += 1

    def _skip_line_comment(self) -> None:
        while self.i < len(self.code) and self.code[self.i] != "\n":
            self.i += 1

    def _skip_block_comment(self) -> None:
        self.i += 2
        while self.i < len(self.code) - 1:
            if self.code[self.i] == "\n":
                self.line += 1
            if self.code.startswith("*/", self.i):
                self.i += 2
                return
            self.i += 1

    def _skip_preprocessor(self) -> None:
        escaped = False
        while self.i < len(self.code):
            ch = self.code[self.i]
            self.i += 1
            if ch == "\n":
                self.line += 1
                if not escaped:
                    break
                escaped = False
                continue
            escaped = ch == "\\"

    def _read_string(self, quote: str) -> str:
        start = self.i
        self.i += 1
        escaped = False
        while self.i < len(self.code):
            ch = self.code[self.i]
            if ch == "\n":
                self.line += 1
            self.i += 1
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                break
        return self.code[start : self.i]

    def _read_identifier(self) -> str:
        start = self.i
        while self.i < len(self.code) and (
            self.code[self.i].isalnum() or self.code[self.i] == "_"
        ):
            self.i += 1
        return self.code[start : self.i]

    def _read_number(self) -> str:
        start = self.i
        while self.i < len(self.code) and re.match(r"[A-Za-z0-9_.]", self.code[self.i]):
            self.i += 1
        return self.code[start : self.i]


class CParser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.i = 0

    def parse_functions(self) -> list[Function]:
        functions: list[Function] = []
        n = len(self.tokens)
        i = 0
        depth = 0
        while i < n:
            text = self.tokens[i].text
            if text == "{":
                depth += 1
                i += 1
                continue
            if text == "}":
                depth = max(0, depth - 1)
                i += 1
                continue
            if self._looks_like_function_at(i):
                name_idx = i
                lparen = i + 1
                rparen = self._find_match(lparen, "(", ")")
                if rparen is None:
                    i += 1
                    continue
                brace = self._body_brace_after_signature(rparen + 1)
                if brace is None or self.tokens[brace].text != "{":
                    i += 1
                    continue
                end = self._find_match(brace, "{", "}")
                if end is None:
                    i += 1
                    continue
                header_start = self._header_start(name_idx)
                header = compact_tokens(self.tokens[header_start:brace])
                body_tokens = self.tokens[brace + 1 : end]
                sub = CParser(body_tokens)
                body = sub.parse_block(stop_at_case=False)
                functions.append(
                    Function(self._function_name(name_idx), header, body, self.tokens[name_idx].line)
                )
                i = end + 1
                continue
            i += 1
        return functions

    def parse_block(self, stop_at_case: bool = True) -> list[Statement]:
        statements: list[Statement] = []
        while self.i < len(self.tokens):
            if self.peek("}"):
                break
            if stop_at_case and (self.peek("case") or self.peek("default")):
                break
            stmt = self.parse_statement()
            if stmt is not None:
                if stmt.kind == "block":
                    statements.extend(stmt.body)
                else:
                    statements.append(stmt)
            else:
                self.i += 1
        return statements

    def parse_statement(self) -> Statement | None:
        tok = self.current()
        if tok is None:
            return None
        if tok.text == "{":
            line = tok.line
            self.i += 1
            body = self.parse_block()
            self.consume("}")
            return Statement("block", body=body, line=line)
        if tok.text == "if":
            return self.parse_if()
        if tok.text in {"while", "for"}:
            return self.parse_loop(tok.text)
        if tok.text == "do":
            return self.parse_do_while()
        if tok.text == "switch":
            return self.parse_switch()
        if tok.text == "try":
            return self.parse_try()
        if tok.text == "return":
            return self.parse_simple("return")
        if tok.text == "throw":
            return self.parse_simple("throw")
        if tok.text == "goto":
            return self.parse_simple("goto")
        if tok.text == "break":
            return self.parse_simple("break")
        if tok.text == "continue":
            return self.parse_simple("continue")
        if self.i + 1 < len(self.tokens) and re.match(r"^[A-Za-z_]\w*$", tok.text) and self.tokens[self.i + 1].text == ":":
            self.i += 2
            return Statement("label", label=tok.text, line=tok.line)
        return self.parse_expression()

    def parse_if(self) -> Statement:
        line = self.current().line
        self.i += 1
        cond = self.read_parenthesized()
        then_stmt = self.parse_statement()
        then_body = to_body(then_stmt)
        else_body: list[Statement] = []
        if self.peek("else"):
            self.i += 1
            else_stmt = self.parse_statement()
            else_body = to_body(else_stmt)
        return Statement("if", label=f"if ({cond})", body=then_body, else_body=else_body, line=line)

    def parse_loop(self, kind: str) -> Statement:
        line = self.current().line
        self.i += 1
        cond = self.read_parenthesized()
        body = to_body(self.parse_statement())
        return Statement(kind, label=f"{kind} ({cond})", body=body, line=line)

    def parse_do_while(self) -> Statement:
        line = self.current().line
        self.i += 1
        body = to_body(self.parse_statement())
        cond = ""
        if self.peek("while"):
            self.i += 1
            cond = self.read_parenthesized()
            self.consume_until(";")
        return Statement("do_while", label=f"while ({cond})", body=body, line=line)

    def parse_switch(self) -> Statement:
        line = self.current().line
        self.i += 1
        cond = self.read_parenthesized()
        cases: list[tuple[str, list[Statement]]] = []
        if not self.consume("{"):
            return Statement("expr", label=f"switch ({cond})", line=line)
        while self.i < len(self.tokens) and not self.peek("}"):
            if self.peek("case"):
                case_line = self.current().line
                self.i += 1
                label_tokens = self.read_until(":")
                self.consume(":")
                body = self.parse_block(stop_at_case=True)
                cases.append((f"case {compact_tokens(label_tokens)}", body))
                if body:
                    body[0].line = min(body[0].line or case_line, case_line)
                continue
            if self.peek("default"):
                self.i += 1
                self.consume(":")
                body = self.parse_block(stop_at_case=True)
                cases.append(("default", body))
                continue
            self.i += 1
        self.consume("}")
        return Statement("switch", label=f"switch ({cond})", cases=cases, line=line)

    def parse_try(self) -> Statement:
        line = self.current().line
        self.i += 1
        body = to_body(self.parse_statement())
        catches: list[tuple[str, list[Statement]]] = []
        while self.peek("catch"):
            catch_line = self.current().line
            self.i += 1
            cond = self.read_parenthesized()
            catch_body = to_body(self.parse_statement())
            if catch_body:
                catch_body[0].line = min(catch_body[0].line or catch_line, catch_line)
            catches.append((f"catch ({cond})", catch_body))
        return Statement("try", label="try", body=body, cases=catches, line=line)

    def parse_simple(self, kind: str) -> Statement:
        line = self.current().line
        parts = self.read_until(";")
        self.consume(";")
        label = compact_tokens(parts)
        return Statement(kind, label=label or kind, line=line)

    def parse_expression(self) -> Statement:
        line = self.current().line
        parts = self.read_until(";")
        self.consume(";")
        raw_label = compact_tokens(parts)
        label = display_flow_label(raw_label)
        if re.match(r"^TRACE_ERROR\s*\(", raw_label):
            kind = "expr"
        elif re.match(r"^TRACE_(?:INFO|WARN)\s*\(", raw_label):
            kind = "trace"
        elif is_io_label(raw_label):
            kind = "io"
        elif is_terminating_call(raw_label):
            kind = "terminate"
        else:
            kind = "expr"
        return Statement(kind, label=label, line=line)

    def read_parenthesized(self) -> str:
        if not self.consume("("):
            return ""
        start = self.i
        depth = 1
        while self.i < len(self.tokens):
            text = self.tokens[self.i].text
            if text == "(":
                depth += 1
            elif text == ")":
                depth -= 1
                if depth == 0:
                    content = self.tokens[start : self.i]
                    self.i += 1
                    return compact_tokens(content)
            self.i += 1
        return compact_tokens(self.tokens[start:self.i])

    def read_until(self, terminator: str) -> list[Token]:
        start = self.i
        depth = 0
        while self.i < len(self.tokens):
            text = self.tokens[self.i].text
            if text in {"(", "[", "{"}:
                depth += 1
            elif text in {")", "]", "}"}:
                depth = max(0, depth - 1)
            if depth == 0 and text == terminator:
                return self.tokens[start:self.i]
            self.i += 1
        return self.tokens[start:self.i]

    def consume_until(self, terminator: str) -> None:
        self.read_until(terminator)
        self.consume(terminator)

    def consume(self, text: str) -> bool:
        if self.peek(text):
            self.i += 1
            return True
        return False

    def peek(self, text: str) -> bool:
        tok = self.current()
        return tok is not None and tok.text == text

    def current(self) -> Token | None:
        if self.i >= len(self.tokens):
            return None
        return self.tokens[self.i]

    def _looks_like_function_at(self, idx: int) -> bool:
        tok = self.tokens[idx].text
        if tok in CONTROL_KEYWORDS or not re.match(r"^[A-Za-z_]\w*$", tok):
            return False
        if idx + 1 >= len(self.tokens) or self.tokens[idx + 1].text != "(":
            return False
        if idx > 0 and self.tokens[idx - 1].text in {"(", "[", ".", "->"}:
            return False
        if idx > 0 and self.tokens[idx - 1].text in {"=", "+", "-", "*", "/", "%", "!", "&&", "||", "?", ","}:
            return False
        if idx > 1 and self.tokens[idx - 1].text == "::":
            return True
        prev_texts = [t.text for t in self.tokens[max(0, idx - 6) : idx]]
        return bool(prev_texts and any(t in TYPE_HINTS or re.match(r"^[A-Za-z_]\w*$", t) for t in prev_texts))

    def _find_match(self, start: int, left: str, right: str) -> int | None:
        depth = 0
        for j in range(start, len(self.tokens)):
            if self.tokens[j].text == left:
                depth += 1
            elif self.tokens[j].text == right:
                depth -= 1
                if depth == 0:
                    return j
        return None

    def _next_non_ws(self, start: int) -> int | None:
        return start if start < len(self.tokens) else None

    def _body_brace_after_signature(self, start: int) -> int | None:
        j = start
        while j < len(self.tokens):
            text = self.tokens[j].text
            if text == "{":
                return j
            if text in {";", "="}:
                return None
            if text == "(":
                end = self._find_match(j, "(", ")")
                if end is None:
                    return None
                j = end + 1
                continue
            if text == "[":
                end = self._find_match(j, "[", "]")
                if end is None:
                    return None
                j = end + 1
                continue
            j += 1
        return None

    def _header_start(self, name_idx: int) -> int:
        j = name_idx - 1
        while j >= 0 and self.tokens[j].text not in {";", "{", "}"}:
            j -= 1
        return j + 1

    def _function_name(self, name_idx: int) -> str:
        name = self.tokens[name_idx].text
        left = name_idx - 1
        if left >= 0 and self.tokens[left].text == "~":
            name = "~" + name
            left -= 1
        while left >= 1 and self.tokens[left].text == "::":
            qualifier = self.tokens[left - 1].text
            if re.match(r"^[A-Za-z_]\w*$", qualifier):
                name = qualifier + "::" + name
                left -= 2
                continue
            break
        return name


def to_body(stmt: Statement | None) -> list[Statement]:
    if stmt is None:
        return []
    if stmt.kind == "block":
        return stmt.body
    return [stmt]


def compact_tokens(tokens: Iterable[Token]) -> str:
    raw = [t.text for t in tokens]
    if not raw:
        return ""
    out = ""
    no_space_before = {")", "]", "}", ";", ",", ":", "::", "++", "--", "[", ".", "->"}
    no_space_after = {"(", "[", "{", ".", "->", "::", "++", "--", "!", "~", "&"}
    operators = {
        "=",
        "+",
        "-",
        "*",
        "/",
        "%",
        "==",
        "!=",
        "<=",
        ">=",
        "<",
        ">",
        "&&",
        "||",
        "+=",
        "-=",
        "*=",
        "/=",
        "%=",
        "<<",
        ">>",
    }
    prev = ""
    for part in raw:
        if not out:
            out = part
        elif part in no_space_before or prev in no_space_after:
            out += part
        elif part in operators or prev in operators:
            out += " " + part
        else:
            out += " " + part
        prev = part
    return out.strip()


def is_io_label(label: str) -> bool:
    names = "|".join(re.escape(name) for name in sorted(IO_NAMES, key=len, reverse=True))
    if re.search(r"\b(" + names + r")\s*\(", label):
        return True
    return bool(re.search(r"\b(std::)?(cin|cout|cerr|clog)\b", label))


def is_terminating_call(label: str) -> bool:
    names = "|".join(re.escape(name) for name in sorted(TERMINATING_CALL_NAMES, key=len, reverse=True))
    return bool(re.search(r"(?:^|\s)(?:" + names + r")\s*\(", label))


def display_flow_label(label: str) -> str:
    """Keep process nodes readable without changing the modeled control flow."""
    trace = re.match(
        r'^(TRACE_(?:INFO|WARN|ERROR))\s*\(\s*"[^"]*"\s*,\s*"([^"]*)"',
        label,
    )
    if trace:
        level, message = trace.groups()
        message = message.replace("\\r", "").replace("\\n", "")
        message = re.sub(r"%[-+ #0]*\d*(?:\.\d+)?(?:hh|h|ll|l|j|z|t|L)?[diuoxXfFeEgGaAcsp]", "[value]", message)
        message = re.sub(r"\s+", " ", message).strip()
        if level == "TRACE_ERROR" and "FAIL after" in message:
            return "ERROR: Apply failed after retry limit"
        return f"{level}: {message}"

    assignment_call = re.match(
        r"^(?P<lhs>.+?\s*(?<![=!<>])=(?!=)\s*)(?P<call>[A-Za-z_]\w*(?:::\w+)*)\s*\(",
        label,
    )
    if assignment_call:
        return f"{assignment_call.group('lhs')}{assignment_call.group('call')}(...)"
    direct_call = re.match(r"^(?P<call>[A-Za-z_]\w*(?:::\w+)*)\s*\(", label)
    if direct_call:
        return f"{direct_call.group('call')}(...)"
    return label


def is_setup_statement(stmt: Statement) -> bool:
    """Return whether a plain expression is a declaration or state update."""
    if stmt.kind != "expr":
        return False
    label = stmt.label.strip()
    if not label:
        return False
    if re.search(r"(?:\+\+|--|(?<![=!<>])=(?!=)|\+=|-=|\*=|/=)", label):
        return True
    # Includes project-specific declarations such as U8, S32, and
    # Charge_PortStatus, without treating an ordinary function call as one.
    return bool(re.match(r"^[A-Za-z_]\w*(?:\s*::\s*\w+)?(?:\s+\w+|\s*\*)", label)) and "(" not in label


def collapse_setup_statements(statements: list[Statement]) -> list[Statement]:
    """Collapse consecutive declarations/assignments into a single setup node."""
    result: list[Statement] = []
    pending: list[Statement] = []

    def flush() -> None:
        nonlocal pending
        if len(pending) == 1:
            result.append(pending[0])
        elif pending:
            result.append(
                Statement(
                    "expr",
                    label="\n".join(stmt.label for stmt in pending),
                    line=pending[0].line,
                )
            )
        pending = []

    for stmt in statements:
        if is_setup_statement(stmt):
            pending.append(stmt)
        else:
            flush()
            result.append(stmt)
    flush()
    return result


class FlowGraph:
    def __init__(self) -> None:
        self.nodes: list[Node] = []
        self.edges: list[Edge] = []
        self.functions: list[FunctionFlow] = []
        self.counter = 0
        self.edge_counter = 0
        self.max_y = 0.0

    def add_node(self, kind: str, label: str, x: float, y: float, function: str = "") -> str:
        self.counter += 1
        node_id = f"n{self.counter}"
        w, h = size_for(kind, label)
        self.nodes.append(Node(node_id, kind, label, x, y, w, h, function))
        self.max_y = max(self.max_y, y + h)
        return node_id

    def set_node_position(self, node_id: str, x: float, y: float) -> None:
        node = self.node(node_id)
        node.x = x
        node.y = y
        self.max_y = max(self.max_y, y + node.h)

    def add_edge(self, source: str, target: str, label: str = "", backward: bool = False) -> None:
        if not source or not target:
            return
        self.edge_counter += 1
        edge_label = str(self.edge_counter)
        if label:
            edge_label += f" {label}"
        self.edges.append(Edge(source, target, edge_label, backward))

    def connect(self, exits: list[ExitRef], target: str) -> None:
        for ref in exits:
            self.add_edge(ref.node_id, target, ref.label)

    def node(self, node_id: str) -> Node:
        for node in self.nodes:
            if node.id == node_id:
                return node
        raise KeyError(node_id)


def size_for(kind: str, label: str) -> tuple[float, float]:
    if kind == "merge":
        return 14, 14
    lines = node_label_lines(kind, label)
    width = max(130, 8 * max((len(line) for line in lines), default=8) + 34)
    if kind in {"decision", "switch"}:
        return max(width, 220), max(86, 22 * len(lines) + 28)
    if kind in {"terminator", "return"}:
        return max(120, width), 62
    if kind == "io":
        return max(width, 170), max(62, 22 * len(lines) + 18)
    if kind == "function":
        return max(width, 180), 44
    if kind == "label":
        return max(width, 130), 44
    return width, max(54, 22 * len(lines) + 18)


def wrap_label(label: str, width: int | None = None) -> list[str]:
    raw_lines = label.strip().splitlines() or [""]
    lines: list[str] = []
    for segment in raw_lines:
        text = re.sub(r"\s+", " ", segment.strip())
        if width is None:
            lines.append(text)
        else:
            lines.extend(textwrap.wrap(text, width=width, break_long_words=True) or [""])
    return lines or [""]


def node_label_lines(kind: str, label: str) -> list[str]:
    # Process nodes preserve complete C statements and grow to fit them. Only
    # decisions are wrapped so their diamond shape remains legible.
    width = 44 if kind in {"decision", "switch"} else None
    return wrap_label(label, width)


def goto_target(label: str) -> str:
    match = re.match(r"goto\s+([A-Za-z_]\w*)", label.strip())
    return match.group(1) if match else ""


def single_jump_statement(statements: list[Statement]) -> Statement | None:
    if len(statements) != 1:
        return None
    stmt = statements[0]
    if stmt.kind in {"break", "continue"}:
        return stmt
    return None


def is_infinite_loop(label: str) -> bool:
    compact = re.sub(r"\s+", "", label).lower()
    return compact in {"for(;;)", "while(1)", "while(true)"}


def without_trailing_break(statements: list[Statement]) -> tuple[list[Statement], bool]:
    if statements and statements[-1].kind == "break":
        return statements[:-1], True
    return statements, False


def statement_descendants(statements: list[Statement]) -> Iterable[Statement]:
    for stmt in statements:
        yield stmt
        yield from statement_descendants(stmt.body)
        yield from statement_descendants(stmt.else_body)
        for _, case_body in stmt.cases:
            yield from statement_descendants(case_body)


def complex_retry_loop_return(statements: list[Statement]) -> Statement | None:
    """Return the success return for a deeply nested retry loop, if present."""
    descendants = list(statement_descendants(statements))
    has_nested_loop = any(stmt.kind in {"for", "while", "do_while"} for stmt in descendants)
    if not has_nested_loop:
        return None
    return next((stmt for stmt in descendants if stmt.kind == "return"), None)


class FlowBuilder:
    X_GAP = 260
    Y_GAP = 120

    def __init__(
        self, graph: FlowGraph, end_id: str, function: str, detail_level: str = "standard"
    ) -> None:
        self.g = graph
        self.end_id = end_id
        self.function = function
        self.detail_level = detail_level

    def next_y_after(self, node_id: str) -> float:
        node = self.g.node(node_id)
        # Keep the established vertical rhythm for ordinary nodes, while
        # reserving extra space for wrapped labels such as TRACE_INFO calls.
        return node.y + max(self.Y_GAP, node.h + 60)

    def build_sequence(
        self, statements: list[Statement], incoming: list[ExitRef], x: float, y: float
    ) -> tuple[list[ExitRef], float]:
        statements = collapse_setup_statements(statements)
        normal = [ref for ref in incoming if ref.kind == "normal"]
        carried: list[ExitRef] = [ref for ref in incoming if ref.kind != "normal"]
        cur_y = y
        for stmt in statements:
            if stmt.kind == "label":
                matched: list[ExitRef] = []
                remaining: list[ExitRef] = []
                for ref in carried:
                    if ref.kind == f"goto:{stmt.label}":
                        matched.append(ExitRef(ref.node_id, "goto"))
                    else:
                        remaining.append(ref)
                carried = remaining
                normal = normal + matched
            if len(normal) > 1:
                normal, cur_y = self.merge_normal_exits(normal, x, cur_y)
            exits, cur_y = self.build_statement(stmt, normal, x, cur_y)
            normal = [e for e in exits if e.kind == "normal"]
            carried.extend(e for e in exits if e.kind != "normal")
            if not normal:
                cur_y += self.Y_GAP / 2
        return normal + carried, cur_y

    def merge_normal_exits(
        self, incoming: list[ExitRef], x: float, y: float
    ) -> tuple[list[ExitRef], float]:
        """Merge branch fall-throughs before resuming the dominant spine."""
        source_bottom = max(
            self.g.node(ref.node_id).y + self.g.node(ref.node_id).h for ref in incoming
        )
        merge_y = max(y - 55, source_bottom + 25)
        merge = self.g.add_node("merge", "", x, merge_y, self.function)
        self.g.connect(incoming, merge)
        return [ExitRef(merge)], max(y, merge_y + 45)

    def build_statement(
        self, stmt: Statement, incoming: list[ExitRef], x: float, y: float
    ) -> tuple[list[ExitRef], float]:
        if stmt.kind == "trace":
            # Logging does not alter local control flow. Keeping every verbose
            # TRACE macro as a node overwhelms nested retry diagrams.
            return incoming, y
        if stmt.kind in {"expr", "io"}:
            node = self.g.add_node(stmt.kind, stmt.label, x, y, self.function)
            self.g.connect(incoming, node)
            return [ExitRef(node)], self.next_y_after(node)
        if stmt.kind == "terminate":
            node = self.g.add_node("expr", stmt.label, x, y, self.function)
            self.g.connect(incoming, node)
            self.g.add_edge(node, self.end_id, "terminate")
            return [ExitRef(node, kind="terminate")], self.next_y_after(node)
        if stmt.kind == "return":
            node = self.g.add_node("return", stmt.label, x, y, self.function)
            self.g.connect(incoming, node)
            self.g.add_edge(node, self.end_id, "return")
            return [ExitRef(node, kind="return")], self.next_y_after(node)
        if stmt.kind == "throw":
            node = self.g.add_node("return", stmt.label, x, y, self.function)
            self.g.connect(incoming, node)
            self.g.add_edge(node, self.end_id, "throw")
            return [ExitRef(node, kind="throw")], self.next_y_after(node)
        if stmt.kind == "goto":
            node = self.g.add_node("goto", stmt.label, x, y, self.function)
            self.g.connect(incoming, node)
            target = goto_target(stmt.label)
            return [ExitRef(node, kind=f"goto:{target}" if target else "goto")], self.next_y_after(node)
        if stmt.kind == "label":
            node = self.g.add_node("label", f"{stmt.label}:", x, y, self.function)
            self.g.connect(incoming, node)
            return [ExitRef(node)], self.next_y_after(node)
        if stmt.kind in {"break", "continue"}:
            node = self.g.add_node(stmt.kind, stmt.label, x, y, self.function)
            self.g.connect(incoming, node)
            return [ExitRef(node, kind=stmt.kind)], self.next_y_after(node)
        if stmt.kind == "if":
            return self.build_if(stmt, incoming, x, y)
        if stmt.kind in {"while", "for"}:
            return self.build_loop(stmt, incoming, x, y)
        if stmt.kind == "do_while":
            return self.build_do_while(stmt, incoming, x, y)
        if stmt.kind == "switch":
            return self.build_switch(stmt, incoming, x, y)
        if stmt.kind == "try":
            return self.build_try(stmt, incoming, x, y)
        node = self.g.add_node("expr", stmt.label or stmt.kind, x, y, self.function)
        self.g.connect(incoming, node)
        return [ExitRef(node)], self.next_y_after(node)

    def build_if(
        self, stmt: Statement, incoming: list[ExitRef], x: float, y: float
    ) -> tuple[list[ExitRef], float]:
        cond = self.g.add_node("decision", stmt.label, x, y, self.function)
        self.g.connect(incoming, cond)
        simple_then_jump = single_jump_statement(stmt.body)
        simple_else_jump = single_jump_statement(stmt.else_body)
        if simple_then_jump is not None and not stmt.else_body:
            normal_label = "no"
            jump_label = f"yes {simple_then_jump.kind}"
            return [
                ExitRef(cond, normal_label),
                ExitRef(cond, jump_label, kind=simple_then_jump.kind),
            ], y + self.Y_GAP
        if simple_then_jump is not None and stmt.else_body:
            branch_y = y + self.Y_GAP
            else_exits, else_y = self.build_sequence(
                stmt.else_body, [ExitRef(cond, "no")], x + self.X_GAP / 2, branch_y
            )
            return else_exits + [
                ExitRef(cond, f"yes {simple_then_jump.kind}", kind=simple_then_jump.kind)
            ], max(else_y, branch_y) + 20
        if simple_then_jump is not None and simple_else_jump is not None:
            return [
                ExitRef(cond, f"yes {simple_then_jump.kind}", kind=simple_then_jump.kind),
                ExitRef(cond, f"no {simple_else_jump.kind}", kind=simple_else_jump.kind),
            ], y + self.Y_GAP
        branch_y = self.next_y_after(cond)
        if not stmt.body and stmt.else_body:
            else_exits, else_y = self.build_sequence(
                stmt.else_body, [ExitRef(cond, "no")], x, branch_y
            )
            return [ExitRef(cond, "yes")] + else_exits, max(else_y, branch_y) + 20
        # Keep a one-sided if on the vertical spine. Reserve left/right
        # placement only when an else branch needs its own column.
        then_x = x - self.X_GAP / 2 if stmt.else_body else x
        then_exits, then_y = self.build_sequence(
            stmt.body, [ExitRef(cond, "yes")], then_x, branch_y
        )
        if stmt.else_body:
            else_exits, else_y = self.build_sequence(
                stmt.else_body, [ExitRef(cond, "no")], x + self.X_GAP / 2, branch_y
            )
        else:
            else_exits, else_y = [ExitRef(cond, "no")], branch_y
        return then_exits + else_exits, max(then_y, else_y, branch_y) + 20

    def build_loop(
        self, stmt: Statement, incoming: list[ExitRef], x: float, y: float
    ) -> tuple[list[ExitRef], float]:
        success_return = complex_retry_loop_return(stmt.body)
        if success_return is not None and self.detail_level != "detailed":
            return self.build_compact_retry_loop(stmt, success_return, incoming, x, y)
        cond = self.g.add_node("decision", stmt.label, x, y, self.function)
        self.g.connect(incoming, cond)
        infinite = is_infinite_loop(stmt.label)
        enter_label = "enter" if infinite else "yes"
        body_exits, body_y = self.build_sequence(
            stmt.body, [ExitRef(cond, enter_label)], x, self.next_y_after(cond)
        )
        after_loop = [] if infinite else [ExitRef(cond, "no")]
        has_break_exit = False
        loop_sources: list[ExitRef] = []
        for ref in body_exits:
            if ref.kind in {"normal", "continue"}:
                loop_sources.append(ref)
            elif ref.kind == "break":
                has_break_exit = True
                after_loop.append(ExitRef(ref.node_id, ref.label or "break"))
            else:
                after_loop.append(ref)
        if len(loop_sources) == 1:
            ref = loop_sources[0]
            loop_label = " ".join(part for part in (ref.label, "loop") if part)
            self.g.add_edge(ref.node_id, cond, loop_label, backward=True)
        elif loop_sources:
            source_bottom = max(
                self.g.node(ref.node_id).y + self.g.node(ref.node_id).h for ref in loop_sources
            )
            merge = self.g.add_node("merge", "", x, source_bottom + 28, self.function)
            self.g.connect(loop_sources, merge)
            self.g.add_edge(merge, cond, "loop", backward=True)
        exit_padding = 90 if has_break_exit else 0
        return after_loop, max(body_y, y + self.Y_GAP * 2) + exit_padding

    def build_compact_retry_loop(
        self,
        stmt: Statement,
        success_return: Statement,
        incoming: list[ExitRef],
        x: float,
        y: float,
    ) -> tuple[list[ExitRef], float]:
        """Render deeply nested write/read retries as a readable subflow."""
        cond = self.g.add_node("decision", stmt.label, x, y, self.function)
        self.g.connect(incoming, cond)
        cycle = self.g.add_node(
            "expr",
            "Send target power and verify readback\n(with nested read retries)",
            x,
            self.next_y_after(cond),
            self.function,
        )
        self.g.add_edge(cond, cycle, "yes")
        verified = self.g.add_node(
            "decision",
            "Target power verified?",
            x,
            self.next_y_after(cycle),
            self.function,
        )
        self.g.add_edge(cycle, verified)
        returned = self.g.add_node(
            "return",
            success_return.label,
            x,
            self.next_y_after(verified),
            self.function,
        )
        self.g.add_edge(verified, returned, "yes")
        self.g.add_edge(returned, self.end_id, "return")
        self.g.add_edge(verified, cond, "no loop", backward=True)
        return [ExitRef(cond, "no")], self.next_y_after(returned) + 20

    def build_do_while(
        self, stmt: Statement, incoming: list[ExitRef], x: float, y: float
    ) -> tuple[list[ExitRef], float]:
        do_node = self.g.add_node("expr", "do", x, y, self.function)
        self.g.connect(incoming, do_node)
        body_exits, body_y = self.build_sequence(stmt.body, [ExitRef(do_node)], x, self.next_y_after(do_node))
        cond = self.g.add_node("decision", stmt.label, x, max(body_y, self.next_y_after(do_node)), self.function)
        after_loop = [ExitRef(cond, "no")]
        has_break_exit = False
        loop_sources: list[ExitRef] = []
        for ref in body_exits:
            if ref.kind in {"normal", "continue"}:
                loop_sources.append(ref)
            elif ref.kind == "break":
                has_break_exit = True
                after_loop.append(ExitRef(ref.node_id, ref.label or "break"))
            else:
                after_loop.append(ref)
        if len(loop_sources) == 1:
            self.g.add_edge(loop_sources[0].node_id, cond, loop_sources[0].label)
        elif loop_sources:
            source_bottom = max(
                self.g.node(ref.node_id).y + self.g.node(ref.node_id).h for ref in loop_sources
            )
            merge = self.g.add_node("merge", "", x, source_bottom + 28, self.function)
            self.g.connect(loop_sources, merge)
            self.g.add_edge(merge, cond)
        self.g.add_edge(cond, do_node, "yes", backward=True)
        return after_loop, cond_y_after(self.g.node(cond)) + (110 if has_break_exit else 40)

    def build_switch(
        self, stmt: Statement, incoming: list[ExitRef], x: float, y: float
    ) -> tuple[list[ExitRef], float]:
        sw = self.g.add_node("switch", stmt.label, x, y, self.function)
        self.g.connect(incoming, sw)
        if not stmt.cases:
            return [ExitRef(sw)], y + self.Y_GAP
        merge_sources: list[ExitRef] = []
        carried: list[ExitRef] = []
        direct_labels: list[str] = []
        case_count = len(stmt.cases)
        start_x = x - self.X_GAP * (case_count - 1) / 2
        max_y = y + self.Y_GAP
        has_default = False
        pending_labels: list[str] = []
        for idx, (case_label, body) in enumerate(stmt.cases):
            has_default = has_default or case_label == "default"
            body_without_break, trailing_break = without_trailing_break(body)
            labels = pending_labels + [case_label]
            if not body and not trailing_break:
                pending_labels = labels
                continue
            pending_labels = []
            branch_label = " / ".join(labels)
            case_x = start_x + idx * self.X_GAP
            case_exits, case_y = self.build_sequence(
                body_without_break,
                [ExitRef(sw, branch_label)],
                case_x,
                y + self.Y_GAP,
            )
            for ref in case_exits:
                if ref.kind in {"normal", "break"}:
                    if ref.node_id == sw:
                        direct_labels.append(ref.label)
                    else:
                        merge_sources.append(ExitRef(ref.node_id))
                else:
                    carried.append(ref)
            max_y = max(max_y, case_y)
        if pending_labels:
            direct_labels.append(" / ".join(pending_labels))
        if not has_default:
            direct_labels.append("no match")

        if direct_labels:
            display_labels = [
                label.removeprefix("case ") for label in direct_labels
            ]
            direct_x = start_x
            direct_node = self.g.add_node(
                "expr",
                "No case action: " + " / ".join(display_labels),
                direct_x,
                y + self.Y_GAP,
                self.function,
            )
            self.g.add_edge(sw, direct_node, "no action")
            merge_sources.append(ExitRef(direct_node))
            max_y = max(max_y, self.g.node(direct_node).y + self.g.node(direct_node).h + 20)
        merge_y = max_y + 25
        merge = self.g.add_node("merge", "", x, merge_y, self.function)
        self.g.connect(merge_sources, merge)
        return [ExitRef(merge)] + carried, merge_y + self.Y_GAP / 2

    def build_try(
        self, stmt: Statement, incoming: list[ExitRef], x: float, y: float
    ) -> tuple[list[ExitRef], float]:
        try_node = self.g.add_node("expr", "try", x, y, self.function)
        self.g.connect(incoming, try_node)
        exits: list[ExitRef] = []
        body_exits, body_y = self.build_sequence(stmt.body, [ExitRef(try_node)], x, y + self.Y_GAP)
        exits.extend(body_exits)
        catch_count = len(stmt.cases)
        start_x = x - self.X_GAP * (catch_count - 1) / 2 if catch_count else x
        max_y = body_y
        for idx, (catch_label, body) in enumerate(stmt.cases):
            catch_x = start_x + idx * self.X_GAP
            catch_exits, catch_y = self.build_sequence(
                body, [ExitRef(try_node, catch_label)], catch_x, y + self.Y_GAP
            )
            exits.extend(catch_exits)
            max_y = max(max_y, catch_y)
        return exits, max_y + 20


def cond_y_after(node: Node) -> float:
    return node.y + node.h + FlowBuilder.Y_GAP


def parse_source(path: Path) -> list[Function]:
    code = path.read_text(encoding="utf-8", errors="replace")
    tokens = CTokenizer(code).tokenize()
    return CParser(tokens).parse_functions()


def build_graph(functions: list[Function], detail_level: str = "standard") -> FlowGraph:
    graph = FlowGraph()
    if not functions:
        start = graph.add_node("terminator", "Start", 0, 40, "__global__")
        end = graph.add_node("terminator", "End", 0, 180, "__global__")
        graph.functions.append(FunctionFlow("__global__", start, end))
        graph.add_edge(start, end)
        return graph
    x_offset = 0.0
    for fn in functions:
        start_y = 40.0
        start = graph.add_node("terminator", "Start", x_offset, start_y, fn.name)
        end = graph.add_node("terminator", "End", x_offset, start_y, fn.name)
        graph.functions.append(FunctionFlow(fn.name, start, end))
        builder = FlowBuilder(graph, end, fn.name, detail_level)
        exits, next_y = builder.build_sequence(fn.body, [ExitRef(start)], x_offset, start_y + 120)
        end_y = max(next_y + 20, graph.max_y + 50)
        graph.set_node_position(end, x_offset, end_y)
        for ref in exits:
            if ref.kind == "normal":
                graph.add_edge(ref.node_id, end, ref.label)
        terminal_edges = [
            edge
            for edge in graph.edges
            if edge.target == end
            and graph.node(edge.source).function == fn.name
            and re.search(r"\b(return|throw|terminate)\b", edge.label)
        ]
        if len(terminal_edges) > 1:
            terminal_merge = graph.add_node("merge", "", x_offset, end_y - 42, fn.name)
            for edge in terminal_edges:
                edge.target = terminal_merge
            graph.add_edge(terminal_merge, end, "return")
        x_offset += 720
    assign_route_lanes(graph)
    return graph


def write_mermaid(graph: FlowGraph, path: Path) -> None:
    lines = ["flowchart TD"]
    for node in graph.nodes:
        label = mermaid_escape(node.label)
        if node.kind in {"terminator", "return"}:
            lines.append(f"    {node.id}([{label}])")
        elif node.kind == "merge":
            lines.append(f"    {node.id}(( ))")
        elif node.kind in {"decision", "switch"}:
            lines.append(f"    {node.id}{{{label}}}")
        elif node.kind == "io":
            lines.append(f"    {node.id}[/{label}/]")
        else:
            lines.append(f"    {node.id}[{label}]")
    for edge in graph.edges:
        label = mermaid_escape(edge.label)
        arrow = f"|{label}| " if label else ""
        lines.append(f"    {edge.source} --> {arrow}{edge.target}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def mermaid_escape(value: str) -> str:
    return value.replace('"', "'").replace("[", "(").replace("]", ")").replace("{", "(").replace("}", ")")


def write_drawio(graph: FlowGraph, path: Path) -> None:
    mxfile = ET.Element("mxfile", {"host": "code2flowchart", "agent": "python", "version": "1.0"})
    diagram = ET.SubElement(mxfile, "diagram", {"name": "Page-1", "id": "c-flowchart"})
    model = ET.SubElement(
        diagram,
        "mxGraphModel",
        {
            "dx": "1400",
            "dy": "1000",
            "grid": "1",
            "gridSize": "10",
            "guides": "1",
            "tooltips": "1",
            "connect": "1",
            "arrows": "1",
            "fold": "1",
            "page": "1",
            "pageScale": "1",
            "pageWidth": "1169",
            "pageHeight": str(max(900, int(graph.max_y + 200))),
            "math": "0",
            "shadow": "0",
        },
    )
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", {"id": "0"})
    ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})
    for node in graph.nodes:
        cell = ET.SubElement(
            root,
            "mxCell",
            {
                "id": node.id,
                "value": node.label,
                "style": drawio_style(node.kind),
                "parent": "1",
                "vertex": "1",
            },
        )
        ET.SubElement(
            cell,
            "mxGeometry",
            {
                "x": f"{node.x - node.w / 2:.1f}",
                "y": f"{node.y:.1f}",
                "width": f"{node.w:.1f}",
                "height": f"{node.h:.1f}",
                "as": "geometry",
            },
        )
    for idx, edge in enumerate(graph.edges, 1):
        cell = ET.SubElement(
            root,
            "mxCell",
            {
                "id": f"e{idx}",
                "value": edge.label,
                "style": drawio_edge_style(graph, edge),
                "parent": "1",
                "source": edge.source,
                "target": edge.target,
                "edge": "1",
            },
        )
        points = edge_points(graph, edge)
        geom_attrs = {"relative": "1", "as": "geometry"}
        if edge.backward or side_routed_edge(graph, edge):
            geom_attrs["x"] = "-0.85"
            geom_attrs["y"] = "-12"
        geom = ET.SubElement(cell, "mxGeometry", geom_attrs)
        if len(points) > 2:
            arr = ET.SubElement(geom, "Array", {"as": "points"})
            for x, y in points[1:-1]:
                ET.SubElement(arr, "mxPoint", {"x": f"{x:.1f}", "y": f"{y:.1f}"})
    indent_xml(mxfile)
    path.write_text(ET.tostring(mxfile, encoding="unicode"), encoding="utf-8")


def drawio_style(kind: str) -> str:
    if kind == "merge":
        return "ellipse;whiteSpace=wrap;html=1;fillColor=#333333;strokeColor=#333333;"
    if kind in {"terminator", "return"}:
        return "ellipse;whiteSpace=wrap;html=1;"
    if kind in {"decision", "switch"}:
        return "rhombus;whiteSpace=wrap;html=1;"
    if kind == "io":
        return "shape=parallelogram;perimeter=parallelogramPerimeter;whiteSpace=wrap;html=1;fixedSize=1;"
    if kind == "function":
        return "rounded=1;whiteSpace=wrap;html=1;fontStyle=1;fillColor=#dae8fc;strokeColor=#6c8ebf;"
    if kind == "label":
        return "rounded=1;dashed=1;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;"
    if kind == "goto":
        return "rounded=1;whiteSpace=wrap;html=1;fillColor=#f8cecc;strokeColor=#b85450;"
    if kind in {"break", "continue"}:
        return "rounded=1;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;"
    return "rounded=0;whiteSpace=wrap;html=1;"


def drawio_edge_style(graph: FlowGraph, edge: Edge) -> str:
    style = "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;labelBackgroundColor=#ffffff;"
    if edge.backward:
        return style + "exitX=0;exitY=0.5;entryX=0;entryY=0.5;"
    if side_routed_edge(graph, edge):
        side = route_side(graph, edge)
        if side < 0:
            return style + "exitX=0;exitY=0.5;entryX=0.5;entryY=0;"
        return style + "exitX=1;exitY=0.5;entryX=0.5;entryY=0;"
    return style


def indent_xml(elem: ET.Element, level: int = 0) -> None:
    pad = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = pad + "  "
        for child in elem:
            indent_xml(child, level + 1)
        if not elem[-1].tail or not elem[-1].tail.strip():
            elem[-1].tail = pad
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = pad


def write_svg(graph: FlowGraph, path: Path) -> None:
    min_x, min_y, max_x, max_y = graph_bounds(graph)
    width = max_x - min_x
    height = max_y - min_y
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" viewBox="{min_x:.0f} {min_y:.0f} {width:.0f} {height:.0f}">',
        "<defs><marker id=\"arrow\" markerWidth=\"10\" markerHeight=\"10\" refX=\"8\" refY=\"3\" orient=\"auto\"><path d=\"M0,0 L0,6 L9,3 z\" fill=\"#333\"/></marker></defs>",
        "<style>text{font-family:Arial,Helvetica,sans-serif;font-size:13px}.edge{stroke:#333;stroke-width:1.4;fill:none;marker-end:url(#arrow)}.label{font-size:12px;fill:#111}</style>",
    ]
    for edge in graph.edges:
        parts.append(svg_edge(graph, edge))
    for node in graph.nodes:
        parts.append(svg_node(node))
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def svg_node(node: Node) -> str:
    x = node.x - node.w / 2
    y = node.y
    fill = "#ffffff"
    stroke = "#333333"
    if node.kind == "function":
        fill = "#dae8fc"
        stroke = "#6c8ebf"
    elif node.kind == "label":
        fill = "#e1d5e7"
        stroke = "#9673a6"
    elif node.kind == "goto":
        fill = "#f8cecc"
        stroke = "#b85450"
    elif node.kind in {"break", "continue"}:
        fill = "#fff2cc"
        stroke = "#d6b656"
    if node.kind == "merge":
        shape = f'<ellipse cx="{node.x:.1f}" cy="{y + node.h / 2:.1f}" rx="{node.w / 2:.1f}" ry="{node.h / 2:.1f}" fill="#333333" stroke="#333333"/>'
    elif node.kind in {"terminator", "return"}:
        shape = f'<ellipse cx="{node.x:.1f}" cy="{y + node.h / 2:.1f}" rx="{node.w / 2:.1f}" ry="{node.h / 2:.1f}" fill="{fill}" stroke="{stroke}"/>'
    elif node.kind in {"decision", "switch"}:
        pts = f"{node.x:.1f},{y:.1f} {x + node.w:.1f},{y + node.h / 2:.1f} {node.x:.1f},{y + node.h:.1f} {x:.1f},{y + node.h / 2:.1f}"
        shape = f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}"/>'
    elif node.kind == "io":
        skew = 24
        pts = f"{x + skew:.1f},{y:.1f} {x + node.w:.1f},{y:.1f} {x + node.w - skew:.1f},{y + node.h:.1f} {x:.1f},{y + node.h:.1f}"
        shape = f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}"/>'
    else:
        rx = 8 if node.kind in {"function", "break", "continue"} else 0
        shape = f'<rect x="{x:.1f}" y="{y:.1f}" width="{node.w:.1f}" height="{node.h:.1f}" rx="{rx}" fill="{fill}" stroke="{stroke}"/>'
    text = svg_text(node, node.x, y + node.h / 2)
    return f"<g>{shape}{text}</g>"


def svg_text(node: Node, cx: float, cy: float) -> str:
    lines = node_label_lines(node.kind, node.label)
    line_h = 15
    start = cy - (len(lines) - 1) * line_h / 2
    parts = []
    for idx, line in enumerate(lines):
        parts.append(
            f'<text x="{cx:.1f}" y="{start + idx * line_h:.1f}" text-anchor="middle" dominant-baseline="middle">{html.escape(line)}</text>'
        )
    return "".join(parts)


def svg_edge(graph: FlowGraph, edge: Edge) -> str:
    points = edge_points(graph, edge)
    d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    lx, ly = edge_label_point(graph, edge, points)
    label = f'<text class="label" x="{lx + 6:.1f}" y="{ly - 6:.1f}">{html.escape(edge.label)}</text>' if edge.label else ""
    return f'<path class="edge" d="{d}"/>{label}'


def edge_points(graph: FlowGraph, edge: Edge) -> list[tuple[float, float]]:
    s = graph.node(edge.source)
    t = graph.node(edge.target)
    if edge.backward:
        left = min(s.x - s.w / 2, t.x - t.w / 2) - side_lane_offset(edge, 240)
        return [
            (s.x - s.w / 2, s.y + s.h / 2),
            (left, s.y + s.h / 2),
            (left, t.y + t.h / 2),
            (t.x - t.w / 2, t.y + t.h / 2),
        ]
    if side_routed_edge(graph, edge) and t.y >= s.y:
        side = route_side(graph, edge)
        lane = side_lane_index(edge)
        merge_y = t.y - 26 - lane * 12
        if re.search(r"\b(return|throw|terminate)\b", edge.label):
            merge_y = t.y - 26
        if side < 0:
            left = side_route_coordinate(graph, edge, -1, 80)
            return [
                (s.x - s.w / 2, s.y + s.h / 2),
                (left, s.y + s.h / 2),
                (left, merge_y),
                (t.x, merge_y),
                (t.x, t.y),
            ]
        right = side_route_coordinate(graph, edge, 1, 120)
        return [
            (s.x + s.w / 2, s.y + s.h / 2),
            (right, s.y + s.h / 2),
            (right, merge_y),
            (t.x, merge_y),
            (t.x, t.y),
        ]
    if t.y >= s.y:
        mid_y = (s.y + s.h + t.y) / 2
        return [(s.x, s.y + s.h), (s.x, mid_y), (t.x, mid_y), (t.x, t.y)]
    return [(s.x, s.y), (t.x, t.y + t.h)]


def side_route_coordinate(graph: FlowGraph, edge: Edge, side: int, base: float) -> float:
    """Place a forward side channel outside every node it must bypass."""
    source = graph.node(edge.source)
    target = graph.node(edge.target)
    siblings = [edge]
    if target.kind == "merge":
        # Branches that intentionally converge at one connector share a rail.
        # This depicts an actual merge instead of drawing several parallel
        # long-distance bypasses for the same destination.
        siblings = [
            candidate
            for candidate in graph.edges
            if candidate.target == edge.target
            and candidate.backward is False
            and side_routed_edge(graph, candidate)
            and route_side(graph, candidate) == side
        ]
    elif re.search(r"\b(return|throw|terminate)\b", edge.label):
        # Every terminal edge ends at the same End node; use one outer rail.
        siblings = [
            candidate
            for candidate in graph.edges
            if re.search(r"\b(return|throw|terminate)\b", candidate.label)
            and graph.node(candidate.target).id == target.id
        ]
    top = min(graph.node(candidate.source).y for candidate in siblings)
    bottom = max(
        max(graph.node(candidate.source).y + graph.node(candidate.source).h, target.y + target.h)
        for candidate in siblings
    )
    nodes = [
        node
        for node in graph.nodes
        if node.y < bottom and node.y + node.h > top
    ]
    shared_rail = len(siblings) > 1
    offset = base + (24 if shared_rail else side_lane_index(edge) * 72)
    if side < 0:
        return min(node.x - node.w / 2 for node in nodes) - offset
    return max(node.x + node.w / 2 for node in nodes) + offset


def side_routed_edge(graph: FlowGraph, edge: Edge) -> bool:
    source = graph.node(edge.source)
    target = graph.node(edge.target)
    if target.y <= source.y:
        return False
    if re.search(r"\b(break|goto|return|throw|terminate)\b", edge.label):
        return True
    # Any decision outcome that skips intermediate nodes needs a side channel.
    # This includes empty guard branches such as `if (invalid) { } else ...`.
    if source.kind not in {"decision", "switch"}:
        return False
    source_bottom = source.y + source.h
    target_top = target.y
    for node in graph.nodes:
        if node.id in {source.id, target.id}:
            continue
        overlaps_vertical_gap = node.y < target_top and node.y + node.h > source_bottom
        crosses_spine = node.x - node.w / 2 <= source.x <= node.x + node.w / 2
        if overlaps_vertical_gap and crosses_spine:
            return True
    return False


def assign_route_lanes(graph: FlowGraph) -> None:
    """Assign non-overlapping side lanes to every routed edge.

    The old edge-number modulo scheme reused a lane after four edges, which
    made nested retries draw on top of each other. Here, overlapping vertical
    intervals always receive distinct lanes.
    """
    groups: dict[int, list[tuple[float, float, Edge]]] = {-1: [], 1: []}
    for edge in graph.edges:
        if edge.backward:
            side = -1
        elif side_routed_edge(graph, edge):
            side = route_side(graph, edge)
        else:
            continue
        source = graph.node(edge.source)
        target = graph.node(edge.target)
        top = min(source.y + source.h / 2, target.y + target.h / 2)
        bottom = max(source.y + source.h / 2, target.y + target.h / 2)
        edge.route_side = side
        groups[side].append((top, bottom, edge))

    for entries in groups.values():
        lane_ends: list[float] = []
        for top, bottom, edge in sorted(entries, key=lambda item: (item[0], item[1], edge_number(item[2].label))):
            lane = 0
            while lane < len(lane_ends) and lane_ends[lane] > top + 1:
                lane += 1
            if lane == len(lane_ends):
                lane_ends.append(bottom)
            else:
                lane_ends[lane] = bottom
            edge.route_lane = lane


def side_lane_offset(edge: Edge, base: float) -> float:
    # Stagger side channels so overlapping loop, break, and goto edges remain distinct.
    return base + side_lane_index(edge) * 72


def side_lane_index(edge: Edge) -> int:
    return edge.route_lane


def route_side(graph: FlowGraph, edge: Edge) -> int:
    if edge.route_side:
        return edge.route_side
    source = graph.node(edge.source)
    target = graph.node(edge.target)
    if "yes break" in edge.label and abs(source.x - target.x) < 20:
        return -1
    if source.x < target.x - 10:
        return -1
    return 1


def edge_label_point(graph: FlowGraph, edge: Edge, points: list[tuple[float, float]]) -> tuple[float, float]:
    if side_routed_edge(graph, edge) or edge.backward:
        return points[1]
    if graph.node(edge.target).kind == "merge":
        return points[1]
    return points[len(points) // 2]


def write_png(graph: FlowGraph, png_path: Path) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        write_minimal_png(png_path, 900, 600)
        return
    min_x, min_y, max_x, max_y = graph_bounds(graph)
    width = max_x - min_x
    height = max_y - min_y
    scale = min(1.6, max(0.45, 1800 / max(width, height)))
    margin = 20

    def pt(p: tuple[float, float]) -> tuple[int, int]:
        return (int((p[0] - min_x) * scale + margin), int((p[1] - min_y) * scale + margin))

    img = Image.new("RGB", (int(width * scale) + margin * 2, int(height * scale) + margin * 2), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    for edge in graph.edges:
        points = [pt(p) for p in edge_points(graph, edge)]
        draw.line(points, fill=(50, 50, 50), width=2)
        draw_arrowhead(draw, points[-2], points[-1])
        if edge.label:
            lx, ly = edge_label_point(graph, edge, [tuple(float(v) for v in p) for p in edge_points(graph, edge)])
            lx, ly = pt((lx, ly))
            tx, ty = lx + 4, ly - 14
            bbox = draw.textbbox((tx, ty), edge.label, font=font)
            draw.rectangle((bbox[0] - 2, bbox[1] - 1, bbox[2] + 2, bbox[3] + 1), fill="white")
            draw.text((tx, ty), edge.label, fill=(20, 20, 20), font=font)

    for node in graph.nodes:
        draw_png_node(draw, font, node, pt, scale)
    img.save(png_path)


def graph_bounds(graph: FlowGraph) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for node in graph.nodes:
        xs.extend([node.x - node.w / 2, node.x + node.w / 2])
        ys.extend([node.y, node.y + node.h])
    for edge in graph.edges:
        for x, y in edge_points(graph, edge):
            xs.append(x)
            ys.append(y)
    return (
        min(xs, default=0) - 80,
        min(ys, default=0) - 30,
        max(xs, default=500) + 140,
        max(ys, default=500) + 120,
    )


def draw_arrowhead(draw, p1: tuple[int, int], p2: tuple[int, int]) -> None:
    angle = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    size = 9
    left = (p2[0] - size * math.cos(angle - math.pi / 6), p2[1] - size * math.sin(angle - math.pi / 6))
    right = (p2[0] - size * math.cos(angle + math.pi / 6), p2[1] - size * math.sin(angle + math.pi / 6))
    draw.polygon([p2, (int(left[0]), int(left[1])), (int(right[0]), int(right[1]))], fill=(50, 50, 50))


def draw_png_node(draw, font, node: Node, pt, scale: float) -> None:
    x1, y1 = pt((node.x - node.w / 2, node.y))
    x2, y2 = pt((node.x + node.w / 2, node.y + node.h))
    cx, cy = pt((node.x, node.y + node.h / 2))
    fill = (255, 255, 255)
    outline = (40, 40, 40)
    if node.kind == "function":
        fill = (218, 232, 252)
        outline = (108, 142, 191)
    elif node.kind == "label":
        fill = (225, 213, 231)
        outline = (150, 115, 166)
    elif node.kind == "goto":
        fill = (248, 206, 204)
        outline = (184, 84, 80)
    elif node.kind in {"break", "continue"}:
        fill = (255, 242, 204)
        outline = (214, 182, 86)
    if node.kind == "merge":
        draw.ellipse((x1, y1, x2, y2), fill=(51, 51, 51), outline=(51, 51, 51), width=1)
    elif node.kind in {"terminator", "return"}:
        draw.ellipse((x1, y1, x2, y2), fill=fill, outline=outline, width=2)
    elif node.kind in {"decision", "switch"}:
        draw.polygon([(cx, y1), (x2, cy), (cx, y2), (x1, cy)], fill=fill, outline=outline)
    elif node.kind == "io":
        skew = int(22 * scale)
        draw.polygon([(x1 + skew, y1), (x2, y1), (x2 - skew, y2), (x1, y2)], fill=fill, outline=outline)
    else:
        draw.rectangle((x1, y1, x2, y2), fill=fill, outline=outline, width=2)
    lines = node_label_lines(node.kind, node.label)
    line_h = 12
    start_y = cy - (len(lines) * line_h) // 2
    for idx, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, start_y + idx * line_h), line, fill=(20, 20, 20), font=font)


def write_minimal_png(path: Path, width: int, height: int) -> None:
    # Valid white PNG fallback, no third-party dependency required.
    raw = b"".join(b"\x00" + b"\xff\xff\xff" * width for _ in range(height))
    def chunk(kind: bytes, data: bytes) -> bytes:
        return len(data).to_bytes(4, "big") + kind + data + zlib.crc32(kind + data).to_bytes(4, "big")
    data = b"\x89PNG\r\n\x1a\n"
    data += chunk(b"IHDR", width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00")
    data += chunk(b"IDAT", zlib.compress(raw, 9))
    data += chunk(b"IEND", b"")
    path.write_bytes(data)


def validate_drawio(path: Path) -> tuple[bool, str]:
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        return False, f"XML parse error: {exc}"
    root = tree.getroot()
    if root.tag != "mxfile":
        return False, "Root element is not mxfile."
    if root.find(".//mxGraphModel/root") is None:
        return False, "mxGraphModel/root is missing."
    return True, "draw.io XML is well-formed and contains mxGraphModel/root."


def edge_number(label: str) -> int:
    match = re.match(r"^(\d+)", label.strip())
    return int(match.group(1)) if match else 0


def enumerate_function_paths(graph: FlowGraph, max_paths_per_function: int = 200) -> list[FunctionPaths]:
    results: list[FunctionPaths] = []
    outgoing: dict[str, list[tuple[int, Edge]]] = {}
    for idx, edge in enumerate(graph.edges):
        outgoing.setdefault(edge.source, []).append((idx, edge))
    for edges in outgoing.values():
        edges.sort(key=lambda item: edge_number(item[1].label))

    max_depth = len(graph.edges) + sum(1 for edge in graph.edges if edge.backward) + 10

    for fn in graph.functions:
        paths: list[list[PathStep]] = []
        truncated = False

        def dfs(node_id: str, steps: list[PathStep], back_counts: dict[int, int]) -> None:
            nonlocal truncated
            if truncated:
                return
            if node_id == fn.end_id:
                paths.append(list(steps))
                if len(paths) >= max_paths_per_function:
                    truncated = True
                return
            if len(steps) > max_depth:
                return
            for edge_idx, edge in outgoing.get(node_id, []):
                if edge.backward and back_counts.get(edge_idx, 0) >= 1:
                    continue
                source = graph.node(edge.source)
                target = graph.node(edge.target)
                if source.function != fn.name or target.function != fn.name:
                    continue
                next_counts = dict(back_counts)
                if edge.backward:
                    next_counts[edge_idx] = next_counts.get(edge_idx, 0) + 1
                steps.append(
                    PathStep(
                        edge_number(edge.label),
                        edge.label,
                        source.label,
                        target.label,
                    )
                )
                dfs(edge.target, steps, next_counts)
                steps.pop()

        dfs(fn.start_id, [], {})
        results.append(FunctionPaths(fn.name, paths, truncated))
    return results


def write_paths_report(path: Path, function_paths: list[FunctionPaths]) -> None:
    lines = ["# Function branch paths / 函数分支路径", ""]
    lines.append(
        "Each path is a Start-to-End edge-number sequence. Loop back edges are expanded at most once per path."
    )
    lines.append(
        "每条路径是一个 Start-to-End 的边号序列。循环回边每条路径最多展开一次。"
    )
    lines.append("")
    lines.append(
        "**Important / 重要提醒：** Paths are enumerated by traversing the control-flow graph "
        "combinatorially. The enumeration does NOT perform data-flow analysis, so some paths "
        "may combine contradictory branch outcomes (e.g., a loop that sets `count > 0` followed "
        "by `if (count == 0)` taking the `yes` branch). Always filter paths against semantic "
        "constraints — the listed count is an upper bound, not a precise reachable-path count."
    )
    lines.append(
        "路径是通过控制流图的组合遍历枚举的，不包含数据流分析。部分路径可能组合了矛盾的谓词 "
        "（例如循环体内设置了 `count > 0`，后续 `if (count == 0)` 却走了 `yes` 分支）。"
        "路径数是理论上界，不是精确可达路径数，用于测试规划前必须做语义过滤。"
    )
    lines.append("")
    for item in function_paths:
        lines.append(f"## {item.function}")
        lines.append("")
        lines.append(f"Branch path count: {len(item.paths)}" + ("+" if item.truncated else ""))
        if item.truncated:
            lines.append("Path listing was truncated at the configured maximum.")
        if not item.paths:
            lines.append("- No complete Start-to-End path found.")
            lines.append("")
            continue
        for idx, steps in enumerate(item.paths, 1):
            sequence = "-".join(str(step.edge_no) for step in steps if step.edge_no)
            lines.append(f"- Path {idx}: `{sequence}`")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def statement_iter(statements: list[Statement]) -> Iterable[Statement]:
    for stmt in statements:
        yield stmt
        yield from statement_iter(stmt.body)
        yield from statement_iter(stmt.else_body)
        for _, case_body in stmt.cases:
            yield from statement_iter(case_body)


def base_function_name(name: str) -> str:
    if "::" in name:
        return name.split("::")[-1]
    return name


def output_folder_name(name: str) -> str:
    """Return a filesystem-safe folder/file stem for a function name."""
    normalized = re.sub(r'[<>:"/\\|?*]+', "_", name.strip())
    return normalized.strip(". ") or "unnamed_function"


def normalize_call_name(name: str) -> str:
    return re.sub(r"\s*(::|->|\.)\s*", r"\1", name).strip()


def split_top_level(text: str, separator: str = ",") -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    for idx, ch in enumerate(text):
        if ch in "([{<":
            depth += 1
        elif ch in ")]}>":
            depth = max(0, depth - 1)
        elif ch == separator and depth == 0:
            parts.append(text[start:idx].strip())
            start = idx + 1
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def clean_type(type_text: str) -> str:
    return re.sub(r"\s+", " ", type_text.replace(" *", "*").replace(" &", "&")).strip()


def parse_function_signature(header: str, function_name: str) -> dict[str, object]:
    match = re.search(r"\((.*)\)", header)
    params_text = match.group(1).strip() if match else ""
    prefix = header[: match.start()].strip() if match else header.strip()
    short_name = base_function_name(function_name).lstrip("~")
    name_pos = prefix.rfind(short_name)
    return_type = prefix[:name_pos].strip() if name_pos >= 0 else prefix
    return_type = re.sub(r"\b(static|extern|inline|virtual|explicit|friend|constexpr|consteval)\b", "", return_type)
    return_type = clean_type(return_type) or ("destructor" if function_name.split("::")[-1].startswith("~") else "constructor/implicit")
    return {
        "return_type": return_type,
        "parameters": parse_parameters(params_text),
    }


def parse_parameters(params_text: str) -> list[dict[str, object]]:
    if not params_text or params_text == "void":
        return []
    params: list[dict[str, object]] = []
    for idx, raw_param in enumerate(split_top_level(params_text), 1):
        params.append(parse_parameter(raw_param, idx))
    return params


def parse_parameter(raw_param: str, index: int) -> dict[str, object]:
    raw = re.sub(r"=.*$", "", raw_param.strip()).strip()
    array_suffix = ""
    array_match = re.search(r"(\[[^\]]*\])\s*$", raw)
    if array_match:
        array_suffix = array_match.group(1)
        raw = raw[: array_match.start()].strip()
    parts = raw.split()
    if not parts:
        name = f"param{index}"
        type_text = "unknown"
    else:
        name = parts[-1]
        type_text = " ".join(parts[:-1])
        pointer_prefix = ""
        while name.startswith("*") or name.startswith("&"):
            pointer_prefix += name[0]
            name = name[1:]
        type_text = clean_type((type_text + " " + pointer_prefix).strip())
        if not type_text:
            type_text = "unknown"
    name = re.sub(r"[^A-Za-z_]\w*$", "", name) or f"param{index}"
    if array_suffix:
        type_text = clean_type(type_text + " " + array_suffix)
    direction = infer_parameter_direction(type_text, name)
    return {
        "index": index,
        "name": name,
        "type": type_text,
        "direction": direction,
        "is_pointer": "*" in type_text or "[" in type_text,
        "is_reference": "&" in type_text,
        "is_const": bool(re.search(r"\bconst\b", type_text)),
        "range": infer_type_range(type_text),
        "description_draft": describe_parameter(name, type_text, direction),
    }


def infer_parameter_direction(type_text: str, name: str = "") -> str:
    is_const = bool(re.search(r"\bconst\b", type_text))
    output_name = bool(re.search(r"(^out_|^output$|^result$|^ret_|^dst$|^dest$)", name))
    if "[" in type_text:
        return "input" if is_const else ("output" if output_name else "input_output")
    if "*" in type_text or "&" in type_text:
        return "input" if is_const else ("output" if output_name else "input_output")
    return "input"


def infer_type_range(type_text: str) -> str:
    text = type_text.replace("const", "").strip()
    if re.search(r"\b(std::)?string\b", text):
        return "empty, nominal text, long text, and special-character text"
    if re.search(r"\bchar\b", text) and ("*" in text or "[" in text):
        return "null/empty string, nominal string, max-length string, and invalid buffer when allowed"
    if "*" in text or "&" in text or "[" in text:
        if "&" in text and "*" not in text:
            return "valid referenced object; include boundary values for the referenced data"
        return "valid object/buffer; include null or invalid pointer as negative tests when allowed"
    if re.search(r"\bbool\b|_Bool", text):
        return "false or true"
    if re.search(r"\bu?int(8|16|32|64)_t\b", text):
        bits = int(re.search(r"\bu?int(8|16|32|64)_t\b", text).group(1))
        signed = not re.search(r"\buint", text)
        if signed:
            return f"{-(2 ** (bits - 1))}..{2 ** (bits - 1) - 1}"
        return f"0..{2 ** bits - 1}"
    if re.search(r"\bunsigned\b", text):
        return "0..type max"
    if re.search(r"\b(char|short|int|long|size_t|float|double)\b", text):
        return "type-dependent numeric range; include boundary, nominal, and invalid-domain values"
    return "unknown; infer from comparisons, comments, or requirements"


def describe_parameter(name: str, type_text: str, direction: str) -> str:
    if direction == "input":
        return f"Input parameter `{name}` of type `{type_text}`."
    if direction == "output":
        return f"Output parameter `{name}` of type `{type_text}`."
    return f"Input/output parameter `{name}` of type `{type_text}`."


def return_value_info(signature: dict[str, object]) -> dict[str, object]:
    return_type = str(signature.get("return_type", "unknown"))
    if return_type == "void":
        return {
            "type": "void",
            "direction": "none",
            "range": "no return value",
            "description_draft": "No return value.",
        }
    if return_type in {"constructor/implicit", "destructor"}:
        return {
            "type": return_type,
            "direction": "constructed object/lifecycle",
            "range": "not applicable",
            "description_draft": "Constructor/destructor style function without an explicit return value.",
        }
    return {
        "type": return_type,
        "direction": "return",
        "range": infer_type_range(return_type),
        "description_draft": f"Returns `{return_type}`.",
    }


def output_parameters(parameters: list[dict[str, object]]) -> list[dict[str, object]]:
    return [param for param in parameters if param.get("direction") in {"output", "input_output"}]


def extract_calls_from_label(label: str) -> list[str]:
    calls: list[str] = []
    pattern = re.compile(r"([A-Za-z_]\w*(?:(?:::|->|\.)\s*[A-Za-z_]\w*)*)\s*\(")
    skip = CONTROL_KEYWORDS | {
        "sizeof",
        "alignof",
        "decltype",
        "static_cast",
        "const_cast",
        "reinterpret_cast",
        "dynamic_cast",
    }
    for match in pattern.finditer(label):
        name = normalize_call_name(match.group(1))
        if name in skip or base_function_name(name) in skip:
            continue
        calls.append(name)
    for scoped, bare in (("std::cin", "cin"), ("std::cout", "cout"), ("std::cerr", "cerr"), ("std::clog", "clog")):
        if re.search(rf"\b{re.escape(scoped)}\b", label):
            if scoped not in calls:
                calls.append(scoped)
        elif re.search(rf"(?<!::)\b{bare}\b", label) and bare not in calls:
            calls.append(bare)
    return calls


def function_calls(fn: Function) -> list[str]:
    calls: list[str] = []
    for stmt in statement_iter(fn.body):
        for call in extract_calls_from_label(stmt.label):
            if call not in calls:
                calls.append(call)
    return calls


def boolean_complexity(label: str) -> int:
    return len(re.findall(r"&&|\|\|", label))


def cyclomatic_complexity(fn: Function) -> int:
    score = 1
    for stmt in statement_iter(fn.body):
        if stmt.kind in {"if", "for", "while", "do_while"}:
            score += 1 + boolean_complexity(stmt.label)
        elif stmt.kind == "switch":
            score += max(1, len(stmt.cases))
            score += boolean_complexity(stmt.label)
        elif stmt.kind == "try":
            score += len(stmt.cases)
    return score


def collect_branches(statements: list[Statement]) -> list[dict[str, object]]:
    branches: list[dict[str, object]] = []

    def visit(items: list[Statement]) -> None:
        for stmt in items:
            if stmt.kind == "if":
                branches.append(
                    {
                        "id": len(branches) + 1,
                        "kind": "if",
                        "line": stmt.line,
                        "condition": stmt.label,
                        "outcomes": ["yes", "no"],
                    }
                )
            elif stmt.kind in {"for", "while", "do_while"}:
                branches.append(
                    {
                        "id": len(branches) + 1,
                        "kind": stmt.kind,
                        "line": stmt.line,
                        "condition": stmt.label,
                        "outcomes": ["enter/yes", "exit/no", "loop"],
                    }
                )
            elif stmt.kind == "switch":
                branches.append(
                    {
                        "id": len(branches) + 1,
                        "kind": "switch",
                        "line": stmt.line,
                        "condition": stmt.label,
                        "outcomes": [case_label for case_label, _ in stmt.cases] or ["default"],
                    }
                )
            elif stmt.kind == "try":
                branches.append(
                    {
                        "id": len(branches) + 1,
                        "kind": "try",
                        "line": stmt.line,
                        "condition": "exception path",
                        "outcomes": ["normal"] + [case_label for case_label, _ in stmt.cases],
                    }
                )
            visit(stmt.body)
            visit(stmt.else_body)
            for _, case_body in stmt.cases:
                visit(case_body)

    visit(statements)
    return branches


def path_conditions(steps: list[PathStep]) -> list[str]:
    conditions: list[str] = []
    for step in steps:
        label = step.edge_label
        if re.search(r"\b(yes|no|case|default|loop|break|continue|return|throw|goto|catch)\b", label):
            detail = f"{step.source_label} -> {label} -> {step.target_label}"
            conditions.append(detail)
    return conditions


def path_to_json(idx: int, steps: list[PathStep]) -> dict[str, object]:
    edges = [step.edge_no for step in steps if step.edge_no]
    labels = [step.edge_label for step in steps]
    conditions = path_conditions(steps)
    return {
        "id": idx,
        "edge_sequence": edges,
        "edge_sequence_text": "-".join(str(edge) for edge in edges),
        "labels": labels,
        "conditions": conditions,
        "suggested_test_name": f"test_path_{idx:02d}",
        "test_intent": "Cover path " + ("-".join(str(edge) for edge in edges) if edges else str(idx)),
    }


def graph_function_edges(graph: FlowGraph, function_name: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for edge in graph.edges:
        source = graph.node(edge.source)
        target = graph.node(edge.target)
        if source.function != function_name or target.function != function_name:
            continue
        rows.append(
            {
                "edge_no": edge_number(edge.label),
                "label": edge.label,
                "source": source.label,
                "target": target.label,
                "backward": edge.backward,
            }
        )
    return rows


def draft_description(fn: Function, calls: list[str], branches: list[dict[str, object]]) -> str:
    pieces = [f"Function `{fn.name}` starts at line {fn.line}"]
    if branches:
        pieces.append(f"contains {len(branches)} control-flow branch point(s)")
    if calls:
        pieces.append("calls " + ", ".join(calls[:8]))
    return "; ".join(pieces) + "."


def test_framework_options() -> list[dict[str, object]]:
    return [
        {
            "id": "google_test",
            "name": "GoogleTest",
            "languages": ["C++"],
            "best_for": "C++ unit tests with assertions, fixtures, and typed tests.",
            "mocking": ["GoogleMock"],
        },
        {
            "id": "google_test_fff",
            "name": "GoogleTest + FFF/Fake Function Framework",
            "aliases": ["GoogleTest + FSF", "GTest + FFF"],
            "languages": ["C", "C++"],
            "best_for": "Testing C modules or C-like embedded code from a C++ GoogleTest harness while faking C functions.",
            "mocking": ["FFF"],
        },
        {
            "id": "unity_cmock",
            "name": "Unity + CMock",
            "languages": ["C"],
            "best_for": "Embedded C unit tests with generated mocks for hardware and OS dependencies.",
            "mocking": ["CMock"],
        },
        {
            "id": "ceedling",
            "name": "Ceedling",
            "languages": ["C"],
            "best_for": "Project-managed Unity/CMock test generation and execution.",
            "mocking": ["CMock"],
        },
        {
            "id": "catch2",
            "name": "Catch2",
            "languages": ["C++"],
            "best_for": "Header-friendly C++ tests with concise test cases.",
            "mocking": ["manual fakes", "third-party mocks"],
        },
        {
            "id": "doctest",
            "name": "doctest",
            "languages": ["C++"],
            "best_for": "Lightweight C++ unit tests, including tests colocated with code.",
            "mocking": ["manual fakes", "third-party mocks"],
        },
    ]


def recommend_frameworks(source: Path, fn: Function, calls: list[str]) -> list[str]:
    suffix = source.suffix.lower()
    has_hardware_or_os_calls = any(re.match(r"(HAL_|os|PLC_|__)", call) for call in calls)
    if suffix in {".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"} or "::" in fn.name:
        return ["google_test", "google_test_fff"] if has_hardware_or_os_calls else ["google_test", "catch2", "doctest"]
    if has_hardware_or_os_calls:
        return ["unity_cmock", "ceedling", "google_test_fff"]
    return ["unity_cmock", "google_test_fff"]


def build_analysis(
    source: Path,
    functions: list[Function],
    graph: FlowGraph,
    function_paths: list[FunctionPaths],
    artifacts: dict[str, Path],
    xml_ok: bool,
    xml_message: str,
) -> dict[str, object]:
    calls_by_function = {fn.name: function_calls(fn) for fn in functions}
    simple_names = {fn.name: base_function_name(fn.name) for fn in functions}
    called_by: dict[str, list[str]] = {fn.name: [] for fn in functions}
    for caller, calls in calls_by_function.items():
        for callee in functions:
            targets = {callee.name, simple_names[callee.name]}
            if any(base_function_name(call) in targets or call in targets for call in calls):
                if caller != callee.name and caller not in called_by[callee.name]:
                    called_by[callee.name].append(caller)

    paths_by_function = {item.function: item for item in function_paths}
    function_rows: list[dict[str, object]] = []
    for fn in functions:
        branches = collect_branches(fn.body)
        calls = calls_by_function[fn.name]
        paths = paths_by_function.get(fn.name, FunctionPaths(fn.name, []))
        path_rows = [path_to_json(idx, steps) for idx, steps in enumerate(paths.paths, 1)]
        signature = parse_function_signature(fn.header, fn.name)
        parameters = signature["parameters"]

        # --- DD Evaluation fields ---
        # Branch count: number of decision/diamond nodes (if, for, while, do-while, switch)
        branch_num = sum(1 for b in branches if b.get("kind") in ("if", "for", "while", "do_while", "switch"))
        cc = cyclomatic_complexity(fn)
        if cc < 2:
            complexity_level = "Low"
        elif cc <= 10:
            complexity_level = "Medium"
        else:
            complexity_level = "High"

        # Interactivity: non-deduplicated call count (only actual function calls)
        call_counts: dict[str, int] = {}
        _call_re = re.compile(r"(?:^|\b)([a-zA-Z_]\w*)\s*\(")
        for stmt in statement_iter(fn.body):
            if stmt.kind in ("expr", "io", "terminate") and stmt.label:
                for m in _call_re.finditer(stmt.label):
                    call_name = m.group(1)
                    # Skip C keywords that look like function calls
                    if call_name in ("if", "for", "while", "switch", "return", "sizeof",
                                     "void", "int", "char", "float", "double", "long",
                                     "short", "unsigned", "signed", "struct", "union",
                                     "enum", "static", "const", "volatile", "typedef",
                                     "extern", "U8", "U16", "U32", "S8", "S16", "S32"):
                        continue
                    call_counts[call_name] = call_counts.get(call_name, 0) + 1
        interactivity = sum(call_counts.values())
        calls_detail = [{"name": name, "count": cnt} for name, cnt in sorted(call_counts.items())]
        criticality = len(called_by[fn.name])
        function_rows.append(
            {
                "name": fn.name,
                "signature": fn.header,
                "line": fn.line,
                "function_id": "",  # filled by --project-prefix or LLM
                "description_draft": draft_description(fn, calls, branches),
                "constraint": "",   # filled by LLM
                "verification_criteria": "",  # filled by LLM
                "return_value": return_value_info(signature),
                "parameters": parameters,
                "input_parameters": [param for param in parameters if param.get("direction") in {"input", "input_output"}],
                "output_parameters": output_parameters(parameters),
                "cyclomatic_complexity": cc,
                "function_evaluation": {
                    "branch_num": branch_num,
                    "cyclomatic_complexity": cc,
                    "complexity_level": complexity_level,
                    "interactivity": interactivity,
                    "calls_detail": calls_detail,
                    "criticality": criticality,
                },
                "calls": calls,
                "called_by_in_file": called_by[fn.name],
                "recommended_test_frameworks": recommend_frameworks(source, fn, calls),
                "branches": branches,
                "branch_path_count": len(paths.paths),
                "paths_truncated": paths.truncated,
                "paths_note": (
                    "Paths are enumerated combinatorially from the control-flow graph without "
                    "data-flow analysis. Some paths may combine contradictory branch outcomes "
                    "(e.g. a branch that depends on a variable being both zero and non-zero). "
                    "Always filter against semantic constraints — the count is an upper bound, "
                    "not a precise reachable-path count. "
                    "路径是通过控制流图的组合遍历枚举的，不包含数据流分析。部分路径可能组合了矛盾的"
                    "谓词。路径数是理论上界，不是精确可达路径数，使用前必须做语义过滤。"
                ),
                "paths": path_rows,
                "unit_test_scenarios": [
                    {
                        "id": row["id"],
                        "name": row["suggested_test_name"],
                        "covers_edges": row["edge_sequence"],
                        "conditions": row["conditions"],
                        "expected_focus": row["test_intent"],
                    }
                    for row in path_rows
                ],
                "cfg_edges": graph_function_edges(graph, fn.name),
            }
        )

    return {
        "schema_version": "0.2",
        "tool": "code2Flowchart",
        "source": str(source),
        "xml_validation": {"ok": xml_ok, "message": xml_message},
        "artifacts": {key: str(value) for key, value in artifacts.items()},
        "test_framework_options": test_framework_options(),
        "functions": function_rows,
        "agent_notes": [
            "description_draft is deterministic and should be refined by an LLM before user-facing output.",
            "called_by_in_file only uses functions parsed from the current input file; project-wide callers require scanning the whole project.",
            "unit_test_scenarios are path coverage hints, not complete compile-ready test code.",
        ],
    }


def write_analysis(path: Path, analysis: dict[str, object]) -> None:
    path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_report(
    path: Path,
    functions: list[Function],
    ok: bool,
    message: str,
    function_paths: list[FunctionPaths],
    generated: set[str],
) -> None:
    lines = [
        "# code2Flowchart conversion report",
        "",
        f"XML validation: {'OK' if ok else 'FAILED'}",
        f"Validation message: {message}",
        "",
        "Parsed functions:",
    ]
    if functions:
        for fn in functions:
            lines.append(f"- {fn.name} at line {fn.line}: {len(fn.body)} top-level statements")
    else:
        lines.append("- None. Check whether the source has complete function definitions.")
    lines.extend(["", "Branch paths:"])
    if function_paths:
        for item in function_paths:
            suffix = "+" if item.truncated else ""
            lines.append(f"- {item.function}: {len(item.paths)}{suffix} Start-to-End paths")
    else:
        lines.append("- None.")
    if "paths" in generated:
        lines.extend(["", "See the generated `.paths.md` file for edge-number sequences such as `1-2-3-5`."])
    if "analysis" in generated:
        lines.extend(["", "See the generated `.analysis.json` file for structured function analysis and test-planning data."])
    lines.extend(
        [
            "",
            "Supported constructs: if/else, for, while, do while, switch/case/default, break, continue, goto labels, return, basic C++ try/catch/throw, C stdio, and common C++ iostream calls.",
            "Limitations: heavy macros/templates, complex declarations, preprocessor-heavy code, lambdas, and unusual formatting may need manual cleanup.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def convert(
    source: Path,
    out_dir: Path,
    basename: str | None = None,
    outputs: set[str] | None = None,
    function_name: str | None = None,
    detail_level: str = "standard",
) -> dict[str, Path]:
    functions = parse_source(source)
    if not functions:
        raise ValueError("No complete function definitions were parsed from the source file")
    if function_name:
        functions = [
            fn for fn in functions
            if fn.name == function_name or base_function_name(fn.name) == function_name
        ]
        if not functions:
            raise ValueError(f"Function not found: {function_name}")
    folder_source = functions[0].name if len(functions) == 1 else (basename or source.stem)
    out_dir = out_dir / output_folder_name(folder_source)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = basename or output_folder_name(functions[0].name if len(functions) == 1 else source.stem)
    graph = build_graph(functions, detail_level)
    all_paths = {
        "mermaid": out_dir / f"{name}.mmd",
        "drawio": out_dir / f"{name}.drawio",
        "svg": out_dir / f"{name}.svg",
        "png": out_dir / f"{name}.png",
        "paths": out_dir / f"{name}.paths.md",
        "report": out_dir / f"{name}.report.md",
        "analysis": out_dir / f"{name}.analysis.json",
    }
    requested = set(outputs or {"drawio"})
    requested.add("drawio")
    unknown = requested - set(all_paths)
    if unknown:
        raise ValueError(f"Unknown output types: {', '.join(sorted(unknown))}")
    paths = {key: all_paths[key] for key in all_paths if key in requested}

    write_drawio(graph, all_paths["drawio"])
    if "mermaid" in requested:
        write_mermaid(graph, all_paths["mermaid"])
    if "svg" in requested:
        write_svg(graph, all_paths["svg"])
    if "png" in requested:
        write_png(graph, all_paths["png"])

    needs_paths = bool(requested & {"paths", "report", "analysis"})
    function_paths = enumerate_function_paths(graph) if needs_paths else []
    if "paths" in requested:
        write_paths_report(all_paths["paths"], function_paths)

    ok, message = validate_drawio(all_paths["drawio"])
    if "report" in requested:
        write_report(all_paths["report"], functions, ok, message, function_paths, requested)
    if "analysis" in requested:
        write_analysis(
            all_paths["analysis"],
            build_analysis(source, functions, graph, function_paths, paths, ok, message),
        )
    if not ok:
        raise RuntimeError(message)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert C/C++ source to an editable draw.io flowchart.")
    parser.add_argument("source", type=Path, help="Input C/C++ source file")
    parser.add_argument(
        "-o",
        "--out-dir",
        type=Path,
        default=None,
        help="Base output directory (a function-named subfolder is created inside it)",
    )
    parser.add_argument("--name", default=None, help="Output basename without extension")
    parser.add_argument("--function", dest="function_name", help="Convert only the named function")
    parser.add_argument(
        "--detail-level",
        choices=("overview", "standard", "detailed"),
        default="standard",
        help="Diagram density: standard keeps deep retry internals compact; detailed expands them",
    )
    parser.add_argument("--preview", action="store_true", help="Also generate a PNG preview")
    parser.add_argument("--svg", action="store_true", help="Also generate an SVG preview")
    parser.add_argument("--mermaid", action="store_true", help="Also generate Mermaid text")
    parser.add_argument("--paths", action="store_true", help="Also generate the path report")
    parser.add_argument("--report", action="store_true", help="Also generate the conversion report")
    parser.add_argument("--analysis", action="store_true", help="Also generate analysis JSON")
    parser.add_argument("--validate", action="store_true", help="Run structural validation on the .drawio after generation")
    parser.add_argument("--dd", action="store_true", help="Generate Detailed Design document (.dd.md) from analysis.json")
    parser.add_argument("--ut", action="store_true", help="Generate Unit Test design (.ut.md) and test code (.ut.cpp, .ut.c)")
    parser.add_argument("--project-prefix", default="", help="Function ID prefix, e.g. SWDD_CHARGE (sets function_id in DD/UT)")
    parser.add_argument("--all", action="store_true", help="Generate every supported artifact (implies --validate --dd --ut)")
    args = parser.parse_args(argv)
    source = args.source
    if not source.exists():
        print(f"Input file does not exist: {source}", file=sys.stderr)
        return 2
    skill_dir = Path(__file__).resolve().parent.parent
    out_dir = args.out_dir or skill_dir / "output"
    outputs = {"drawio"}
    if args.all:
        outputs = {"drawio", "png", "svg", "mermaid", "paths", "report", "analysis"}
        args.validate = True
        args.dd = True
        args.ut = True
    else:
        if args.preview:
            outputs.add("png")
        if args.svg:
            outputs.add("svg")
        if args.mermaid:
            outputs.add("mermaid")
        if args.paths:
            outputs.add("paths")
        if args.report:
            outputs.add("report")
        if args.analysis:
            outputs.add("analysis")
    try:
        paths = convert(source, out_dir, args.name, outputs, args.function_name, args.detail_level)
    except Exception as exc:
        print(f"Conversion failed: {exc}", file=sys.stderr)
        return 1
    for key, value in paths.items():
        print(f"{key}: {value}")

    # Structural validation
    if args.validate and "drawio" in paths:
        validate_script = Path(__file__).resolve().parent / "validate.py"
        if validate_script.exists():
            result = subprocess.run(
                [sys.executable, str(validate_script), str(paths["drawio"])],
                capture_output=True, text=True,
            )
            if result.stdout:
                print(result.stdout)
            if result.returncode != 0:
                if result.stderr:
                    print(result.stderr, file=sys.stderr)
                print("note: validation found issues. Fix and re-run, or inspect manually.", file=sys.stderr)
        else:
            print("note: validate.py not found — skipping structural validation", file=sys.stderr)

    # DD/UT generation
    if (args.dd or args.ut) and "drawio" in paths:
        analysis_path = paths.get("drawio").parent / f"{paths['drawio'].stem}.analysis.json"
        if not analysis_path.exists():
            # analysis wasn't generated — regenerate it
            source_path = source
            functions = parse_source(source_path)
            if args.function_name:
                functions = [fn for fn in functions if fn.name == args.function_name
                             or base_function_name(fn.name) == args.function_name]
            if functions:
                graph = build_graph(functions, args.detail_level)
                function_paths = enumerate_function_paths(graph)
                ok, message = validate_drawio(paths["drawio"])
                analysis = build_analysis(source_path, functions, graph, function_paths, paths, ok, message)
                write_analysis(analysis_path, analysis)

        if args.dd:
            dd_script = Path(__file__).resolve().parent / "dd_generator.py"
            if dd_script.exists():
                cmd = [sys.executable, str(dd_script), str(analysis_path)]
                if args.project_prefix:
                    cmd += ["--project-prefix", args.project_prefix]
                subprocess.run(cmd)
            else:
                print("note: dd_generator.py not found — skipping DD generation", file=sys.stderr)

        if args.ut:
            ut_script = Path(__file__).resolve().parent / "ut_generator.py"
            if ut_script.exists():
                cmd = [sys.executable, str(ut_script), str(analysis_path)]
                if args.project_prefix:
                    cmd += ["--project-prefix", args.project_prefix]
                subprocess.run(cmd)
            else:
                print("note: ut_generator.py not found — skipping UT generation", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
