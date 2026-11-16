# AI Flowchart Review

Use this review protocol when the user asks for AI review, monitoring, or validation of a generated flowchart.

## 中文说明

本文件用于用户明确要求的 AI 复核，不代替每次生成或修改后必做的[生成后自检](flowchart-self-check.md)。复核目标是检查流程图是否忠实表达源码中可见的控制流，不是证明它等同于编译器级 CFG。

同时核对源码、`.drawio` 和最新渲染图，检查分支、循环、跳转、清理步骤及硬件调用。具有视觉能力时实际查看预览；无法渲染或没有视觉能力时记录限制，不声称视觉检查通过。宏、模板、回调或库函数行为不明确时写入 `Limits` 或 `Findings`，结论使用 `PASS/WARNING/FAIL`。

## Inputs

- Source file or pasted function.
- Generated `.drawio` file.
- A current rendered preview: PNG, browser-rendered SVG, or native draw.io export.

## Review procedure

1. Read the selected function body and relevant macro definitions, then list its decisions, loops, exits, cleanup steps, and externally visible calls. Do not infer behavior from names or comments alone.
2. Inspect the current rendered image and trace each visible source path through the diagram; disclose when this cannot be performed.
3. Check that every decision has the intended outcomes, loops return to the correct header, and exits do not create impossible paths.
4. Check label readability, arrow direction, crossings, clipping, merge points, and whether the dominant path remains understandable.
5. Treat macros, templates, indirect calls, library behavior, and domain-specific termination calls as uncertain unless the source makes their behavior explicit.

## 源码优先核对

- 每个分支必须来自真实源码结构，或明确标记为轻量解析器的降级处理。
- 未展开宏、未知条件编译配置、函数指针及外部库隐藏的路径不能作为已经验证的执行事实。
- 不因嵌入式代码“通常如此”而添加路径；注释与代码冲突时以代码为准，并在问题清单说明。

## Review result

Write `<basename>.ai-review.md` beside the reviewed `.drawio` file (by default `output/<function>/<function>.ai-review.md`) using this structure:

```markdown
# AI flowchart review: <function>

- Source: <source path>
- Diagram: <drawio path>
- Preview: <rendered image path or SKIPPED with reason>
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

Use `PASS` only when source and actual visual checks are complete and no material issue remains. Use `WARNING` when a check is skipped or the diagram needs manual confirmation. Use `FAIL` when the generated diagram is misleading or misses material control flow.
