#!/usr/bin/env python3
"""Generate Unit Test (UT) design document and skeleton test code from analysis.json.

Reads the structured analysis + path data and produces:
  - <function>.ut.md   — test case design document
  - <function>.ut.cpp  — GoogleTest + FFF skeleton
  - <function>.ut.c    — Unity + CMock skeleton

Usage: python ut_generator.py <analysis.json> [--project-prefix SWDD_CHARGE]
"""
import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Design method heuristics — assigned per path based on path characteristics
# ---------------------------------------------------------------------------

DESIGN_METHODS = [
    "Equivalence Classes",
    "Boundary Values",
    "Error Guessing",
    "Analysis of requirements",
]

TEST_METHODS = [
    "Requirement-based test",
    "Walk-through",
    "Static code analysis",
    "Fault injection test",
    "Resource usage evaluation",
]

TEST_ENVIRONMENTS = [
    "software-in-the-loop",
    "model-in-the-loop",
    "processor-in-the-loop",
    "hardware-in-the-loop",
]


def _pick_design_method(path_idx: int, total: int, conditions: list[str]) -> str:
    """Assign a design method based on path position and conditions."""
    cond_text = " ".join(conditions).lower()
    if "break" in cond_text or "return" in cond_text:
        return "Error Guessing"
    if path_idx == 1:
        return "Equivalence Classes"
    if path_idx == total:
        return "Boundary Values"
    if "loop" in cond_text or "retry" in cond_text:
        return "Analysis of requirements"
    return DESIGN_METHODS[path_idx % len(DESIGN_METHODS)]


def _pick_test_method(path_idx: int) -> str:
    return TEST_METHODS[path_idx % len(TEST_METHODS)]


def _test_goal_from_conditions(conditions: list[str], labels: list[str] | None = None) -> str:
    """Generate a test goal from path conditions and edge labels."""
    if not conditions:
        return "Verify function behavior for this path."

    # Analyze labels for key path characteristics
    label_str = " ".join(labels) if labels else ""
    has_loop = "loop" in label_str
    has_break = "break" in label_str
    has_return = "return" in label_str

    # Build a concise description from unique conditions
    key_conditions = []
    for c in conditions:
        # Extract the decision description (before the arrow)
        if chr(8594) in c:
            decision = c.split(chr(8594))[0].strip()
        elif "->" in c:
            decision = c.split("->")[0].strip()
        else:
            decision = c[:60].strip()
        # Skip duplicate decisions
        if decision not in key_conditions:
            key_conditions.append(decision)

    if has_break and has_loop:
        return f"Verify retry-and-break path: {key_conditions[0] if key_conditions else 'loop with break'}"
    if has_break:
        return f"Verify immediate success path (break on first attempt): {key_conditions[0] if key_conditions else ''}"
    if has_loop:
        return f"Verify retry exhaust path (loop exits after max retries)"
    if has_return:
        return f"Verify early return path: {key_conditions[0] if key_conditions else ''}"
    return f"Verify path: {key_conditions[0][:80] if key_conditions else 'all branches'}"


