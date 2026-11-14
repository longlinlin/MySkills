import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import code2flowchart as converter
import validate as diagram_validator


def graph_from_source(source: str) -> converter.FlowGraph:
    tokens = converter.CTokenizer(source).tokenize()
    functions = converter.CParser(tokens).parse_functions()
    return converter.build_graph(functions)


def has_edge(graph: converter.FlowGraph, source: str, target: str) -> bool:
    return any(
        graph.node(edge.source).label == source and graph.node(edge.target).label == target
        for edge in graph.edges
    )


def has_path(graph: converter.FlowGraph, source: str, target: str) -> bool:
    start = next(node.id for node in graph.nodes if node.label == source)
    target_id = next(node.id for node in graph.nodes if node.label == target)
    pending = [start]
    visited = set()
    while pending:
        node_id = pending.pop()
        if node_id == target_id:
            return True
        if node_id in visited:
            continue
        visited.add(node_id)
        pending.extend(edge.target for edge in graph.edges if edge.source == node_id)
    return False


class SwitchFlowTests(unittest.TestCase):
    def test_fallthrough_reaches_next_case(self):
        graph = graph_from_source(
            "int f(int x) { switch (x) { case 1: x++; case 2: x += 2; break; "
            "default: x = 0; } return x; }"
        )
        self.assertTrue(has_path(graph, "x++", "x += 2"))

    def test_break_branch_does_not_fall_through(self):
        graph = graph_from_source(
            "int f(int x) { switch (x) { case 1: if (x) break; x++; "
            "case 2: x += 2; break; } return x; }"
        )
        self.assertTrue(has_path(graph, "x++", "x += 2"))
        self.assertFalse(has_edge(graph, "if (x)", "x += 2"))

    def test_empty_case_labels_share_next_body(self):
        graph = graph_from_source(
            "int f(int x) { switch (x) { case 1: case 2: x++; break; } return x; }"
        )
        self.assertTrue(any(
            "case 1 / case 2" in edge.label
            for edge in graph.edges
            if graph.node(edge.target).label == "x++"
        ))


