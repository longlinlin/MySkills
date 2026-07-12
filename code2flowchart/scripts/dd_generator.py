#!/usr/bin/env python3
"""Generate Detailed Design (DD) markdown document from analysis.json.

Reads the structured analysis produced by code2flowchart.py and writes a
DD document following automotive/embedded software engineering conventions.

Usage: python dd_generator.py <analysis.json> [--project-prefix SWDD_CHARGE]
"""
import argparse
import json
import sys
from pathlib import Path


def _param_direction(param: dict) -> str:
    d = param.get("direction", "")
    if d == "input":
        return "IN"
    if d == "output":
        return "OUT"
    if d == "input_output":
        return "IN/OUT"
    return d.upper()


def _param_default(param: dict) -> str:
    if param.get("is_pointer"):
        return "NULL"
    return "N/A"


def _param_range(param: dict) -> str:
    t = param.get("type", "")
    if "U8" in t or "uint8" in t.lower():
        return "0x00–0xFF"
    if "U16" in t or "uint16" in t.lower():
        return "0x0000–0xFFFF"
    if "U32" in t or "uint32" in t.lower():
        return "0x00000000–0xFFFFFFFF"
    if "S8" in t or "int8" in t.lower():
        return "-128–127"
    if "S16" in t or "int16" in t.lower():
        return "-32768–32767"
    if "S32" in t or "int32" in t.lower():
        return "-2^31–2^31-1"
    if param.get("is_pointer"):
        return "Valid pointer or NULL"
    return "(see type limits)"


def _param_description(param: dict, fn_name: str) -> str:
    """Generate a concise parameter description from available data."""
    name = param.get("name", "")
    t = param.get("type", "")
    direction = _param_direction(param)
    parts = [f"{direction} parameter `{name}` of type `{t}`"]
    if param.get("is_pointer"):
        parts.append("(pointer)")
    if param.get("is_const"):
        parts.append("(const)")
    if param.get("is_reference"):
        parts.append("(reference)")
    return ". ".join(parts) + "."