def generate_ut_md(analysis: dict, paths_data: dict, project_prefix: str = "") -> str:
    """Generate UT design document markdown."""
    functions = analysis.get("functions", [])
    if not functions:
        return "# Unit Test Design\n\nNo functions found in analysis.\n"

    lines: list[str] = []
    fn_counter = 0

    for fn in functions:
        fn_counter += 1
        name = fn.get("name", "Unknown")
        fe = fn.get("function_evaluation", {})
        func_id = fn.get("function_id", "")
        if not func_id and project_prefix:
            func_id = f"{project_prefix}_F{fn_counter:03d}"

        paths = fn.get("paths", [])
        branches = fn.get("branches", [])
        test_frameworks = fn.get("recommended_test_frameworks", [])

        lines.append(f"# Unit Test Design: {name}")
        lines.append("")
        lines.append(f"**Function ID:** `{func_id}`  ")
        lines.append(f"**Test Environment:** {TEST_ENVIRONMENTS[0]}  ")
        lines.append(f"**Test Frameworks:** {', '.join(test_frameworks) if test_frameworks else 'GoogleTest + FFF, Unity + CMock'}  ")
        lines.append(f"**Branch Paths:** {len(paths)}  ")
        lines.append("")

        # Summary table
        lines.append("## Test Case Overview")
        lines.append("")
        lines.append("| # | Test Case ID | Sequence | Design Method | Test Method | Goal |")
        lines.append("|---|-------------|----------|---------------|-------------|------|")
        for i, path in enumerate(paths):
            tc_id = f"{func_id}_UT{i+1:03d}"
            seq = path.get("edge_sequence_text", "")
            conditions = path.get("conditions", [])
            pat_labels = path.get("labels", [])
            method = _pick_design_method(i + 1, len(paths), conditions)
            test_method = _pick_test_method(i + 1)
            goal = _test_goal_from_conditions(conditions, pat_labels)[:80]
            lines.append(f"| {i+1} | `{tc_id}` | `{seq}` | {method} | {test_method} | {goal} |")
        lines.append("")

        # Detailed test cases
        lines.append("## Detailed Test Cases")
        lines.append("")
        for i, path in enumerate(paths):
            tc_id = f"{func_id}_UT{i+1:03d}"
            seq = path.get("edge_sequence_text", "")
            conditions = path.get("conditions", [])
            labels = path.get("labels", [])
            method = _pick_design_method(i + 1, len(paths), conditions)
            test_method = _pick_test_method(i + 1)
            goal = _test_goal_from_conditions(conditions, labels)

            lines.append(f"### UT{i+1:03d}: `{tc_id}`")
            lines.append("")
            lines.append("| Field | Value |")
            lines.append("|-------|-------|")
            lines.append(f"| **Test Case ID** | `{tc_id}` |")
            lines.append(f"| **Function ID** | `{func_id}` |")
            lines.append(f"| **Function Name** | `{name}` |")
            lines.append(f"| **Sequence** | `{seq}` |")
            lines.append(f"| **Case Design Method** | {method} |")
            lines.append(f"| **Test Method** | {test_method} |")
            lines.append(f"| **Test Environment** | {TEST_ENVIRONMENTS[0]} |")
            lines.append(f"| **Test Goal** | {goal} |")
            lines.append(f"| **Precondition** | (To be filled by review: set up mocks, initial state) |")
            lines.append(f"| **Action** | Call `{name}()` with appropriate arguments |")
            lines.append(f"| **Expected Result** | (To be filled by review: assert expected behavior) |")
            lines.append(f"| **Post-condition** | (To be filled by review: verify final state) |")
            lines.append(f"| **Actual Result** | (To be filled after test execution) |")
            lines.append("")

            # Edge sequence detail
            if labels:
                lines.append("**Edge sequence detail:**")
                lines.append("")
                for lbl in labels:
                    lines.append(f"- {lbl}")
                lines.append("")

        if len(functions) > 1:
            lines.append("---")
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GoogleTest + FFF code generation
# ---------------------------------------------------------------------------

G_TEST_TEMPLATE = """/**
 * @Test Case ID: {tc_id}
 * @Function ID: {func_id}
 * @Function Name: {fn_name}
 * @Sequence: {sequence}
 * @Case Design Method: {design_method}
 * @Test Environment: {test_env}
 * @Test Method: {test_method}
 * @Test Goal: {test_goal}
 * @Precondition: (To be filled)
 * @Action: Call {fn_name}()
 * @Expected Result: (To be filled)
 * @Post-condition: (To be filled)
 */
TEST_F({suite_name}, {tc_id})
{{
    // Arrange
{fake_mocks}
    // Act
    // TODO: Call {fn_name}() with appropriate arguments

    // Assert
    // TODO: Add EXPECT_* / ASSERT_* checks
}}
"""


def _gtest_suite_name(fn_name: str) -> str:
    """Derive a GoogleTest suite name from function name."""
    # Convert snake_case to CamelCase
    parts = fn_name.split("_")
    return "".join(p.capitalize() for p in parts) + "Test"


def _gtest_fake_mocks(calls: list[str]) -> str:
    """Generate FSF_MOCK declarations for external calls."""
    lines = []
    for call in calls:
        lines.append(f"    FSF_MOCK({call});")
        lines.append(f"    EXPECT_CALL(FSF_MOCK_OBJ({call}), {call}(_)).Times(0);")
    return "\n".join(lines) if lines else "    // No external calls to mock"


