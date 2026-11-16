#!/usr/bin/env python3
"""从 analysis.json 生成 UT 设计草稿和明确跳过的 GoogleTest/Unity 骨架。

输出 .ut.md、.ut.cpp、.ut.c；真实类型、输入、依赖与断言仍需项目确认。
本脚本不执行 C/C++ 测试，也不测量代码覆盖率。
用法：python ut_generator.py <analysis.json> [--project-prefix SWDD_CHARGE]
"""
import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 只给出待复核的需求分析方法，不按路径序号猜测测试方法。
# ---------------------------------------------------------------------------

DEFAULT_DESIGN_METHOD = "Analysis of requirements (待源码复核与参数用例补充)"
DEFAULT_TEST_METHOD = "Requirement-based test"
DEFAULT_TEST_ENVIRONMENT = "TBD (host / SIL / PIL / HIL)"


def _function_id(function: dict, index: int, project_prefix: str) -> str:
    """让文档与两种骨架共用同一编号，缺少项目编号时使用本地草稿编号。"""
    if function.get("function_id"):
        return function["function_id"]
    prefix = project_prefix or "LOCAL"
    return f"{prefix}_F{index:03d}"


def _markdown_cell(value: str) -> str:
    """避免源码条件中的竖线或换行破坏 Markdown 表格。"""
    return value.replace("|", "\\|").replace("\r\n", "<br>").replace("\n", "<br>")


def _test_goal_from_conditions(conditions: list[str], labels: list[str] | None = None) -> str:
    """保留真实条件及其结果，不把 break 或一次回边推断为成功或重试耗尽。"""
    evidence = conditions or labels or []
    unique_items = []
    for item in evidence:
        if item not in unique_items:
            unique_items.append(item)
    if not unique_items:
        return "核对可见路径的返回值与副作用，具体输入和预期待源码确认。"
    return "核对路径证据：" + "; ".join(unique_items)


