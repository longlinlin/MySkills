# AI Flowchart Review

Use this review protocol when the user asks for AI review, monitoring, or validation of a generated flowchart.

## Inputs

- Source file or pasted function.
- Generated `.drawio` file.
- PNG preview generated with `--preview`.

## Review procedure

1. List the source decisions, loops, exits, cleanup steps, and externally visible calls.
2. Inspect the PNG and trace each source path through the diagram.
3. Check that every decision has the intended outcomes, loops return to the correct header, and exits do not create impossible paths.
4. Check label readability, arrow direction, crossings, clipping, merge points, and whether the dominant path remains understandable.
5. Treat macros, templates, indirect calls, library behavior, and domain-specific termination calls as uncertain unless the source makes their behavior explicit.

## Review result

Write `output/<name>.ai-review.md` using this structure:

```markdown
# AI flowchart review: <function>

- Source: <source path>
- Diagram: <drawio path>
- Preview: <png path>
- Verdict: PASS | WARNING | FAIL

## Verified

- <source construct and matching diagram behavior>

## Findings

- <issue, uncertainty, or none>

## Visual review

- <layout/readability finding>

## Limits

- AI review is not compiler-verified control-flow analysis.
```

Use `PASS` only when no material semantic or visual issue is found. Use `WARNING` when the diagram is usable but needs manual confirmation. Use `FAIL` when the generated diagram is misleading or misses material control flow.
