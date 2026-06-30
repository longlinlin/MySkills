#!/usr/bin/env python3
"""
Convert C/C++ source code into Mermaid, draw.io XML, SVG, and PNG flowchart previews.

The parser is intentionally lightweight. It targets teaching/lab-style C/C++ code and
the most common control-flow constructs rather than full ISO C or C++ grammar.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import re
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
        label = compact_tokens(parts)
        kind = "io" if is_io_label(label) else "expr"
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
    no_space_before = {")", "]", "}", ";", ",", ":", "::", "++", "--"}
    no_space_after = {"(", "[", "{", ".", "->", "::", "++", "--", "!", "~"}
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
    width = max(130, min(300, 9 * max_line_len(label) + 34))
    if kind in {"decision", "switch"}:
        return max(width, 170), 86
    if kind in {"terminator", "return"}:
        return max(120, min(240, width)), 62
    if kind == "io":
        return max(width, 170), 62
    if kind == "function":
        return max(width, 180), 44
    if kind == "label":
        return max(width, 130), 44
    return width, max(54, 22 * len(wrap_label(label, 28)) + 18)


def max_line_len(label: str) -> int:
    return max((len(line) for line in wrap_label(label, 32)), default=8)


def wrap_label(label: str, width: int = 28) -> list[str]:
    text = re.sub(r"\s+", " ", label.strip())
    if not text:
        return [""]
    lines: list[str] = []
    for segment in text.split("\\n"):
        lines.extend(textwrap.wrap(segment, width=width, break_long_words=True) or [""])
    return lines[:6]


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


class FlowBuilder:
    X_GAP = 260
    Y_GAP = 120

    def __init__(self, graph: FlowGraph, end_id: str, function: str) -> None:
        self.g = graph
        self.end_id = end_id
        self.function = function

    def build_sequence(
        self, statements: list[Statement], incoming: list[ExitRef], x: float, y: float
    ) -> tuple[list[ExitRef], float]:
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
            exits, cur_y = self.build_statement(stmt, normal, x, cur_y)
            normal = [e for e in exits if e.kind == "normal"]
            carried.extend(e for e in exits if e.kind != "normal")
            if not normal:
                cur_y += self.Y_GAP / 2
        return normal + carried, cur_y

    def build_statement(
        self, stmt: Statement, incoming: list[ExitRef], x: float, y: float
    ) -> tuple[list[ExitRef], float]:
        if stmt.kind in {"expr", "io"}:
            node = self.g.add_node(stmt.kind, stmt.label, x, y, self.function)
            self.g.connect(incoming, node)
            return [ExitRef(node)], y + self.Y_GAP
        if stmt.kind == "return":
            node = self.g.add_node("return", stmt.label, x, y, self.function)
            self.g.connect(incoming, node)
            self.g.add_edge(node, self.end_id, "return")
            return [ExitRef(node, kind="return")], y + self.Y_GAP
        if stmt.kind == "throw":
            node = self.g.add_node("return", stmt.label, x, y, self.function)
            self.g.connect(incoming, node)
            self.g.add_edge(node, self.end_id, "throw")
            return [ExitRef(node, kind="throw")], y + self.Y_GAP
        if stmt.kind == "goto":
            node = self.g.add_node("goto", stmt.label, x, y, self.function)
            self.g.connect(incoming, node)
            target = goto_target(stmt.label)
            return [ExitRef(node, kind=f"goto:{target}" if target else "goto")], y + self.Y_GAP
        if stmt.kind == "label":
            node = self.g.add_node("label", f"{stmt.label}:", x, y, self.function)
            self.g.connect(incoming, node)
            return [ExitRef(node)], y + self.Y_GAP
        if stmt.kind in {"break", "continue"}:
            node = self.g.add_node(stmt.kind, stmt.label, x, y, self.function)
            self.g.connect(incoming, node)
            return [ExitRef(node, kind=stmt.kind)], y + self.Y_GAP
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
        return [ExitRef(node)], y + self.Y_GAP

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
        branch_y = y + self.Y_GAP
        then_exits, then_y = self.build_sequence(
            stmt.body, [ExitRef(cond, "yes")], x - self.X_GAP / 2, branch_y
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
        cond = self.g.add_node("decision", stmt.label, x, y, self.function)
        self.g.connect(incoming, cond)
        body_exits, body_y = self.build_sequence(stmt.body, [ExitRef(cond, "yes")], x, y + self.Y_GAP)
        after_loop = [ExitRef(cond, "no")]
        has_break_exit = False
        for ref in body_exits:
            if ref.kind in {"normal", "continue"}:
                self.g.add_edge(ref.node_id, cond, "loop", backward=True)
            elif ref.kind == "break":
                has_break_exit = True
                after_loop.append(ExitRef(ref.node_id, "break"))
            else:
                after_loop.append(ref)
        exit_padding = 90 if has_break_exit else 0
        return after_loop, max(body_y, y + self.Y_GAP * 2) + exit_padding

    def build_do_while(
        self, stmt: Statement, incoming: list[ExitRef], x: float, y: float
    ) -> tuple[list[ExitRef], float]:
        do_node = self.g.add_node("expr", "do", x, y, self.function)
        self.g.connect(incoming, do_node)
        body_exits, body_y = self.build_sequence(stmt.body, [ExitRef(do_node)], x, y + self.Y_GAP)
        cond = self.g.add_node("decision", stmt.label, x, max(body_y, y + self.Y_GAP), self.function)
        after_loop = [ExitRef(cond, "no")]
        has_break_exit = False
        for ref in body_exits:
            if ref.kind in {"normal", "continue"}:
                self.g.add_edge(ref.node_id, cond)
            elif ref.kind == "break":
                has_break_exit = True
                after_loop.append(ExitRef(ref.node_id, "break"))
            else:
                after_loop.append(ref)
        self.g.add_edge(cond, do_node, "yes", backward=True)
        return after_loop, cond_y_after(self.g.node(cond)) + (110 if has_break_exit else 40)

    def build_switch(
        self, stmt: Statement, incoming: list[ExitRef], x: float, y: float
    ) -> tuple[list[ExitRef], float]:
        sw = self.g.add_node("switch", stmt.label, x, y, self.function)
        self.g.connect(incoming, sw)
        if not stmt.cases:
            return [ExitRef(sw)], y + self.Y_GAP
        exits: list[ExitRef] = []
        case_count = len(stmt.cases)
        start_x = x - self.X_GAP * (case_count - 1) / 2
        max_y = y + self.Y_GAP
        for idx, (case_label, body) in enumerate(stmt.cases):
            case_x = start_x + idx * self.X_GAP
            case_exits, case_y = self.build_sequence(body, [ExitRef(sw, case_label)], case_x, y + self.Y_GAP)
            for ref in case_exits:
                if ref.kind == "break":
                    exits.append(ExitRef(ref.node_id, "break"))
                else:
                    exits.append(ref)
            max_y = max(max_y, case_y)
        return exits, max_y + 20

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


def build_graph(functions: list[Function]) -> FlowGraph:
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
        builder = FlowBuilder(graph, end, fn.name)
        exits, next_y = builder.build_sequence(fn.body, [ExitRef(start)], x_offset, start_y + 120)
        end_y = max(next_y + 20, graph.max_y + 50)
        graph.set_node_position(end, x_offset, end_y)
        for ref in exits:
            if ref.kind == "normal":
                graph.add_edge(ref.node_id, end, ref.label)
        x_offset += 720
    return graph


def write_mermaid(graph: FlowGraph, path: Path) -> None:
    lines = ["flowchart TD"]
    for node in graph.nodes:
        label = mermaid_escape(node.label)
        if node.kind in {"terminator", "return"}:
            lines.append(f"    {node.id}([{label}])")
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
        geom_attrs = {"relative": "1", "as": "geometry"}
        if edge.backward or side_routed_edge(graph, edge):
            geom_attrs["x"] = "-0.85"
            geom_attrs["y"] = "-12"
        geom = ET.SubElement(cell, "mxGeometry", geom_attrs)
        if edge.backward or side_routed_edge(graph, edge):
            arr = ET.SubElement(geom, "Array", {"as": "points"})
            for x, y in edge_points(graph, edge)[1:-1]:
                ET.SubElement(arr, "mxPoint", {"x": f"{x:.1f}", "y": f"{y:.1f}"})
    indent_xml(mxfile)
    path.write_text(ET.tostring(mxfile, encoding="unicode"), encoding="utf-8")


def drawio_style(kind: str) -> str:
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
    style = "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;"
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
    if node.kind in {"terminator", "return"}:
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
    text = svg_text(node.label, node.x, y + node.h / 2)
    return f"<g>{shape}{text}</g>"


def svg_text(label: str, cx: float, cy: float) -> str:
    lines = wrap_label(label, 28)
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
        if side < 0:
            left = min(s.x - s.w / 2, t.x - t.w / 2) - side_lane_offset(edge, 80)
            return [
                (s.x - s.w / 2, s.y + s.h / 2),
                (left, s.y + s.h / 2),
                (left, merge_y),
                (t.x, merge_y),
                (t.x, t.y),
            ]
        right = max(s.x + s.w / 2, t.x + t.w / 2) + side_lane_offset(edge, 120)
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


def side_routed_edge(graph: FlowGraph, edge: Edge) -> bool:
    if not re.search(r"\b(break|goto)\b", edge.label):
        return False
    source = graph.node(edge.source)
    target = graph.node(edge.target)
    return target.y > source.y


def side_lane_offset(edge: Edge, base: float) -> float:
    # Stagger side channels so loop, break, and goto edges do not sit on top of each other.
    return base + side_lane_index(edge) * 56


def side_lane_index(edge: Edge) -> int:
    return edge_number(edge.label) % 4


def route_side(graph: FlowGraph, edge: Edge) -> int:
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
            draw.text((lx + 4, ly - 14), edge.label, fill=(20, 20, 20), font=font)

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
    if node.kind in {"terminator", "return"}:
        draw.ellipse((x1, y1, x2, y2), fill=fill, outline=outline, width=2)
    elif node.kind in {"decision", "switch"}:
        draw.polygon([(cx, y1), (x2, cy), (cx, y2), (x1, cy)], fill=fill, outline=outline)
    elif node.kind == "io":
        skew = int(22 * scale)
        draw.polygon([(x1 + skew, y1), (x2, y1), (x2 - skew, y2), (x1, y2)], fill=fill, outline=outline)
    else:
        draw.rectangle((x1, y1, x2, y2), fill=fill, outline=outline, width=2)
    lines = wrap_label(node.label, 24)
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
    lines = ["# Function branch paths", ""]
    lines.append("Each path is a Start-to-End edge-number sequence. Loop back edges are expanded at most once per path.")
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
            detailed = " -> ".join(step.edge_label for step in steps)
            lines.append(f"- Path {idx}: `{sequence}`")
            lines.append(f"  Labels: {detailed}")
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


def normalize_call_name(name: str) -> str:
    return re.sub(r"\s*(::|->|\.)\s*", r"\1", name).strip()


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
        function_rows.append(
            {
                "name": fn.name,
                "signature": fn.header,
                "line": fn.line,
                "description_draft": draft_description(fn, calls, branches),
                "cyclomatic_complexity": cyclomatic_complexity(fn),
                "calls": calls,
                "called_by_in_file": called_by[fn.name],
                "branches": branches,
                "branch_path_count": len(paths.paths),
                "paths_truncated": paths.truncated,
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
        "schema_version": "0.1",
        "tool": "code2Flowchart",
        "source": str(source),
        "xml_validation": {"ok": xml_ok, "message": xml_message},
        "artifacts": {key: str(value) for key, value in artifacts.items()},
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
    lines.extend(
        [
            "",
            "See the generated `.paths.md` file for edge-number sequences such as `1-2-3-5`.",
            "See the generated `.analysis.json` file for Dify/agent-friendly function analysis, branch paths, calls, complexity, and test scenarios.",
            "",
            "Supported constructs: if/else, for, while, do while, switch/case/default, break, continue, goto labels, return, basic C++ try/catch/throw, C stdio, and common C++ iostream calls.",
            "Limitations: heavy macros/templates, complex declarations, preprocessor-heavy code, lambdas, and unusual formatting may need manual cleanup.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def convert(source: Path, out_dir: Path, basename: str | None = None) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    name = basename or source.stem
    functions = parse_source(source)
    graph = build_graph(functions)
    paths = {
        "mermaid": out_dir / f"{name}.mmd",
        "drawio": out_dir / f"{name}.drawio",
        "svg": out_dir / f"{name}.svg",
        "png": out_dir / f"{name}.png",
        "paths": out_dir / f"{name}.paths.md",
        "report": out_dir / f"{name}.report.md",
        "analysis": out_dir / f"{name}.analysis.json",
    }
    write_mermaid(graph, paths["mermaid"])
    write_drawio(graph, paths["drawio"])
    write_svg(graph, paths["svg"])
    write_png(graph, paths["png"])
    function_paths = enumerate_function_paths(graph)
    write_paths_report(paths["paths"], function_paths)
    ok, message = validate_drawio(paths["drawio"])
    write_report(paths["report"], functions, ok, message, function_paths)
    write_analysis(paths["analysis"], build_analysis(source, functions, graph, function_paths, paths, ok, message))
    if not ok:
        raise RuntimeError(message)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert C/C++ source to Mermaid, draw.io XML, SVG, and PNG.")
    parser.add_argument("source", type=Path, help="Input C/C++ source file")
    parser.add_argument("-o", "--out-dir", type=Path, default=None, help="Output directory")
    parser.add_argument("--name", default=None, help="Output basename without extension")
    args = parser.parse_args(argv)
    source = args.source
    if not source.exists():
        print(f"Input file does not exist: {source}", file=sys.stderr)
        return 2
    out_dir = args.out_dir or source.with_suffix("").parent / f"{source.stem}_flowchart"
    try:
        paths = convert(source, out_dir, args.name)
    except Exception as exc:
        print(f"Conversion failed: {exc}", file=sys.stderr)
        return 1
    for key, value in paths.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