def generate_ut_md(analysis: dict, paths_data: dict, project_prefix: str = "") -> str:
    """生成包含未执行状态与证据缺口的 UT 设计文档。"""
    functions = analysis.get("functions", [])
    if not functions:
        return "# Unit Test Design\n\nNo functions found in analysis.\n"

    lines: list[str] = []
    fn_counter = 0

    for fn in functions:
        fn_counter += 1
        name = fn.get("name", "Unknown")
        func_id = _function_id(fn, fn_counter, project_prefix)

        paths = fn.get("paths", [])
        test_frameworks = fn.get("recommended_test_frameworks", [])

        lines.append(f"# Unit Test Design: {name}")
        lines.append("")
        lines.append(f"**Function ID:** `{func_id}`  ")
        lines.append("**Design Status:** DRAFT  ")
        lines.append("**Execution Status:** NE (未执行)  ")
        lines.append(f"**Test Environment:** {DEFAULT_TEST_ENVIRONMENT}  ")
        lines.append(f"**Test Frameworks:** {', '.join(test_frameworks) if test_frameworks else 'GoogleTest + FFF, Unity + CMock'}  ")
        lines.append(f"**Candidate Graph Paths:** {len(paths)}  ")
        lines.append("")
        lines.append("候选路径未经数据流可行性证明，不等于实测分支覆盖率；需按源码补充等价类、边界与故障注入用例。")
        lines.append("")
        lines.append("## 执行与覆盖率证据")
        lines.append("")
        lines.append("| 项目 | 当前记录 |")
        lines.append("| --- | --- |")
        lines.append("| 源码版本、编译宏与需求/设计依据 | TBD |")
        lines.append("| 选中范围、覆盖率目标与统计分母 | TBD |")
        lines.append("| 实测分支覆盖率 | 未测量；不得用候选路径数推算 |")
        lines.append("| 已执行数、通过数、执行率与通过率 | 未执行 / N/A |")
        lines.append("| 构建与运行命令、工具版本、日志及覆盖率报告 | TBD |")
        lines.append("| 失败缺陷与修复后回归范围 | TBD |")
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
            method = DEFAULT_DESIGN_METHOD
            test_method = DEFAULT_TEST_METHOD
            goal = _markdown_cell(_test_goal_from_conditions(conditions, pat_labels))
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
            method = DEFAULT_DESIGN_METHOD
            test_method = DEFAULT_TEST_METHOD
            goal = _markdown_cell(_test_goal_from_conditions(conditions, labels))

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
            lines.append(f"| **Test Environment** | {DEFAULT_TEST_ENVIRONMENT} |")
            lines.append(f"| **Test Goal** | {goal} |")
            lines.append("| **Requirement / Source Reference** | TBD：需求、源码位置与当前图版本 |")
            lines.append("| **Input / Dependency Setup** | TBD：具体参数、全局状态、真实签名与 mock 返回序列 |")
            lines.append(f"| **Precondition** | (To be filled by review: set up mocks, initial state) |")
            lines.append(f"| **Action** | Call `{name}()` with appropriate arguments |")
            lines.append(f"| **Expected Result** | (To be filled by review: assert expected behavior) |")
            lines.append(f"| **Post-condition** | (To be filled by review: verify final state) |")
            lines.append(f"| **Actual Result** | (To be filled after test execution) |")
            lines.append("| **Execution Status** | NE |")
            lines.append("| **Evidence / Defect / Regression** | TBD：命令、日志、覆盖率、缺陷与回归记录 |")
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
    GTEST_SKIP() << "DRAFT: implement real inputs, call and assertions first";

    // 准备：根据真实声明和当前状态配置依赖。
{fake_mocks}
    // 执行：补入 {fn_name} 的真实调用与具体参数。

    // 断言：补入具体预期值和副作用后，才能移除跳过保护。
}}
"""


def _gtest_suite_name(fn_name: str) -> str:
    """Derive a GoogleTest suite name from function name."""
    # Convert snake_case to CamelCase
    parts = fn_name.split("_")
    return "".join(p.capitalize() for p in parts) + "Test"


def generate_gtest_cpp(analysis: dict, project_prefix: str = "") -> str:
    """生成明确跳过的 GoogleTest 草稿，不猜测外部函数签名或 mock 框架接口。"""
    functions = analysis.get("functions", [])
    if not functions:
        return "// No functions in analysis.\n"

    source = analysis.get("source", "")
    lines: list[str] = [
        "// 自动生成的单元测试草稿，尚未验证编译或执行。",
        f"// 源码：{source}",
        "// 生成器：code2flowchart ut_generator.py",
        "//",
        "// 按项目真实声明添加被测函数头文件与所需的 FFF 或 gMock 配置。",
        "// 补齐输入、依赖、真实调用和断言后再移除 GTEST_SKIP。",
        "// 跳过用例不能计入执行通过率或覆盖率。",
        "",
        '#include <gtest/gtest.h>',
        "",
    ]

    fn_counter = 0
    for fn in functions:
        fn_counter += 1
        name = fn.get("name", "Unknown")
        func_id = _function_id(fn, fn_counter, project_prefix)

        suite = _gtest_suite_name(name)
        calls = fn.get("calls", [])
        paths = fn.get("paths", [])

        lines.append(f"// ============================================================")
        lines.append(f"// Function: {name}")
        lines.append(f"// Function ID: {func_id}")
        lines.append(f"// ============================================================")
        lines.append("")

        # 缺少真实声明时只列依赖，避免生成错误类型与参数列表。
        if calls:
            lines.append("// 待确认的外部依赖：")
            for call in calls:
                lines.append(f"// {call}：核对头文件、隔离边界及参数/返回值类型。")
            lines.append("")

        lines.append(f"class {suite} : public ::testing::Test")
        lines.append("{")
        lines.append("protected:")
        lines.append("    void SetUp() override {")
        lines.append("        // TODO: 初始化本用例的全局状态，并复位已配置的全部替身。")
        lines.append("    }")
        lines.append("")
        lines.append("    void TearDown() override {")
        lines.append("        // TODO: 释放资源，恢复共享状态。")
        lines.append("    }")
        lines.append("};")
        lines.append("")

        # Test cases per path
        for i, path in enumerate(paths):
            tc_id = f"{func_id}_UT{i+1:03d}"
            seq = path.get("edge_sequence_text", "")
            conditions = path.get("conditions", [])
            pat_labels = path.get("labels", [])
            method = DEFAULT_DESIGN_METHOD
            test_method = DEFAULT_TEST_METHOD
            goal = _test_goal_from_conditions(conditions, pat_labels)

            lines.append(
                G_TEST_TEMPLATE.format(
                    tc_id=tc_id,
                    func_id=func_id,
                    fn_name=name,
                    sequence=seq,
                    design_method=method,
                    test_env=DEFAULT_TEST_ENVIRONMENT,
                    test_method=test_method,
                    test_goal=goal,
                    suite_name=suite,
                    fake_mocks="    // TODO: 按用例设置参数、返回序列、调用次数和有依据的顺序。",
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
    TEST_IGNORE_MESSAGE("DRAFT: implement real inputs, call and assertions first");

    // 准备：按本用例配置实际依赖。
{cmock_expects}
    // 执行：补入 {fn_name} 的真实调用与具体参数。

    // 断言：补入具体预期值和副作用后，才能移除忽略保护。
}}
"""


