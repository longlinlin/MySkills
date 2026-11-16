import copy
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import ut_generator


def sample_analysis() -> dict:
    return {
        "source": "control.c",
        "functions": [{
            "name": "control_step",
            "calls": ["read_sensor", "set_output", "delay_ticks"],
            "paths": [
                {
                    "edge_sequence_text": "1-2-3",
                    "conditions": ["if ((x < 0) || !ready) -> yes"],
                    "labels": ["1", "2 yes", "3 return"],
                },
                {
                    "edge_sequence_text": "1-2-4-5",
                    "conditions": ["if ((x < 0) || !ready) -> no"],
                    "labels": ["1", "2 no", "4 loop", "5 break"],
                },
            ],
        }],
    }


class UnitTestDraftTests(unittest.TestCase):
    def test_incomplete_skeletons_skip_every_case(self):
        analysis = sample_analysis()
        cpp = ut_generator.generate_gtest_cpp(analysis)
        unity = ut_generator.generate_unity_c(analysis)
        self.assertEqual(len(re.findall(r"\bTEST_F\(", cpp)), 2)
        self.assertEqual(len(re.findall(r"\bGTEST_SKIP\(\)", cpp)), 2)
        self.assertEqual(len(re.findall(r"^void test_", unity, re.MULTILINE)), 2)
        self.assertEqual(len(re.findall(r"\bTEST_IGNORE_MESSAGE\(", unity)), 2)

    def test_unknown_dependencies_do_not_get_fabricated_signatures_or_success(self):
        analysis = sample_analysis()
        for output in (
            ut_generator.generate_gtest_cpp(analysis),
            ut_generator.generate_unity_c(analysis),
        ):
            with self.subTest(output=output[:30]):
                for invented in ("LPI2C", "FAKE_VALUE_FUNC(", "FSF_MOCK(", "_IgnoreAndReturn("):
                    self.assertNotIn(invented, output)
                for dependency in analysis["functions"][0]["calls"]:
                    self.assertIn(dependency, output)

    def test_local_ids_match_all_outputs_and_are_unique_across_functions(self):
        analysis = sample_analysis()
        second = copy.deepcopy(analysis["functions"][0])
        second["name"] = "other_step"
        analysis["functions"].append(second)
        outputs = (
            ut_generator.generate_ut_md(analysis, {}),
            ut_generator.generate_gtest_cpp(analysis),
            ut_generator.generate_unity_c(analysis),
        )
        for output in outputs:
            for function in (1, 2):
                for case in (1, 2):
                    self.assertIn(f"LOCAL_F{function:03d}_UT{case:03d}", output)
        unity = outputs[2]
        self.assertEqual(unity.count("int main(void)"), 1)
        self.assertEqual(unity.count("void setUp(void)"), 1)
        self.assertEqual(unity.count("void tearDown(void)"), 1)
        self.assertEqual(len(re.findall(r"\bRUN_TEST\(", unity)), 4)

    def test_project_prefix_and_existing_function_id_are_preserved(self):
        for existing_id, expected in (("", "MCU_POWER_F001"), ("MCU_EXISTING_F007", "MCU_EXISTING_F007")):
            with self.subTest(existing_id=existing_id):
                analysis = sample_analysis()
                analysis["functions"][0]["function_id"] = existing_id
                outputs = (
                    ut_generator.generate_ut_md(analysis, {}, "MCU_POWER"),
                    ut_generator.generate_gtest_cpp(analysis, "MCU_POWER"),
                    ut_generator.generate_unity_c(analysis, "MCU_POWER"),
                )
                for output in outputs:
                    self.assertIn(f"{expected}_UT001", output)
                    self.assertNotIn("MCU_MCU_", output)

    def test_design_records_unexecuted_state_and_unmeasured_coverage(self):
        result = ut_generator.generate_ut_md(sample_analysis(), {})
        self.assertIn("**Design Status:** DRAFT", result)
        self.assertIn("**Execution Status:** NE", result)
        self.assertIn("未测量", result)
        self.assertIn("TBD (host / SIL / PIL / HIL)", result)
        self.assertIn("Evidence / Defect / Regression", result)
        self.assertNotIn("Static code analysis", result)
        self.assertNotIn("Resource usage evaluation", result)

    def test_goal_preserves_outcomes_without_guessing_retry_result(self):
        conditions = ["while (retry < limit) -> yes", "if (error) -> yes"]
        goal = ut_generator._test_goal_from_conditions(conditions, ["loop", "break", "return"])
        for condition in conditions:
            self.assertIn(condition, goal)
        self.assertNotIn("success", goal)
        self.assertNotIn("exhaust", goal)

    def test_conditions_with_or_do_not_break_markdown_table(self):
        result = ut_generator.generate_ut_md(sample_analysis(), {})
        self.assertIn(r"\|\|", result)
        goal_rows = [line for line in result.splitlines() if line.startswith("| **Test Goal**")]
        self.assertEqual(len(goal_rows), 2)
        for row in goal_rows:
            separators = re.findall(r"(?<!\\)\|", row)
            self.assertEqual(len(separators), 3)

    def test_cli_rejects_analysis_without_functions_without_writing_artifacts(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            base = Path(directory)
            analysis = base / "empty.analysis.json"
            analysis.write_text(json.dumps({"functions": []}), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-B", str(SCRIPTS / "ut_generator.py"), str(analysis)],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("no functions", result.stderr)
            self.assertEqual(list(base.glob("*.ut.*")), [])

    def test_ut_pipeline_does_not_generate_unrequested_dd_png_or_it(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            base = Path(directory)
            source = base / "control.c"
            source.write_text(
                "int control_step(int x) { if (x < 0) return -1; return x; }",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable, "-B", str(SCRIPTS / "code2flowchart.py"), str(source),
                    "--function", "control_step", "--analysis", "--ut", "--validate",
                    "--project-prefix", "MCU_CONTROL", "--out-dir", str(base / "generated"),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            output = base / "generated" / "control_step"
            names = {path.name for path in output.iterdir()}
            self.assertEqual(names, {
                "control_step.drawio", "control_step.analysis.json", "control_step.ut.md",
                "control_step.ut.cpp", "control_step.ut.c",
            })
            cpp = (output / "control_step.ut.cpp").read_text(encoding="utf-8")
            self.assertIn("GTEST_SKIP()", cpp)
            self.assertIn("MCU_CONTROL_F001_UT001", cpp)


if __name__ == "__main__":
    unittest.main()
