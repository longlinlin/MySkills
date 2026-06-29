---
name: code2drawio
description: Convert C source code into flowcharts with Mermaid as an intermediate format and draw.io XML as the editable target. Use when Codex needs to turn .c files or pasted C functions into .drawio diagrams, SVG/PNG previews, Mermaid .mmd flowcharts, or function branch path reports, especially for teaching/lab-style and STM32-style code using if/else, for, while, do while, switch/case/default, break, continue, goto labels, return, task calls, hardware calls, and common stdio calls.
---

# code2drawio

## Overview

Use this skill to convert C control flow into visual artifacts:

- Mermaid `.mmd` as a readable intermediate representation.
- draw.io `.drawio` XML for editable diagrams.
- SVG and PNG previews for quick inspection.
- A conversion report with XML validation status, parser notes, and function path counts.
- A `.paths.md` report listing Start-to-End edge-number sequences for each function.

The bundled converter is intentionally lightweight. It targets readable C source files and common procedural control flow, not full compiler-grade C parsing.

## Quick Start

Run the converter directly:

```bash
python code2drawio/scripts/code2drawio.py path/to/source.c -o path/to/output
```

For a file named `demo.c`, outputs are:

- `demo.mmd`
- `demo.drawio`
- `demo.svg`
- `demo.png`
- `demo.paths.md`
- `demo.report.md`

When converting pasted code, first write it to a temporary `.c` file, then run the script.

## Workflow

1. Save or locate the input C source file.
2. Run `scripts/code2drawio.py` with an output directory.
3. Read the generated `.report.md`.
4. If XML validation is OK, return the `.drawio`, `.svg`, `.png`, and `.mmd` paths to the user.
5. If parsing misses important logic, simplify macro-heavy code, expand macros manually, or isolate the target function and rerun.

For STM32 test-task code modeled after `D:/STM32/spa5000_old/Src/app/test.c`, read `references/stm32-test-patterns.md` before generating or reviewing diagrams.

## Generation Approach

Use this mental model when maintaining or extending the converter:

1. Tokenize C source while ignoring comments and preprocessor bodies.
2. Parse top-level function definitions and build a lightweight statement tree.
3. Normalize control-flow constructs into graph nodes:
   `Start`, ordinary process, IO, decision, label/goto, return, and `End`.
4. Convert simple jump branches such as `if (...) { break; }` into labeled edges like `yes break` instead of separate boxes. This keeps loop diagrams compact and avoids tangled jump lines.
5. Build edges in execution order and assign monotonically increasing edge numbers.
6. Lay out each function on a dominant vertical spine:
   normal execution goes downward, branch bodies sit left/right, loop-back edges use a left-side channel, and break/goto exits use staggered side channels.
7. Reserve extra vertical space after loops with break exits so jump edges can merge above the next ordinary node.
8. Generate artifacts from the same graph model:
   Mermaid for inspection, draw.io XML for editing, SVG/PNG for preview, and `.paths.md` for branch path sequences.
9. Validate the `.drawio` file as XML and verify it contains `mxGraphModel/root`.

Do not rely on Mermaid layout for final quality. Mermaid is only an intermediate text representation; draw.io XML is the editable target.

## Flowchart Rules

Use these conventions when interpreting or editing the output:

- Start and End use ellipses.
- Start and End labels should be exactly `Start` and `End`; do not add a separate function-title box above Start.
- `if`, `for`, `while`, `do while`, and `switch` use diamonds.
- Ordinary statements use rectangles.
- `printf`, `scanf`, and common stdio calls use parallelograms.
- `return` uses an ellipse and connects to the function End.
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

## Supported C Constructs

The converter currently handles:

- Function definitions.
- Sequential statements and declarations.
- `if`, `else`, and `else if`.
- `for`, `while`, and `do while`.
- `switch`, `case`, and `default`.
- `break`, `continue`, `goto` labels, and `return`.
- Common stdio-style calls such as `printf`, `scanf`, `puts`, `getchar`, and `putchar`.

## Known Limits

Expect manual review for:

- Heavy macro/preprocessor logic.
- Function pointers and complex declaration syntax.
- Interprocedural call graphs.
- Struct initializers or expressions containing unmatched braces.
- Compiler extensions.

When exact semantics matter, tell the user this is a visual aid and not a compiler-verified control-flow graph.

## Validation

Always check the generated report. The script parses the `.drawio` file as XML and verifies that it contains `mxGraphModel/root`.

If validation fails, do not present the `.drawio` as complete. Fix the converter or reduce the input and rerun.

## Path Report

Use `.paths.md` when the user needs branch coverage-style path sequences.

- `Branch path count` is the number of complete Start-to-End paths found for that function.
- `Path N` is the numeric edge sequence.
- `Labels` keeps the edge labels, including `yes`, `no`, `case`, `default`, `loop`, `break`, and `return`.
- Loop back edges are expanded at most once per path to avoid infinite paths.