def generate_gtest_cpp(analysis: dict, project_prefix: str = "") -> str:
    """Generate GoogleTest + FFF skeleton C++ code."""
    functions = analysis.get("functions", [])
    if not functions:
        return "// No functions in analysis.\n"

    source = analysis.get("source", "")
    lines: list[str] = [
        "// Auto-generated GoogleTest + FFF unit test skeleton",
        f"// Source: {source}",
        "// Generated by: code2flowchart ut_generator.py",
        "//",
        "// TODO:",
        "//   - Fill Arrange sections with mock expectations and test data",
        "//   - Fill Act sections with the actual function call",
        "//   - Fill Assert sections with EXPECT_*/ASSERT_* checks",
        "//   - Review and adjust test goals, pre/post conditions",
        "",
        '#include <gtest/gtest.h>',
        '#include "fff.h"',
        "",
    ]

    fn_counter = 0
    for fn in functions:
        fn_counter += 1
        name = fn.get("name", "Unknown")
        func_id = fn.get("function_id", "")
        if not func_id and project_prefix:
            func_id = f"{project_prefix}_F{fn_counter:03d}"

        suite = _gtest_suite_name(name)
        calls = fn.get("calls", [])
        paths = fn.get("paths", [])

        lines.append(f"// ============================================================")
        lines.append(f"// Function: {name}")
        lines.append(f"// Function ID: {func_id}")
        lines.append(f"// ============================================================")
        lines.append("")

        # DEFINE_FFF_GLOBALS and mocks
        if calls:
            lines.append("// --- Mocks ---")
            for call in calls:
                lines.append(f"FAKE_VALUE_FUNC(LPI2C_Status_t, {call}, U8, U8, U8*, U16, U8, U32);")
            lines.append("")

        lines.append(f"class {suite} : public ::testing::Test")
        lines.append("{")
        lines.append("protected:")
        lines.append("    void SetUp() override {")
        if calls:
            for call in calls:
                lines.append(f"        FFF_RESET_HISTORY();")
            lines.append(f"        RESET_FAKE({calls[0]});")
        lines.append("        // TODO: Initialize test fixtures")
        lines.append("    }")
        lines.append("")
        lines.append("    void TearDown() override {")
        lines.append("        // TODO: Clean up test fixtures")
        lines.append("    }")
        lines.append("};")
        lines.append("")

        # Test cases per path
        for i, path in enumerate(paths):
            tc_id = f"{func_id}_UT{i+1:03d}"
            seq = path.get("edge_sequence_text", "")
            conditions = path.get("conditions", [])
            pat_labels = path.get("labels", [])
            method = _pick_design_method(i + 1, len(paths), conditions)
            test_method = _pick_test_method(i + 1)
            goal = _test_goal_from_conditions(conditions, pat_labels)

            lines.append(
                G_TEST_TEMPLATE.format(
                    tc_id=tc_id,
                    func_id=func_id,
                    fn_name=name,
                    sequence=seq,
                    design_method=method,
                    test_env=TEST_ENVIRONMENTS[0],
                    test_method=test_method,
                    test_goal=goal,
                    suite_name=suite,
                    fake_mocks="    // TODO: Set up mock expectations",
                )
            )
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Unity + CMock code generation
# ---------------------------------------------------------------------------

UNITY_TEMPLATE = """/**
 * @Test Case ID: {tc_id}
 * @Function ID: {func_id}
 * @Function Name: {fn_name}
 * @Sequence: {sequence}
 * @Case Design Method: {design_method}
 * @Test Environment: {test_env}
 * @Test Method: {test_method}
 * @Test Goal: {test_goal}
 * @Precondition: (To be filled)
 * @Action: Call {fn_name}()
 * @Expected Result: (To be filled)
 * @Post-condition: (To be filled)
 */
void test_{tc_id}(void)
{{
    // Arrange
{cmock_expects}
    // Act
    // TODO: Call {fn_name}() with appropriate arguments

    // Assert
    // TODO: Add TEST_ASSERT_* checks
}}
"""


