import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import code2flowchart as converter
from c_flowchart import CFlowchart
from lang_support import detect_from_extension, get


class CFlowchartAdapterTests(unittest.TestCase):
    def setUp(self):
        self.support = CFlowchart()

    def test_single_function_matches_main_converter(self):
        source = "int f(int x) { if (x < 0) return -1; return x; }"
        tokens = self.support.tokenize(source)
        functions = self.support.parse(tokens)
        graph = self.support.build_graph(functions)
        expected = converter.build_graph(functions)
        self.assertEqual(graph.nodes, expected.nodes)
        self.assertEqual(graph.edges, expected.edges)
        self.assertEqual(graph.functions, expected.functions)

    def test_multiple_functions_are_not_silently_dropped(self):
        source = "int first(void) { return 1; } int second(void) { return 2; }"
        functions = self.support.parse(self.support.tokenize(source))
        graph = self.support.build_graph(functions)
        self.assertEqual([function.name for function in graph.functions], ["first", "second"])
        self.assertEqual(sum(node.label == "Start" for node in graph.nodes), 2)
        self.assertEqual(sum(node.label == "End" for node in graph.nodes), 2)

    def test_empty_function_list_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no functions"):
            self.support.build_graph([])

    def test_constant_preprocessor_branch_matches_cli(self):
        source = "#if 0\nint disabled(void) { return 0; }\n#else\nint active(void) { return 1; }\n#endif\n"
        functions = self.support.parse(self.support.tokenize(source))
        self.assertEqual([function.name for function in functions], ["active"])

    def test_unknown_preprocessor_configuration_is_rejected(self):
        source = "#ifdef UNKNOWN\nint f(void) { return 0; }\n#endif\n"
        with self.assertRaisesRegex(ValueError, "unknown definition status"):
            self.support.tokenize(source)

    def test_registry_exposes_c_and_cpp(self):
        self.assertIs(get("c"), CFlowchart)
        self.assertIs(detect_from_extension(Path("example.c")), CFlowchart)
        self.assertIs(detect_from_extension(Path("example.cpp")), CFlowchart)


if __name__ == "__main__":
    unittest.main()
