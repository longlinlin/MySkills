import re
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import code2flowchart as converter


class ControlFlowSemanticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(__file__).resolve().parents[1] / "examples" / "acceptance" / "control_flow.c"
        cls.functions = {function.name: function for function in converter.parse_source(source)}

    def graph(self, name):
        return converter.build_graph([self.functions[name]])

    def next_visible(self, graph, source_label, branch=None):
        """只越过不可见合流点，核对跳转的直接可执行后继。"""
        sources = [node for node in graph.nodes if node.label == source_label]
        self.assertEqual(len(sources), 1, source_label)
        pending = [
            edge.target for edge in graph.edges
            if edge.source == sources[0].id
            and (branch is None or converter.semantic_edge_label(edge.label) == branch)
        ]
        visited = set()
        targets = set()
        while pending:
            node_id = pending.pop()
            if node_id in visited:
                continue
            visited.add(node_id)
            node = graph.node(node_id)
            if node.kind == "merge":
                pending.extend(edge.target for edge in graph.edges if edge.source == node_id)
            else:
                targets.add(node.label)
        return targets

    def test_for_continue_runs_update_before_next_condition(self):
        graph = self.graph("for_continue_case")
        self.assertEqual(self.next_visible(graph, "if (i == 1)", "yes continue"), {"i++"})
        self.assertEqual(self.next_visible(graph, "i++"), {"for (i < limit)"})
        self.assertEqual(self.next_visible(graph, "int i = 0"), {"for (i < limit)"})
        init = next(node for node in graph.nodes if node.label == "int i = 0")
        self.assertEqual(sum(edge.target == init.id for edge in graph.edges), 1)

    def test_for_break_skips_update_and_reaches_loop_successor(self):
        graph = self.graph("for_break_case")
        self.assertEqual(self.next_visible(graph, "if (i == 2)", "yes break"), {"return total"})
        self.assertEqual(self.next_visible(graph, "total += i"), {"i++"})

    def test_switch_break_does_not_exit_enclosing_loop(self):
        graph = self.graph("switch_in_loop_case")
        calls = [node for node in graph.nodes if node.label == "record_value(...)"]
        self.assertEqual(len(calls), 2)
        after = next(node for node in graph.nodes if node.label == "after_switch(...)")
        for call in calls:
            pending = [edge.target for edge in graph.edges if edge.source == call.id]
            targets = set()
            visited = set()
            while pending:
                target_id = pending.pop()
                if target_id in visited:
                    continue
                visited.add(target_id)
                target = graph.node(target_id)
                if target.kind == "merge":
                    pending.extend(edge.target for edge in graph.edges if edge.source == target.id)
                else:
                    targets.add(target.id)
            self.assertEqual(targets, {after.id})

    def test_continue_inside_switch_targets_enclosing_while(self):
        graph = self.graph("switch_in_loop_case")
        self.assertEqual(self.next_visible(graph, "continue"), {"while (count > 0)"})

    def test_inner_loop_break_does_not_exit_outer_loop(self):
        graph = self.graph("nested_break_case")
        self.assertEqual(self.next_visible(graph, "if (mode)", "yes break"), {"after_inner(...)"})

    def test_forward_goto_reaches_cleanup_without_falling_through(self):
        graph = self.graph("forward_cleanup_case")
        self.assertEqual(self.next_visible(graph, "goto cleanup"), {"cleanup:"})
        self.assertEqual(self.next_visible(graph, "cleanup:"), {"release_resource(...)"})

    def test_backward_goto_reaches_label_and_is_marked_backward(self):
        graph = self.graph("backward_goto_case")
        self.assertEqual(self.next_visible(graph, "goto retry"), {"retry:"})
        jump = next(node for node in graph.nodes if node.label == "goto retry")
        self.assertTrue(next(edge for edge in graph.edges if edge.source == jump.id).backward)

    def test_goto_can_target_label_in_another_block(self):
        graph = self.graph("cross_block_goto_case")
        self.assertEqual(self.next_visible(graph, "goto cleanup"), {"cleanup:"})

    def test_unknown_goto_label_is_rejected(self):
        source = "int f(void) { goto missing; }"
        functions = converter.CParser(converter.CTokenizer(source).tokenize()).parse_functions()
        with self.assertRaisesRegex(ValueError, "missing"):
            converter.build_graph(functions)

    def test_duplicate_label_is_rejected(self):
        source = "int f(void) { same: ; same: return 0; }"
        functions = converter.CParser(converter.CTokenizer(source).tokenize()).parse_functions()
        with self.assertRaisesRegex(ValueError, "Duplicate label"):
            converter.build_graph(functions)

    def test_for_header_does_not_split_semicolon_inside_string(self):
        source = 'int f(int limit) { for (int i = prepare(";"); i < limit; i++) { work(); } return 0; }'
        functions = converter.CParser(converter.CTokenizer(source).tokenize()).parse_functions()
        loop = functions[0].body[0]
        self.assertIsNotNone(loop.for_clauses)
        self.assertIn('";"', loop.for_clauses[0])
        self.assertEqual(loop.for_clauses[1:], ("i < limit", "i++"))

    def test_do_continue_targets_condition_and_all_junctions_are_continuous(self):
        graph = self.graph("do_continue_case")
        self.assertEqual(self.next_visible(graph, "if (count > 2)", "yes continue"), {"while (count > 0)"})
        for node in graph.nodes:
            if node.kind != "merge":
                continue
            center = (node.x, node.y + node.h / 2)
            for edge in graph.edges:
                points = converter.edge_points(graph, edge)
                if edge.target == node.id:
                    self.assertEqual(points[-1], center)
                if edge.source == node.id:
                    self.assertEqual(points[0], center)

    def test_short_circuit_conditions_keep_side_effects_inside_one_decision(self):
        for name, condition in (
            ("short_circuit_and_case", "if (value++ && probe())"),
            ("short_circuit_or_case", "if (value-- || probe())"),
        ):
            with self.subTest(function=name):
                graph = self.graph(name)
                calls = [node for node in graph.nodes if re.search(r"probe\s*\(", node.label)]
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0].kind, "decision")
                actual_tokens = [token.text for token in converter.CTokenizer(calls[0].label).tokenize()]
                expected_tokens = [token.text for token in converter.CTokenizer(condition).tokenize()]
                self.assertEqual(actual_tokens, expected_tokens)
                self.assertEqual(self.next_visible(graph, calls[0].label, "yes"), {"return value"})
                self.assertEqual(self.next_visible(graph, calls[0].label, "no"), {"return - 1"})

    def test_nested_returns_are_not_replaced_with_invented_power_logic(self):
        graph = self.graph("nested_return_case")
        labels = {node.label for node in graph.nodes}
        self.assertIn("while (state > 0)", labels)
        self.assertIn("if (state == 1)", labels)
        self.assertIn("return 77", labels)
        self.assertNotIn("Target power verified?", labels)

    def test_for_with_initialization_and_no_condition_has_no_false_exit(self):
        graph = self.graph("infinite_for_case")
        loops = [node for node in graph.nodes if node.label == "for (;;)"]
        self.assertEqual(len(loops), 1)
        labels = [converter.semantic_edge_label(edge.label) for edge in graph.edges if edge.source == loops[0].id]
        self.assertEqual(labels, ["enter"])
        self.assertEqual(self.next_visible(graph, "if (i == limit)", "yes break"), {"return 0"})

    def test_for_with_constant_true_condition_has_no_false_exit(self):
        source = "int f(int stop) { for (; 1; ) { if (stop) break; } return 0; }"
        functions = converter.CParser(converter.CTokenizer(source).tokenize()).parse_functions()
        graph = converter.build_graph(functions)
        loop = next(node for node in graph.nodes if node.label == "for (1)")
        labels = [converter.semantic_edge_label(edge.label) for edge in graph.edges if edge.source == loop.id]
        self.assertEqual(labels, ["enter"])


if __name__ == "__main__":
    unittest.main()