def generate_dd(analysis: dict, project_prefix: str = "") -> str:
    """Generate DD markdown from analysis data."""
    functions = analysis.get("functions", [])
    if not functions:
        return "# Detailed Design\n\nNo functions found in analysis.\n"

    source_path = analysis.get("source", "")
    lines: list[str] = []
    fn_counter = 0

    for fn in functions:
        fn_counter += 1
        fe = fn.get("function_evaluation", {})
        func_id = fn.get("function_id", "")
        if not func_id and project_prefix:
            func_id = f"{project_prefix}_F{fn_counter:03d}"
            fn["function_id"] = func_id

        name = fn.get("name", "Unknown")
        signature = fn.get("signature", "")
        desc = fn.get("description_draft", "")
        constraint = fn.get("constraint", "(To be filled by review)")
        verification = fn.get("verification_criteria", "(To be filled by review)")
        called_by = fn.get("called_by_in_file", [])
        calls = fn.get("calls", [])
        cc = fe.get("cyclomatic_complexity", fn.get("cyclomatic_complexity", 0))
        level = fe.get("complexity_level", "")
        branch_num = fe.get("branch_num", 0)
        interactivity = fe.get("interactivity", 0)
        criticality = fe.get("criticality", 0)
        calls_detail = fe.get("calls_detail", [])
        params = fn.get("parameters", [])
        return_val = fn.get("return_value", {})
        artifacts = analysis.get("artifacts", {})
        png_path = artifacts.get("png", "")
        drawio_path = artifacts.get("drawio", "")

        # --- DD Document ---
        lines.append(f"# Detailed Design: {name}")
        lines.append("")
        lines.append("| Field | Value |")
        lines.append("|-------|-------|")
        lines.append(f"| **Function ID** | `{func_id}` |")
        lines.append(f"| **Function Declaration** | `{signature}` |")
        lines.append(f"| **Source File** | `{source_path}` |")
        lines.append("")
        lines.append("## Description")
        lines.append("")
        lines.append(desc)
        lines.append("")
        lines.append("## Constraint")
        lines.append("")
        lines.append(constraint)
        lines.append("")
        lines.append("## Verification Criteria")
        lines.append("")
        lines.append(verification)
        lines.append("")

        # Parameter Table
        if params:
            lines.append("## Parameter / Returned Value")
            lines.append("")
            lines.append("| Name | I/O | Type | Range | Default | Description |")
            lines.append("|------|-----|------|-------|---------|-------------|")
            for p in params:
                io = _param_direction(p)
                t = p.get("type", "")
                rng = _param_range(p)
                default = _param_default(p)
                pdesc = _param_description(p, name)
                lines.append(f"| `{p['name']}` | {io} | `{t}` | {rng} | {default} | {pdesc} |")
            # Return value
            if return_val and return_val.get("type"):
                rt = return_val.get("type", "void")
                lines.append(f"| *(return)* | OUT | `{rt}` | (see type limits) | N/A | Returns `{rt}`. |")
            lines.append("")

        # Called By / Callings
        lines.append("## Called By")
        lines.append("")
        if called_by:
            for cb in called_by:
                lines.append(f"- `{cb}()`")
        else:
            lines.append("- (none detected in project — the agent should perform cross-file grep search)")
        lines.append("")

        lines.append("## Callings")
        lines.append("")
        if calls:
            for c in calls:
                lines.append(f"- `{c}()`")
        else:
            lines.append("- None")
        lines.append("")

        # Function Evaluation
        lines.append("## Function Evaluation")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Branch Num | {branch_num} |")
        lines.append(f"| Cyclomatic Complexity | {cc} ({level}) |")
        lines.append(f"| Interactivity | {interactivity} |")
        lines.append(f"| Criticality | {criticality} |")
        lines.append("")
        if calls_detail:
            lines.append("**Call Detail (non-deduplicated):**")
            lines.append("")
            for cd in calls_detail:
                lines.append(f"- `{cd['name']}()` called {cd['count']} time(s)")
            lines.append("")

        # Remark
        lines.append("## Remark")
        lines.append("")
        lines.append(f"- **Criticality:** {criticality} (called by {criticality} other function(s) in file).")
        interact_msg = f"calls {interactivity} function(s)" if interactivity > 0 else "no external calls"
        lines.append(f"- **Interactivity:** {interactivity} ({interact_msg}).")
        lines.append(f"- **Cyclomatic Complexity:** {cc} ({level}). N = decision_nodes + 1 = {branch_num} + 1 = {cc}.")
        lines.append(f"- **Branch Num:** {branch_num} decision node(s) (diamond shapes in flowchart).")
        lines.append("")

        # Flowchart
        if png_path or drawio_path:
            lines.append("## Flowchart")
            lines.append("")
            if png_path:
                lines.append(f"![{name} flowchart]({png_path})")
                lines.append("")
            lines.append(f"Editable diagram: `{drawio_path}`")
            lines.append("")

        # Divider between functions
        if len(functions) > 1:
            lines.append("---")
            lines.append("")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Generate Detailed Design (.dd.md) from analysis.json")
    ap.add_argument("analysis_json", type=Path, help="Path to analysis.json produced by code2flowchart.py")
    ap.add_argument("--project-prefix", default="",
                    help="Function ID prefix, e.g. SWDD_CHARGE (sets function_id)")
    ap.add_argument("-o", "--output", type=Path, default=None,
                    help="Output .dd.md path (default: alongside analysis.json)")
    args = ap.parse_args()

    analysis_path: Path = args.analysis_json
    if not analysis_path.exists():
        sys.exit(f"error: analysis.json not found: {analysis_path}")

    with open(analysis_path, encoding="utf-8") as f:
        analysis = json.load(f)

    dd_md = generate_dd(analysis, args.project_prefix)

    # Use function name for output, not analysis file stem
    fn_name = analysis.get("functions", [{}])[0].get("name", analysis_path.stem.split(".")[0])
    out_dir = args.output or analysis_path.parent
    if out_dir.is_dir():
        out_path = out_dir / f"{fn_name}.dd.md"
    else:
        out_path = out_dir
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(dd_md, encoding="utf-8")
    print(f"dd: {out_path}")


if __name__ == "__main__":
    main()