def generate_unity_c(analysis: dict, project_prefix: str = "") -> str:
    """生成明确忽略的 Unity 草稿，CMock 配置须依据项目真实声明补充。"""
    functions = analysis.get("functions", [])
    if not functions:
        return "// No functions in analysis.\n"

    source = analysis.get("source", "")
    lines: list[str] = [
        "/* 自动生成的单元测试草稿，尚未验证编译或执行。",
        f" * 源码：{source}",
        " * 生成器：code2flowchart ut_generator.py",
        " *",
        " * 按项目真实声明添加被测函数头文件与 CMock 生成的 mock 头文件。",
        " * 补齐输入、依赖、真实调用和断言后再移除 TEST_IGNORE_MESSAGE。",
        " * 被忽略用例不能计入执行通过率或覆盖率。",
        " */",
        "",
        '#include "unity.h"',
        "",
        "void setUp(void)",
        "{",
        "    /* TODO: 复位全局状态并初始化全部替身。 */",
        "}",
        "",
        "void tearDown(void)",
        "{",
        "    /* TODO: 释放资源并恢复共享状态。 */",
        "}",
        "",
    ]

    test_ids: list[str] = []
    fn_counter = 0
    for fn in functions:
        fn_counter += 1
        name = fn.get("name", "Unknown")
        func_id = _function_id(fn, fn_counter, project_prefix)

        calls = fn.get("calls", [])
        paths = fn.get("paths", [])

        lines.append(f"/* ============================================================")
        lines.append(f" * Function: {name}")
        lines.append(f" * Function ID: {func_id}")
        lines.append(f" * ============================================================ */")
        lines.append("")

        # Test cases
        for i, path in enumerate(paths):
            tc_id = f"{func_id}_UT{i+1:03d}"
            test_ids.append(tc_id)
            seq = path.get("edge_sequence_text", "")
            conditions = path.get("conditions", [])
            pat_labels = path.get("labels", [])
            method = DEFAULT_DESIGN_METHOD
            test_method = DEFAULT_TEST_METHOD
            goal = _test_goal_from_conditions(conditions, pat_labels)

            cmock_expects = ""
            if calls:
                for call in calls:
                    cmock_expects += f"    /* TODO: 按 {call} 的真实签名设置预期与返回序列。 */\n"

            lines.append(
                UNITY_TEMPLATE.format(
                    tc_id=tc_id,
                    func_id=func_id,
                    fn_name=name,
                    sequence=seq,
                    design_method=method,
                    test_env=DEFAULT_TEST_ENVIRONMENT,
                    test_method=test_method,
                    test_goal=goal,
                    cmock_expects=cmock_expects or "    /* 核对是否有未显式解析的外部依赖。 */",
                )
            )
            lines.append("")

    # 同一文件仅生成一个 runner，避免多函数输入时重复定义入口与夹具。
    lines.append("int main(void)")
    lines.append("{")
    lines.append("    UNITY_BEGIN();")
    for tc_id in test_ids:
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

    if not analysis.get("functions"):
        sys.exit("error: no functions found in analysis.json; no UT artifacts were generated")

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
