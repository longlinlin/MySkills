---
name: code2flowchart
description: Convert C and C++ source code into flowcharts with Mermaid as an intermediate format and draw.io XML as the editable target. Use when Codex needs to turn .c, .h, .cpp, .cc, .cxx, .hpp files or pasted C/C++ functions into .drawio diagrams, SVG/PNG previews, Mermaid .mmd flowcharts, or function branch path reports, especially for teaching, lab, embedded, and procedural code using if/else, for, while, do while, switch/case/default, break, continue, goto labels, return, basic try/catch/throw, task calls, hardware calls, stdio calls, and C++ iostream calls.
---

# code2Flowchart

## Overview

Use this skill to convert C/C++ control flow into visual artifacts:

- Mermaid `.mmd` as a readable intermediate representation.
- draw.io `.drawio` XML for editable diagrams.
- SVG and PNG previews for quick inspection.
- A conversion report with XML validation status, parser notes, and function path counts.
- A `.paths.md` report listing Start-to-End edge-number sequences for each function.
- An `.analysis.json` file for Dify/agent workflows, including function summaries, parameters, return values, output parameters, cyclomatic complexity, calls, in-file callers, branches, path sequences, test-framework options, and unit-test scenario hints.

The bundled converter is intentionally lightweight. It targets readable C/C++ source files and common procedural control flow, not full compiler-grade C or C++ parsing.

## Quick Start

Run the converter directly:

```bash
python code2flowchart/scripts/code2flowchart.py path/to/source.c -o path/to/output
```

For a file named `demo.c`, outputs are:

- `demo.mmd`
- `demo.drawio`
- `demo.svg`
- `demo.png`
- `demo.paths.md`
- `demo.report.md`
- `demo.analysis.json`

When converting pasted code, first write it to a temporary `.c` or `.cpp` file, then run the script.

## Workflow

1. Save or locate the input C/C++ source file.
2. Run `scripts/code2flowchart.py` with an output directory.
3. Read the generated `.report.md`.
4. Use `.analysis.json` as the structured input for downstream Dify/agent prompts.
5. If XML validation is OK, return the `.drawio`, `.svg`, `.png`, `.mmd`, `.paths.md`, and `.analysis.json` paths to the user.
6. If parsing misses important logic, simplify macro-heavy code, expand macros manually, or isolate the target function and rerun.

For retry loops, task dispatchers, cleanup labels, hardware-style calls, or similar procedural C patterns, read `references/c-control-flow-patterns.md` before generating or reviewing diagrams.

For building a Dify workflow or agent around `.analysis.json`, read `references/dify-agent-setup.md`.

## Generation Approach

Use this mental model when maintaining or extending the converter:

1. Tokenize C/C++ source while ignoring comments and preprocessor bodies.
2. Parse function definitions and build a lightweight statement tree. Include common C++ free functions, namespace functions, constructors, and class-scope or `Class::method` member functions when their bodies are visible.
3. Normalize control-flow constructs into graph nodes:
   `Start`, ordinary process, IO, decision, label/goto, return/throw, and `End`.
4. Convert simple jump branches such as `if (...) { break; }` into labeled edges like `yes break` instead of separate boxes. This keeps loop diagrams compact and avoids tangled jump lines.
5. Build edges in execution order and assign monotonically increasing edge numbers.
6. Lay out each function on a dominant vertical spine:
   normal execution goes downward, branch bodies sit left/right, loop-back edges use a left-side channel, and break/goto exits use staggered side channels.
7. Reserve extra vertical space after loops with break exits so jump edges can merge above the next ordinary node.
8. Generate artifacts from the same graph model:
   Mermaid for inspection, draw.io XML for editing, SVG/PNG for preview, `.paths.md` for branch path sequences, and `.analysis.json` for agent-readable analysis.
9. Validate the `.drawio` file as XML and verify it contains `mxGraphModel/root`.

Do not rely on Mermaid layout for final quality. Mermaid is only an intermediate text representation; draw.io XML is the editable target.

## Flowchart Rules

Use these conventions when interpreting or editing the output:

- Start and End use ellipses / terminator shapes.
- Start and End labels should be exactly `Start` and `End`; do not add a separate function-title box above Start.
- Ordinary processing steps use rectangles.
- `if`, `else if`, `for`, `while`, `do while`, and `switch` use diamonds.
- Ordinary statements use rectangles.
- Input/output steps use parallelograms, including `printf`, `scanf`, common stdio calls, and C++ `std::cin` / `std::cout` / `std::cerr` / `std::clog` style statements.
- `return` uses an ellipse and connects to the function End.
- `throw` uses an ellipse and connects to End with a `throw` edge because it leaves the current normal flow.
- `try` uses a process node; each `catch (...)` is a labeled branch from the try node.
- Simple `if (...) { break; }` and `if (...) { continue; }` branches should be rendered as labeled edges such as `yes break`, not as separate statement boxes.
- Standalone or complex `break` / `continue` statements may use highlighted rounded rectangles.
- `goto` uses a distinct highlighted process node and connects directly to its label.
- Labels such as `__end:` use dashed rounded rectangles as merge/cleanup points.
- Every edge label starts with a sequence number. Branch labels are appended, for example `4 yes`, `5 no`, `8 case 1`, or `12 loop`.
- Back edges for loops are routed to the left in draw.io/SVG to reduce overlap.
- `break` and `goto` exit edges are routed through staggered right-side channels so they do not overlap loop-back lines or each other.
- Loops with break exits reserve extra vertical space before the next statement, so break edges can merge above the next node instead of crossing through it.
- Function branch paths are reported as edge-number sequences, for example `1-2-3-5`. Read the generated `.paths.md` file for the full list per function.

For more detail, read `references/flowchart-conventions.md`.

## Supported C/C++ Constructs

The converter currently handles:

- C function definitions.
- Common C++ free functions, namespace functions, constructors, and class member functions with visible bodies.
- Sequential statements and declarations.
- `if`, `else`, and `else if`.
- `for`, `while`, and `do while`.
- `switch`, `case`, and `default`.
- `break`, `continue`, `goto` labels, and `return`.
- Basic C++ `try`, `catch`, and `throw`.
- Common stdio-style calls such as `printf`, `scanf`, `puts`, `getchar`, and `putchar`.
- Common C++ iostream-style statements such as `std::cout << value` and `std::cin >> value`.

## Known Limits

Expect manual review for:

- Heavy macro/preprocessor logic.
- Heavy template metaprogramming and overloaded operator syntax.
- Function pointers and complex declaration syntax.
- Interprocedural call graphs.
- Struct initializers or expressions containing unmatched braces.
- Lambdas and deeply nested class/namespace constructs.
- Compiler extensions.

When exact semantics matter, tell the user this is a visual aid and not a compiler-verified control-flow graph.

## Validation

Always check the generated report. The script parses the `.drawio` file as XML and verifies that it contains `mxGraphModel/root`.

If validation fails, do not present the `.drawio` as complete. Fix the converter or reduce the input and rerun.

## Agent Analysis JSON

Use `.analysis.json` as the stable bridge into Dify or a later test-generation agent.

The first version includes:

- `functions[].description_draft`: deterministic function description seed for LLM refinement.
- `functions[].parameters`: parsed parameter name, type, direction, inferred range, and description draft.
- `functions[].input_parameters`: parameters used as inputs, including input/output pointer or reference parameters.
- `functions[].output_parameters`: pointer, reference, or array-style parameters likely to carry output or input/output data.
- `functions[].return_value`: return type, direction, inferred range, and description draft.
- `functions[].cyclomatic_complexity`: decision-based complexity estimate.
- `functions[].calls`: functions or IO streams called by the function.
- `functions[].called_by_in_file`: callers found among functions parsed in the same input file.
- `functions[].recommended_test_frameworks`: framework IDs suitable for generating unit tests for the function.
- `functions[].branches`: branch points with condition, source line, type, and outcomes.
- `functions[].paths`: Start-to-End edge-number sequences with labels and conditions.
- `functions[].unit_test_scenarios`: one scenario hint per path for branch/unit-test planning.
- `functions[].cfg_edges`: numbered control-flow edges for traceability back to the diagram.
- `test_framework_options`: available test frameworks such as GoogleTest, GoogleTest + FFF/Fake Function Framework, Unity/CMock, Ceedling, Catch2, and doctest.

Treat the JSON as deterministic analysis input. Let the LLM generate polished function descriptions, test-case names, mock setup, and concrete unit-test code from this structure.

Parameter ranges are inferred from type and pointer/reference shape only. Use requirements, comments, comparisons, or caller context to refine ranges before generating final tests.

For Dify integration, treat `.analysis.json` as the boundary between deterministic parsing and LLM generation. Keep code parsing in `code2flowchart.py` or a wrapper API; let Dify handle orchestration, prompt chaining, human review, and final report generation.

## Path Report

Use `.paths.md` when the user needs branch coverage-style path sequences.

- `Branch path count` is the number of complete Start-to-End paths found for that function.
- `Path N` is the numeric edge sequence.
- `Labels` keeps the edge labels, including `yes`, `no`, `case`, `default`, `loop`, `break`, and `return`.
- Loop back edges are expanded at most once per path to avoid infinite paths.
