import json
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


SKILL_ROOT = Path(__file__).resolve().parents[1]
SAMPLES = SKILL_ROOT / "examples" / "acceptance"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
import code2flowchart as converter
import validate as diagram_validator


class DiagramAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = json.loads((SAMPLES / "cases.json").read_text(encoding="utf-8"))["cases"]

    def test_sources_match_reviewed_drawio_and_svg_baselines(self):
        for case in self.cases:
            with self.subTest(function=case["function"]):
                with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
                    generated = converter.convert(
                        SAMPLES / case["source"], Path(directory),
                        outputs={"drawio", "svg"}, function_name=case["function"],
                    )
                    for kind, artifact in generated.items():
                        baseline = SAMPLES / "baselines" / case["function"] / artifact.name
                        self.assertTrue(baseline.is_file(), str(baseline))
                        self.assertEqual(
                            artifact.read_text(encoding="utf-8"),
                            baseline.read_text(encoding="utf-8"),
                            f"{case['function']} {kind}: 先核对源码、严格校验和视觉，再人工更新基线",
                        )

    def test_independent_structure_and_rendering_invariants(self):
        for case in self.cases:
            with self.subTest(function=case["function"]):
                functions = [
                    function for function in converter.parse_source(SAMPLES / case["source"])
                    if function.name == case["function"]
                ]
                graph = converter.build_graph(functions)
                self.assertEqual(sum(node.kind == "decision" for node in graph.nodes), case["expected_decisions"])
                self.assertEqual(sum(node.kind == "return" for node in graph.nodes), case["expected_returns"])
                self.assertEqual(sum(edge.backward for edge in graph.edges), case["expected_back_edges"])
                merges = [node for node in graph.nodes if node.kind == "merge"]
                self.assertGreaterEqual(len(merges), case["minimum_hidden_junctions"])
                if case["grouped_assignment_count"]:
                    self.assertTrue(any(
                        node.kind == "expr" and len(node.label.splitlines()) == case["grouped_assignment_count"]
                        for node in graph.nodes
                    ))
                end = next(node for node in graph.nodes if node.label == "End")
                incoming = [edge for edge in graph.edges if edge.target == end.id]
                self.assertEqual(len(incoming), 1)
                self.assertTrue(all(abs(x - end.x) < 1e-6 for x, _ in converter.edge_points(graph, incoming[0])))
                for node in merges:
                    self.assertIn("opacity=0", converter.drawio_style(node.kind))
                    center = (node.x, node.y + node.h / 2)
                    for edge in graph.edges:
                        points = converter.edge_points(graph, edge)
                        if edge.target == node.id:
                            self.assertEqual(points[-1], center)
                        if edge.source == node.id:
                            self.assertEqual(points[0], center)
                for edge in graph.edges:
                    self.assertIn("jumpStyle=none", converter.drawio_edge_style(graph, edge))

    def test_baselines_have_no_structural_or_geometry_warnings(self):
        for case in self.cases:
            with self.subTest(function=case["function"]):
                path = SAMPLES / "baselines" / case["function"] / f"{case['function']}.drawio"
                tree = ET.parse(path)
                for page in tree.getroot().findall("diagram"):
                    errors, warnings = diagram_validator.check_page(page)
                    self.assertEqual(errors, [])
                    self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