class LayoutRulesTests(unittest.TestCase):
    def test_all_returns_merge_above_end_without_a_synthetic_return(self):
        graph = graph_from_source(
            "int f(int x) { if (x < 0) return -1; if (x == 0) return -2; return 0; }"
        )
        end = next(node for node in graph.nodes if node.label == "End")
        returns = [node for node in graph.nodes if node.kind == "return"]
        self.assertEqual(len(returns), 3)
        self.assertEqual(sum(node.label == "End" for node in graph.nodes), 1)
        for node in returns:
            edges = [edge for edge in graph.edges if edge.source == node.id]
            self.assertEqual(len(edges), 1)
            target = graph.node(edges[0].target)
            self.assertEqual(target.kind, "merge")
            self.assertTrue(any(
                edge.source == target.id and edge.target == end.id
                and converter.is_end_join_edge(graph, edge)
                for edge in graph.edges
            ))
            self.assertEqual(converter.semantic_edge_label(edges[0].label), "return")
            self.assertTrue(converter.display_edge_label(graph, edges[0]).isdigit())
        self.assertFalse(any(
            graph.node(edge.source).kind == "merge"
            and converter.semantic_edge_label(edge.label) == "return"
            for edge in graph.edges
        ))
        self.assertEqual(sum(edge.target == end.id for edge in graph.edges), 1)
        shared = next(edge for edge in graph.edges if converter.is_end_join_edge(graph, edge))
        join_point = converter.edge_points(graph, shared)[0]
        for edge in graph.edges:
            if edge.target == shared.source:
                self.assertEqual(converter.edge_points(graph, edge)[-1], join_point)

    def test_six_side_returns_keep_separate_rails_and_one_arrow_into_end(self):
        source = "int f(int x) { "
        for value in range(6):
            source += f"if (x == {value}) return {value}; "
        source += "return -1; }"
        graph = graph_from_source(source)
        end = next(node for node in graph.nodes if node.label == "End")
        shared_edges = [edge for edge in graph.edges if converter.is_end_join_edge(graph, edge)]
        self.assertEqual(len(shared_edges), 1)
        shared = shared_edges[0]
        incoming = [edge for edge in graph.edges if edge.target == shared.source]
        self.assertEqual(len(incoming), 7)
        side_edges = [edge for edge in incoming if converter.side_routed_edge(graph, edge)]
        self.assertEqual(len(side_edges), 6)
        self.assertEqual(len({converter.edge_points(graph, edge)[1][0] for edge in side_edges}), 6)
        self.assertEqual(converter.display_edge_label(graph, shared), "")
        shared_points = converter.edge_points(graph, shared)
        self.assertEqual(len({x for x, _ in shared_points}), 1)
        self.assertEqual(shared_points[-1], (end.x, end.y))
        self.assertLess(shared_points[0][1], shared_points[-1][1])

        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            diagram = Path(directory) / "end_ports.drawio"
            converter.write_drawio(graph, diagram)
            tree = ET.parse(diagram)
            cells = {cell.get("id"): cell for cell in tree.iter("mxCell")}
            for index, edge in enumerate(graph.edges, 1):
                if graph.node(edge.source).kind != "return" and edge is not shared:
                    continue
                cell = cells[f"e{index}"]
                if edge is shared:
                    self.assertEqual(cell.get("value"), "")
                    self.assertIn("endArrow=block", cell.get("style"))
                else:
                    self.assertTrue(cell.get("value").isdigit())
                if edge.target == shared.source:
                    self.assertIn("endArrow=none", cell.get("style"))
                actual_source = diagram_validator.endpoint(cell, "source", cells)
                expected_source = converter.edge_points(graph, edge)[0]
                self.assertAlmostEqual(actual_source[0], expected_source[0], places=6)
                self.assertAlmostEqual(actual_source[1], expected_source[1], places=6)
                actual = diagram_validator.endpoint(cell, "target", cells)
                expected = converter.edge_points(graph, edge)[-1]
                self.assertAlmostEqual(actual[0], expected[0], places=6)
                self.assertAlmostEqual(actual[1], expected[1], places=6)
            errors, warnings = diagram_validator.check_page(tree.find("diagram"))
            self.assertEqual(errors, [])
            self.assertEqual(warnings, [])

    def test_left_and_right_terminal_paths_share_one_downward_end_arrow(self):
        graph = graph_from_source(
            "int f(int x) { if (x == 1) return 1; if (x == 2) return 2; "
            "if (x == 3) abort(); if (x == 4) exit(1); return 0; }"
        )
        joins = [edge for edge in graph.edges if converter.is_end_join_edge(graph, edge)]
        self.assertEqual(len(joins), 1)
        incoming = [edge for edge in graph.edges if edge.target == joins[0].source]
        self.assertEqual(len(incoming), 5)
        self.assertEqual({
            converter.route_side(graph, edge) for edge in incoming
            if converter.side_routed_edge(graph, edge)
        }, {-1, 1})

    def test_single_early_return_also_enters_end_from_above(self):
        graph = graph_from_source(
            "void f(int x) { if (x) return; while (1) { process(); } }"
        )
        end = next(node for node in graph.nodes if node.label == "End")
        incoming = [edge for edge in graph.edges if edge.target == end.id]
        self.assertEqual(len(incoming), 1)
        self.assertTrue(converter.is_end_join_edge(graph, incoming[0]))
        self.assertEqual(converter.edge_points(graph, incoming[0])[-1], (end.x, end.y))

    def test_do_while_uses_invisible_entry_before_the_body(self):
        graph = graph_from_source("int f(int x) { do { x++; } while (x < 3); return x; }")
        loop_edge = next(edge for edge in graph.edges if edge.backward)
        entry = graph.node(loop_edge.target)
        self.assertEqual(entry.kind, "merge")
        self.assertEqual(entry.label, "")
        self.assertFalse(any(node.label == "do" for node in graph.nodes))
        self.assertTrue(any(
            edge.source == entry.id and graph.node(edge.target).label == "x++"
            for edge in graph.edges
        ))
        self.assertEqual(graph.node(loop_edge.source).label, "while (x < 3)")

    def test_empty_do_while_keeps_its_condition_and_back_edge(self):
        graph = graph_from_source("int f(int x) { do { } while (x); return x; }")
        loop_edge = next(edge for edge in graph.edges if edge.backward)
        self.assertEqual(graph.node(loop_edge.source).label, "while (x)")
        self.assertEqual(graph.node(loop_edge.target).kind, "merge")
        self.assertTrue(any(
            edge.source == loop_edge.target and edge.target == loop_edge.source
            for edge in graph.edges
        ))

    def test_drawio_ports_match_preview_route_endpoints(self):
        graph = graph_from_source(
            "int f(int x) { while (x > 0) { if (x == 2) break; x--; } "
            "do { x++; } while (x < 5); return x; }"
        )
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            diagram = Path(directory) / "ports.drawio"
            converter.write_drawio(graph, diagram)
            cells = {cell.get("id"): cell for cell in ET.parse(diagram).iter("mxCell")}
            for index, edge in enumerate(graph.edges, 1):
                cell = cells[f"e{index}"]
                points = converter.edge_points(graph, edge)
                self.assertEqual(diagram_validator.endpoint(cell, "source", cells), points[0])
                self.assertEqual(diagram_validator.endpoint(cell, "target", cells), points[-1])

    def test_consecutive_assignments_merge_within_each_straight_line_block(self):
        graph = graph_from_source(
            "int f(int x) { x = 1; x = 2; if (x) { x = 3; x = 4; } "
            "x = 5; x = 6; send(); x = 7; x = 8; return x; }"
        )
        labels = [node.label for node in graph.nodes]
        for expected in ("x = 1\nx = 2", "x = 3\nx = 4", "x = 5\nx = 6", "x = 7\nx = 8"):
            self.assertIn(expected, labels)
        self.assertIn("send(...)", labels)
        self.assertNotIn("x = 5\nx = 6\nsend()", labels)

    def test_retry_break_uses_right_rail_and_loop_uses_left_rail(self):
        graph = graph_from_source(
            "int f(void) { int retry = 0; while (retry <= 3) { "
            "status = send(); if (status == 0) break; "
            "if (retry < 3) delay(); retry++; } return status; }"
        )
        loop_edge = next(edge for edge in graph.edges if edge.backward)
        break_edge = next(edge for edge in graph.edges if "break" in edge.label)
        loop_points = converter.edge_points(graph, loop_edge)
        break_points = converter.edge_points(graph, break_edge)
        condition_exit = next(
            edge for edge in graph.edges
            if graph.node(edge.source).label.startswith("while")
            and converter.semantic_edge_label(edge.label) == "no"
        )
        condition_exit_points = converter.edge_points(graph, condition_exit)
        self.assertLess(loop_points[1][0], graph.node(loop_edge.source).x)
        self.assertGreater(break_points[1][0], graph.node(break_edge.source).x)
        self.assertLess(loop_points[1][0], break_points[1][0])
        self.assertGreater(condition_exit_points[1][0], break_points[1][0])
        self.assertGreater(condition_exit_points[-3][1], break_points[-3][1])

        for first, second in zip(loop_points, loop_points[1:]):
            for third, fourth in zip(break_points, break_points[1:]):
                if first[0] == second[0] and third[1] == fourth[1]:
                    self.assertFalse(
                        min(third[0], fourth[0]) < first[0] < max(third[0], fourth[0])
                        and min(first[1], second[1]) < third[1] < max(first[1], second[1])
                    )
                if first[1] == second[1] and third[0] == fourth[0]:
                    self.assertFalse(
                        min(first[0], second[0]) < third[0] < max(first[0], second[0])
                        and min(third[1], fourth[1]) < first[1] < max(third[1], fourth[1])
                    )

        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            diagram = Path(directory) / "retry.drawio"
            converter.write_drawio(graph, diagram)
            validator = Path(__file__).resolve().parents[1] / "scripts" / "validate.py"
            result = subprocess.run(
                [sys.executable, "-B", str(validator), str(diagram), "--strict"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("0 warning(s)", result.stdout)

    def test_multiple_loop_exits_keep_distinct_rails(self):
        graph = graph_from_source(
            "int f(int x, int y) { int n = 0; while (n < 10) { "
            "if (x) break; if (y) break; n++; } return n; }"
        )
        exits = [
            edge for edge in graph.edges
            if converter.side_routed_edge(graph, edge)
            and converter.route_side(graph, edge) == 1
        ]
        self.assertEqual(len(exits), 3)
        rail_x = [converter.edge_points(graph, edge)[1][0] for edge in exits]
        self.assertEqual(len(set(rail_x)), 3)

    def test_validator_detects_shared_side_rail_but_allows_local_join(self):
        first = [(10, 0), (100, 0), (100, 200), (0, 200), (0, 240)]
        second = [(10, 80), (100, 80), (100, 220), (0, 220), (0, 240)]
        self.assertTrue(diagram_validator.routes_share_side_rail(first, second, [0]))
        separate = [(10, 80), (80, 80), (80, 220), (0, 220), (0, 240)]
        self.assertFalse(diagram_validator.routes_share_side_rail(first, separate, [0]))

    def test_early_returns_stay_outside_later_do_while(self):
        graph = graph_from_source(
            "int f(int x, int y) { if (x) return -1; "
            "if (y) { cleanup(); return -2; } int n = 0; "
            "do { if (ready()) process(); n++; } while (n < 10); "
            "finish(); return 0; }"
        )
        loop_edge = next(edge for edge in graph.edges if edge.backward)
        loop_rail_x = converter.edge_points(graph, loop_edge)[1][0]
        early_returns = [
            edge for edge in graph.edges
            if graph.node(edge.source).kind == "return"
            and graph.node(edge.source).label != "return 0"
        ]
        self.assertEqual(len(early_returns), 2)
        for edge in early_returns:
            self.assertLess(converter.edge_points(graph, edge)[1][0], loop_rail_x)

        final_return = next(
            edge for edge in graph.edges
            if graph.node(edge.source).label == "return 0"
        )
        self.assertFalse(converter.side_routed_edge(graph, final_return))
        self.assertEqual(len({x for x, _ in converter.edge_points(graph, final_return)}), 1)

        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            diagram = Path(directory) / "early_returns.drawio"
            converter.write_drawio(graph, diagram)
            errors, warnings = diagram_validator.check_page(ET.parse(diagram).find("diagram"))
            self.assertEqual(errors, [])
            self.assertEqual(warnings, [])

    def test_early_return_still_bypasses_later_normal_statements(self):
        graph = graph_from_source("void f(int x) { if (x) return; process(); }")
        returned = next(
            edge for edge in graph.edges if graph.node(edge.source).kind == "return"
        )
        self.assertTrue(converter.side_routed_edge(graph, returned))

    def test_merge_junctions_are_invisible_in_outputs(self):
        graph = graph_from_source(
            "int f(int x) { if (x) x = 1; else x = 2; return x; }"
        )
        self.assertTrue(any(node.kind == "merge" for node in graph.nodes))
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            diagram = Path(directory) / "f.drawio"
            preview = Path(directory) / "f.svg"
            converter.write_drawio(graph, diagram)
            converter.write_svg(graph, preview)
            cells = list(ET.parse(diagram).iter("mxCell"))
            merge_ids = {node.id for node in graph.nodes if node.kind == "merge"}
            for cell in cells:
                if cell.get("id") in merge_ids:
                    self.assertIn("opacity=0", cell.get("style"))
                    self.assertIn("fillColor=none", cell.get("style"))
                if cell.get("target") in merge_ids:
                    self.assertIn("endArrow=none", cell.get("style"))
            self.assertNotIn('fill="#333333" stroke="#333333"', preview.read_text(encoding="utf-8"))


class ConditionalCompilationTests(unittest.TestCase):
    def parse_selected(self, source: str, defined=None, undefined=None):
        selected = converter.select_preprocessor_branches(source, defined, undefined)
        return converter.CParser(converter.CTokenizer(selected).tokenize()).parse_functions()[0]

    def test_constant_condition_selects_one_branch(self):
        source = "int f(void) {\n#if 0\nreturn 1;\n#else\nreturn 2;\n#endif\n}"
        function = self.parse_selected(source)
        self.assertEqual([item.label for item in function.body], ["return 2"])
        self.assertEqual(function.body[0].line, 5)

    def test_known_macro_selects_one_branch(self):
        source = "int f(void) {\n#ifdef ENABLED\nreturn 1;\n#else\nreturn 2;\n#endif\n}"
        self.assertEqual(
            [item.label for item in self.parse_selected(source, {"ENABLED"}).body],
            ["return 1"],
        )
        self.assertEqual(
            [item.label for item in self.parse_selected(source, undefined={"ENABLED"}).body],
            ["return 2"],
        )

    def test_nested_elif_uses_only_selected_branch(self):
        source = (
            "int f(void) {\n#if 0\n#if defined(UNKNOWN)\nreturn 1;\n#endif\n"
            "#elif defined(A) && !defined(B)\nreturn 2;\n#else\nreturn 3;\n#endif\n}"
        )
        function = self.parse_selected(source, {"A"}, {"B"})
        self.assertEqual([item.label for item in function.body], ["return 2"])

    def test_short_circuit_does_not_require_unused_macro(self):
        source = (
            "int f(void) {\n#if 0 && defined(UNKNOWN)\nreturn 1;\n"
            "#else\nreturn 2;\n#endif\n}"
        )
        function = self.parse_selected(source)
        self.assertEqual([item.label for item in function.body], ["return 2"])

    def test_unknown_condition_is_rejected(self):
        source = "int f(void) {\n#ifdef ENABLED\nreturn 1;\n#else\nreturn 2;\n#endif\n}"
        with self.assertRaisesRegex(ValueError, r"line 2: macro ENABLED"):
            converter.select_preprocessor_branches(source)

    def test_comment_directives_are_ignored(self):
        source = "/*\n#if UNKNOWN\n*/\nint f(void) { return 1; }"
        function = self.parse_selected(source)
        self.assertEqual([item.label for item in function.body], ["return 1"])

    def test_multiline_define_is_not_parsed_as_code(self):
        source = "#define ENABLED \\\n1\nint f(void) {\n#ifdef ENABLED\nreturn 1;\n#endif\n}"
        function = self.parse_selected(source)
        self.assertEqual([item.label for item in function.body], ["return 1"])


class CommandStatusTests(unittest.TestCase):
    def test_all_requests_png_and_generates_other_artifacts(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            source = Path(directory) / "example.c"
            source.write_text("int f(int x) { if (x) return 1; return 2; }", encoding="utf-8")
            with patch.object(converter, "write_png") as preview_writer:
                self.assertEqual(
                    converter.main([str(source), "--function", "f", "--all", "--out-dir", directory]),
                    0,
                )
                preview_writer.assert_called_once()
            self.assertTrue((Path(directory) / "f" / "f.drawio").exists())
            self.assertTrue((Path(directory) / "f" / "f.svg").exists())

    def test_missing_pillow_fails_without_creating_a_blank_png(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            source = Path(directory) / "example.c"
            source.write_text("int f(void) { return 0; }", encoding="utf-8")
            with patch.dict(sys.modules, {"PIL": None}):
                result = converter.main([
                    str(source), "--function", "f", "--svg", "--preview", "--out-dir", directory,
                ])
            self.assertEqual(result, 1)
            self.assertTrue((Path(directory) / "f" / "f.drawio").exists())
            self.assertTrue((Path(directory) / "f" / "f.svg").exists())
            self.assertFalse((Path(directory) / "f" / "f.png").exists())

    def test_missing_pillow_does_not_overwrite_an_existing_preview(self):
        graph = graph_from_source("int f(void) { return 0; }")
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            preview = Path(directory) / "existing.png"
            preview.write_bytes(b"existing preview")
            with patch.dict(sys.modules, {"PIL": None}):
                with self.assertRaisesRegex(RuntimeError, "requires Pillow"):
                    converter.write_png(graph, preview)
            self.assertEqual(preview.read_bytes(), b"existing preview")

    def test_cli_outputs_only_active_preprocessor_branch(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            source = Path(directory) / "example.c"
            source.write_text(
                "int f(void) {\n#ifdef ENABLED\nreturn 1;\n#else\nreturn 2;\n#endif\n}",
                encoding="utf-8",
            )
            args = [str(source), "--function", "f", "--define", "ENABLED", "--validate",
                    "--out-dir", directory]
            self.assertEqual(converter.main(args), 0)
            diagram = Path(directory) / "f" / "f.drawio"
            labels = [cell.get("value") for cell in ET.parse(diagram).iter("mxCell")]
            self.assertIn("return 1", labels)
            self.assertNotIn("return 2", labels)

    def test_validation_failure_returns_nonzero(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            source = Path(directory) / "example.c"
            source.write_text("int f(void) { return 1; }", encoding="utf-8")
            diagram = Path(directory) / "example.drawio"
            with patch.object(converter, "convert", return_value={"drawio": diagram}):
                with patch.object(converter.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)):
                    self.assertEqual(converter.main([str(source), "--validate"]), 1)

    def test_document_generation_failure_returns_nonzero(self):
        for flag in ("--dd", "--ut"):
            with self.subTest(flag=flag):
                with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
                    source = Path(directory) / "example.c"
                    source.write_text("int f(void) { return 1; }", encoding="utf-8")
                    diagram = Path(directory) / "example.drawio"
                    diagram.with_suffix(".analysis.json").write_text("{}", encoding="utf-8")
                    with patch.object(converter, "convert", return_value={"drawio": diagram}):
                        with patch.object(
                            converter.subprocess, "run",
                            return_value=subprocess.CompletedProcess([], 1),
                        ):
                            self.assertEqual(converter.main([str(source), flag]), 1)


if __name__ == "__main__":
    unittest.main()
