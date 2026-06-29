# Flowchart Conventions

Use this reference when adjusting the converter or manually reviewing generated diagrams.

## Shapes

- Start: ellipse.
- End: ellipse.
- Do not add a separate function header box above Start. Keep function names in reports and filenames, not as an extra top-level flowchart node.
- Return: ellipse connected to the function End.
- Process/declaration/assignment/function call: rectangle.
- Input/output such as `printf`, `scanf`, `puts`, `getchar`, `putchar`: parallelogram.
- Decision constructs: diamond.
  - `if` / `else if`
  - `for`
  - `while`
  - `do while`
  - `switch`
- Simple `if (...) { break; }` / `if (...) { continue; }`: labeled edge, not a separate node.
- Standalone or complex `break` and `continue`: highlighted rounded rectangle.
- `goto`: highlighted process node.
- Label such as `__end:`: dashed rounded rectangle.

## Edges

- Label every edge with a monotonically increasing sequence number.
- Append branch text after the sequence number:
  - `yes` and `no` for binary decisions.
  - `case ...` and `default` for switch branches.
  - `loop` for loop back edges.
  - `return` for return-to-End edges.
  - `goto` for goto-to-label edges.
- Route forward flow downward.
- Route loop back edges on the left side of the loop body.
- Route `break` and `goto` exit edges on staggered right-side channels.
- Stagger side channels horizontally so two exit lines never share the exact same vertical segment.
- Merge simple break/continue edges above the next ordinary node, then enter that node through the top center.
- Reserve vertical whitespace after loops with break exits to keep merge lines away from process boxes.
- Include all edge waypoints in preview bounds so long side routes and labels are not clipped.
- Avoid crossing branch edges by placing then/yes branches to the left and else/no branches to the right.
- Keep one dominant downward spine for the normal path of each function.
- Put side branches beside the spine, then merge them back into the next common statement.
- Draw no diagonal spaghetti lines. Use orthogonal segments with explicit waypoints.
- Put edge labels near the source side of the line when possible so the decision that produced the edge is obvious.

## Construct Patterns

- `if`: one incoming edge to the diamond, `yes` to the true body, `no` to the false body or the next statement. Both normal exits merge before the next statement.
- `else`: do not create a separate decision. Treat it as the `no` branch of the preceding `if`.
- `else if`: represent as a second diamond on the `no` side of the previous `if`.
- `for`: use a diamond for the loop condition/header. `yes` enters the body; normal body exit and `continue` route back to the loop diamond; `no` exits to the next statement.
- `while`: same as `for`, but the condition diamond appears before the body.
- `do while`: draw the body first, then the condition diamond. `yes` loops back to the body; `no` exits.
- `switch`: use one diamond. Each `case` and `default` is an outgoing branch. Case bodies should align horizontally under the switch, then merge after `break` or normal completion.
- `break`: exits the nearest loop or switch and connects to the statement after that construct.
- `continue`: connects to the nearest loop condition/update.
- `goto`: connects directly to the matching label and does not fall through to the next statement.
- Label: acts as a merge point, then continues downward through cleanup or subsequent statements.
- `return`: connects directly to the function End and does not merge into later statements.

## Semantics

- `return` terminates the current function flow and connects directly to End.
- `break` exits the nearest loop or switch.
- `continue` returns to the nearest loop condition/update.
- `switch` cases are visual branches. Fallthrough can be ambiguous; review generated case exits manually when a case does not contain `break` or `return`.

## Mermaid Intermediate

Mermaid is used as a human-readable intermediate representation. Treat `.drawio` as the editable target artifact, and `.svg` / `.png` as previews.

## Path Sequences

The converter writes `.paths.md` with function-level path sequences.

- A path is a complete Start-to-End sequence of edge numbers.
- Example shape: `1-2-3-5`.
- The path list is useful for branch coverage, test-case planning, and checking that generated lines are traceable.
- Loops are represented with zero-iteration and one-iteration style paths. Infinite repeated loop paths are intentionally not expanded.
