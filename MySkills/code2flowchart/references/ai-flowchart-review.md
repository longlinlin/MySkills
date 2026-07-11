# AI Flowchart Review

Use this review protocol when the user asks for AI review, monitoring, or validation of a generated flowchart.

## 中文说明

本文件用于“AI 复核流程图”。复核目标不是证明流程图等同于编译器级 CFG，而是检查生成结果是否忠实表达了源码中可见的控制流。

复核时要同时看源码、`.drawio` 和 PNG 预览。重点检查：每个 `if/switch/loop` 的分支是否存在，每个 `return/break/continue/goto` 是否连到正确位置，清理路径和硬件调用是否保留，图形是否有线条交叉、标签裁剪或难以阅读的问题。

结论只能写 `PASS`、`WARNING` 或 `FAIL`。如果宏、模板、回调、库函数行为不明确，应写入 `Limits` 或 `Findings`，不要把不确定路径说成已经验证。

## Inputs

- Source file or pasted function.
- Generated `.drawio` file.
- PNG preview generated with `--preview`.

## Review procedure

1. Read the selected function body and relevant macro definitions. Do not infer behavior from names or comments alone.
2. List the source decisions, loops, exits, cleanup steps, and externally visible calls.
3. Inspect the PNG and trace each source path through the diagram.
4. Check that every decision has the intended outcomes, loops return to the correct header, and exits do not create impossible paths.
5. Check draw.io rendering details: labels are readable, arrows have direction, edges do not cross unrelated shapes, edge labels are not clipped, and merge points are clear.
6. Treat macros, templates, indirect calls, library behavior, and domain-specific termination calls as uncertain unless the source makes their behavior explicit.

## Source-first checks

- Confirm every diagram branch comes from a real source construct or a clearly labeled parser fallback.
- Mark any edge derived from an unexpanded macro, conditional compilation block, callback, function pointer, or domain-specific library behavior as uncertain.
- Do not add paths because they "usually happen" in embedded code. If the code does not show the path, leave it out or label it partial.
- When comments disagree with code, follow the code and mention the mismatch in `Findings`.

## Review result

Write `output/<function>/<function>.ai-review.md` using this structure:

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
