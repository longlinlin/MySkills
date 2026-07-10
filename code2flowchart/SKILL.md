---
name: code2flowchart
description: Convert C and C++ source code or individual functions into clean, editable draw.io control-flow diagrams. Use for .c, .h, .cpp, .cc, .cxx, and .hpp files containing procedural logic such as if/else, loops, switch/case, break, continue, goto, return, basic exceptions, task calls, and embedded hardware calls. Prefer function-level conversion for complex code and generate previews or analysis files only when requested.
---

# code2Flowchart

Convert C/C++ control flow into an editable `.drawio` diagram. Keep the graph readable and semantically useful; do not mirror every source token as a separate node.

## Default workflow

1. Locate the source file or save pasted code as a temporary `.c` or `.cpp` file.
2. For a multi-function or complex file, select one function with `--function`.
3. Run the bundled converter.
4. Open or inspect the `.drawio` result.
5. Generate a PNG preview only when visual review is needed.
6. If parsing misses important logic, isolate the function, expand relevant macros, or simplify template-heavy syntax and rerun.

Default command:

```bash
python code2flowchart/scripts/code2flowchart.py source.c --function target -o output
```

The default output is only `source.drawio`.

Optional outputs:

```bash
# Add a PNG preview
python code2flowchart/scripts/code2flowchart.py source.c --preview -o output

# Generate every legacy artifact for debugging or downstream analysis
python code2flowchart/scripts/code2flowchart.py source.c --all -o output
```

Available flags:

- `--function NAME`: convert only the named function.
- `--preview`: add a PNG preview.
- `--svg`: add an SVG preview.
- `--mermaid`: add the Mermaid intermediate file.
- `--paths`: add function path sequences.
- `--report`: add the conversion report.
- `--analysis`: add structured analysis JSON.
- `--all`: generate every supported artifact.

## Graph rules

- Label the function entry and exit exactly `Start` and `End`.
- Use ellipses for Start, End, return, and throw.
- Use rectangles for declarations, assignments, ordinary calls, and processing.
- Use parallelograms for C stdio and C++ iostream operations.
- Use diamonds for `if`, conditional loops, and `switch`.
- Keep `for (;;)` and equivalent infinite loops free of a false/no exit edge.
- Remove a top-level trailing `break` from each switch case instead of drawing a break box.
- Merge equivalent empty switch cases into a single “No test call” or equivalent branch.
- Add an explicit `no match` route when a switch has no `default` case.
- Merge case exits through one small connector before continuing downward.
- Route loop-back edges on the left and keep forward flow on a dominant vertical spine.
- Route `goto` and complex break exits through staggered side channels.
- Number every edge monotonically and append branch meaning such as `yes`, `no`, `case`, `loop`, `return`, or `terminate`.
- Treat known non-returning calls such as `exit`, `abort`, and `osThreadTerminate` as terminating flow. Review `osThreadTerminate` manually if it targets another thread and can return.
- Do not add a separate function-title box above Start.

Read [references/flowchart-conventions.md](references/flowchart-conventions.md) when editing layout or reviewing a branch-heavy diagram.

For embedded retry loops, cleanup labels, task dispatchers, or hardware calls, read [references/c-control-flow-patterns.md](references/c-control-flow-patterns.md).

## Complexity policy

- Prefer one function per diagram.
- Keep ordinary function calls as single nodes; do not recursively expand callees.
- Merge adjacent low-value statements when manual simplification is needed.
- Preserve decisions, exits, side effects, cleanup, and externally visible calls.
- Use a labeled process node for code that cannot be parsed reliably instead of inventing control flow.
- Review macro-heavy, template-heavy, lambda-heavy, or extension-heavy code manually.

The bundled parser is intentionally lightweight and is not a compiler-verified CFG.

## Verification

- Require the `.drawio` file to parse as XML and contain `mxGraphModel/root`.
- Visually inspect branch merges, loop exits, switch fallthrough, goto targets, and terminating calls.
- Do not treat XML validation as semantic validation.
- If no function is parsed, do not accept the empty Start-to-End diagram as a successful conversion.

## Optional analysis

Use `.analysis.json` and `.paths.md` only when the user requests branch coverage, test planning, or Dify integration. Do not generate them for ordinary flowchart requests.

For Dify integration, read [references/dify-agent-setup.md](references/dify-agent-setup.md). Keep deterministic parsing outside the LLM and pass structured analysis to Dify only when analysis generation is enabled.