def generate_unity_c(analysis: dict, project_prefix: str = "") -> str:
    """Generate Unity + CMock skeleton C code."""
    functions = analysis.get("functions", [])
    if not functions:
        return "// No functions in analysis.\n"

    source = analysis.get("source", "")
    lines: list[str] = [
        "/* Auto-generated Unity + CMock unit test skeleton",
        f" * Source: {source}",
        " * Generated by: code2flowchart ut_generator.py",
        " *",
        " * TODO:",
        " *   - Fill Arrange sections with mock expectations and test data",
        " *   - Fill Act sections with the actual function call",
        " *   - Fill Assert sections with TEST_ASSERT_* checks",
        " *   - Review and adjust test goals, pre/post conditions",
        " */",
        "",
        '#include "unity.h"',
        '#include "cmock.h"',
        "",
    ]

    fn_counter = 0
    for fn in functions:
        fn_counter += 1
        name = fn.get("name", "Unknown")
        func_id = fn.get("function_id", "")
        if not func_id and project_prefix:
            func_id = f"{project_prefix}_F{fn_counter:03d}"

        calls = fn.get("calls", [])
        paths = fn.get("paths", [])

        lines.append(f"/* ============================================================")
        lines.append(f" * Function: {name}")
        lines.append(f" * Function ID: {func_id}")
        lines.append(f" * ============================================================ */")
        lines.append("")

        # setUp/tearDown
        lines.append("void setUp(void)")
        lines.append("{")
        lines.append("    /* TODO: Initialize test fixtures */")
        lines.append("}")
        lines.append("")
        lines.append("void tearDown(void)")
        lines.append("{")
        lines.append("    /* TODO: Clean up test fixtures */")
        lines.append("}")
        lines.append("")

        # Test cases
        for i, path in enumerate(paths):
            tc_id = f"{func_id}_UT{i+1:03d}"
            seq = path.get("edge_sequence_text", "")
            conditions = path.get("conditions", [])
            pat_labels = path.get("labels", [])
            method = _pick_design_method(i + 1, len(paths), conditions)
            test_method = _pick_test_method(i + 1)
            goal = _test_goal_from_conditions(conditions, pat_labels)

            cmock_expects = ""
            if calls:
                for call in calls:
                    cmock_expects += f"    {call}_IgnoreAndReturn(LPI2C_STATUS_OK);\n"

            lines.append(
                UNITY_TEMPLATE.format(
                    tc_id=tc_id,
                    func_id=func_id,
                    fn_name=name,
                    sequence=seq,
                    design_method=method,
                    test_env=TEST_ENVIRONMENTS[0],
                    test_method=test_method,
                    test_goal=goal,
                    cmock_expects=cmock_expects or "    /* No external calls to mock */",
                )
            )
            lines.append("")

        # Main runner
        lines.append("int main(void)")
        lines.append("{")
        lines.append("    UNITY_BEGIN();")
        for i in range(len(paths)):
            tc_id = f"{func_id}_UT{i+1:03d}"
            lines.append(f"    RUN_TEST(test_{tc_id});")
        lines.append("    return UNITY_END();")
        lines.append("}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Generate Unit Test design (.ut.md) and test code from analysis.json"
    )
    ap.add_argument("analysis_json", type=Path, help="Path to analysis.json produced by code2flowchart.py")
    ap.add_argument("--project-prefix", default="",
                    help="Function ID prefix, e.g. SWDD_CHARGE (sets function_id)")
    ap.add_argument("-o", "--output-dir", type=Path, default=None,
                    help="Output directory for .ut.md/.ut.cpp/.ut.c (default: alongside analysis.json)")
    args = ap.parse_args()

    analysis_path: Path = args.analysis_json
    if not analysis_path.exists():
        sys.exit(f"error: analysis.json not found: {analysis_path}")

    with open(analysis_path, encoding="utf-8") as f:
        analysis = json.load(f)

    # Also try to read paths.md for rich path data
    paths_path = analysis_path.with_suffix(".paths.md")
    paths_data: dict = {}
    if paths_path.exists():
        pass  # paths data is already embedded in analysis.json

    prefix = args.project_prefix
    fn_name = analysis.get("functions", [{}])[0].get("name", analysis_path.stem.split(".")[0])

    def _out_path(suffix: str) -> Path:
        if args.output_dir:
            p = args.output_dir / f"{fn_name}{suffix}"
        else:
            p = analysis_path.parent / f"{fn_name}{suffix}"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    # Generate .ut.md
    ut_md = generate_ut_md(analysis, paths_data, prefix)
    ut_md_path = _out_path(".ut.md")
    ut_md_path.write_text(ut_md, encoding="utf-8")
    print(f"ut.md: {ut_md_path}")

    # Generate .ut.cpp (GoogleTest)
    cpp_code = generate_gtest_cpp(analysis, prefix)
    cpp_path = _out_path(".ut.cpp")
    cpp_path.write_text(cpp_code, encoding="utf-8")
    print(f"ut.cpp: {cpp_path}")

    # Generate .ut.c (Unity + CMock)
    c_code = generate_unity_c(analysis, prefix)
    c_path = _out_path(".ut.c")
    c_path.write_text(c_code, encoding="utf-8")
    print(f"ut.c: {c_path}")


if __name__ == "__main__":
    main()
