---
name: code2flowchart
description: Convert C and C++ source code or individual functions into clean, editable draw.io control-flow diagrams. Proactively suggest conversion when a C/C++ function has 3+ control-flow decisions (if/switch/loop), contains goto/cleanup labels, implements retry/timeout logic, is a task dispatcher, or handles hardware state machines. Supports if/else, loops, switch/case, break, continue, goto, return, basic exceptions, FreeRTOS task calls, queues, semaphores, interrupts, retry loops, cleanup labels, and embedded hardware calls. Prefer function-level conversion for complex code. When AI review or monitoring is requested, compare the generated flowchart with source logic and write an auditable review result.
compatibility: Requires Python 3.10+. Optional Pillow for PNG preview. Optional draw.io desktop CLI for -e PNG export (repair_png.py available for IEND fix). Vision self-check requires a vision-capable model.
---

# code2Flowchart

Convert C/C++ control flow into an editable `.drawio` diagram. Use draw.io as the drawing and editing format; PNG, SVG, and Mermaid do not replace the editable deliverable. Read [references/flowchart-conventions.md](references/flowchart-conventions.md) before generating, refining, or reviewing a diagram. Keep the graph readable and semantically useful; do not mirror every source token as a separate node.

Proactively suggest flowchart conversion when: a C/C++ function has 3+ control-flow decisions (if/switch/loop), contains goto/cleanup labels, implements retry/timeout logic, is a task dispatcher, or handles hardware state machines.

## When to Use / When NOT to Use

**Use this skill for:**
- C/C++ function control-flow: if/else, loops, switch/case, goto, return, break, continue, try/catch
- Embedded patterns: retry loops, cleanup labels, task dispatchers, hardware/PLC calls, RTOS primitives
- AI review / audit: compare generated diagram against source, produce `.ai-review.md`

**Do NOT use — route to the appropriate sibling skill:**
- General architecture, network, cloud, or infrastructure diagrams → **drawio-skill**
- Diagrams-as-code for Markdown (GitHub-rendered flowcharts) → **mermaid-skill**
- Strict UML diagrams (class, sequence, component, C4) → **plantuml-skill**
- Freeform whiteboard sketches or hand-drawn style → **excalidraw-skill** or **tldraw-skill**

Scope this skill tightly to C/C++ code-to-flowchart conversion. Do not handle general architecture diagrams, UML diagrams, PlantUML diagrams, README Mermaid diagrams, network diagrams, cloud diagrams, or whole-project visual summaries here unless they are only incidental notes around a requested C/C++ function flowchart.

## 中文说明

这个 skill 只做一件事：把 C/C++ 源码里的函数控制流转换成可编辑的 `.drawio` 流程图。它不负责通用架构图、UML、PlantUML、网络图、云架构图或 README Mermaid 图。

### 使用场景判断
- **适用：** C/C++ 函数控制流（if/else、循环、switch/case、goto、return、break、continue、try/catch）、嵌入式模式（重试循环、清理标签、任务调度器、硬件/PLC调用、RTOS原语）
- **不适用 → 路由到对应技能：** 通用架构/网络/云图 → **drawio-skill**；Markdown 文本图表 → **mermaid-skill**；严格UML → **plantuml-skill**；手绘/白板风格 → **excalidraw-skill** 或 **tldraw-skill**

### 入口路由
根据用户意图选择模式：**Generate**（默认，完整10步转换）、**Review**（AI审查现有图）、**Refine**（修改已有图，最小化XML编辑）、**Validate**（仅运行 validate.py 结构检查）

### 工作流要点
1. 定位源码 → 2. 识别目标函数（`--function`） → 3. 先读函数体再转换 → 4. 运行转换器 → 5. **结构校验**：必须运行 `validate.py`（最多重试3次） → 6. **视觉自查**：检查7类缺陷（形状重叠、标签截断、连接丢失、形状越界、边穿过形状、边堆叠、边标签重叠），最多2轮 → 7. 检查 `.drawio` → 8. AI审查（按需） → 9. **用户审查循环**（最多5轮，超出建议手动微调） → 10. **解析失败降级**：6级渐进降级（展开宏→简化模板→折叠嵌套→缩小范围→标记为partial→手工指导），最多3步，绝不声称已知错误的输出成功

### 硬性轮次上限
- 结构校验重试：最多 3 次
- 视觉自查：最多 2 轮
- 用户审查：最多 5 轮
- 解析降级：最多 3 步

### 视觉自查7项缺陷（Step 6）
| # | 缺陷 | 现象 | 自动修复 |
|---|------|------|----------|
| 1 | 形状重叠 | 两个以上形状叠在一起 | 移开 ≥200px |
| 2 | 标签截断 | 文字被形状边界切断 | 增大形状宽高 |
| 3 | 连接丢失 | 箭头未连接到形状 | 验证 source/target ID |
| 4 | 形状越界 | 形状远离主体集群 | 移到集群附近，确保 y>0 |
| 5 | 边穿过形状 | 边穿过无关形状内部 | 添加航点或增加间距 |
| 6 | 边堆叠 | 多条边共用同一路径 | 分散出入口点 |
| 7 | 边标签重叠 | 边文字与节点/标签/边线重叠 | 添加白色背景 + 偏移 |

### 常见错误
| 错误 | 修复 |
|------|------|
| 未解析到函数 | 检查源码是否有完整函数定义和大括号 |
| 空 Start-to-End 图 | 检查函数名匹配，重读函数体 |
| 宏隐藏控制流 | 展开宏或标记为 uncertain |
| 密集分支标签重叠 | 使用 `--detail-level overview` |
| 模板代码静默失败 | 简化模板或标记为 partial |
| XML合法但无实际内容 | 运行 `validate.py --score` 检查边数 |
| PNG 空白或太小 | 安装 Pillow，增大间距 |
| Goto目标未找到 | 检查标签名是否完全匹配 |

### 路径枚举注意事项
`branch_path_count` 和路径列表是通过控制流图的组合DFS计算的，**不包含数据流分析**。部分路径可能组合了矛盾的谓词（例如循环体内设置了 `count>0`，后续 `if(count==0)` 却走了 `yes` 分支）。路径数是**理论上界**，不是精确可达路径数，用于测试规划前必须做语义过滤。

### 浏览器回退
当 draw.io 桌面CLI不可用时：`python code2flowchart/scripts/encode_drawio_url.py output/<fn>/<fn>.drawio`（只读查看），加 `--edit` 进入编辑模式。图表XML编码在URL片段中，不上传到任何服务器。

### PNG 修复
从 draw.io 桌面导出 `-e` 产生的PNG可能截断IEND块，用 `python code2flowchart/scripts/repair_png.py <diagram>.drawio.png` 修复。`code2flowchart.py --preview` 产生的PNG（Pillow）不需要。

### 配套脚本
| 脚本 | 用途 |
|------|------|
| `validate.py` | 结构校验：重复ID、悬空边、几何体、重叠、交叉。`--strict` CI门控，`--score` 可读性评分 |
| `repair_png.py` | 修复 draw.io CLI 导出的PNG截断IEND块 |
| `encode_drawio_url.py` | 将 .drawio 编码为浏览器URL |
| `lang_support.py` | 多语言提取框架（抽象基类+注册表） |
| `c_flowchart.py` | C/C++ 语言支持（参考实现） |
| `py/js/go_flowchart.py` | Python/JS/Go 语言支持（桩，待实现） |
| `dd_generator.py` | DD详细设计文档生成器（`.dd.md`） |
| `ut_generator.py` | UT单元测试设计 + 骨架代码生成器（`.ut.md`, `.ut.cpp`, `.ut.c`） |

### 子技能
| 技能 | 用途 |
|------|------|
| `skills/ddut-generator/SKILL.md` | DD/UT 自动化生成：详细设计文档 + 单元测试用例 + 测试骨架代码 |

使用时优先按"单函数一个流程图"处理。复杂 `.c/.cpp` 文件不要直接画成一个大图，应先选择目标函数。如果代码里有宏、编译器扩展、回调或硬件库函数隐藏控制流，要明确标记为需要人工确认，不能凭空推断。

输出的核心文件是 `.drawio`。PNG、SVG、Mermaid、路径报告和分析 JSON 都是辅助产物，只在用户需要预览、审查、测试路径或调试转换器时生成。

## Entry-Point Routing

Choose the workflow mode based on what the user wants:

| Mode | User wants to... | Entry point |
|------|-----------------|-------------|
| **Generate** (default) | Convert C/C++ code to a flowchart | Run the full 10-step workflow below |
| **Review** | AI-audit an existing diagram against source | Skip to Step 8 (AI review); run `validate.py` first |
| **Refine** | Change an existing diagram | Load the `.drawio`, apply a minimal targeted XML edit, re-export (Step 9) |
| **Validate** | Check a `.drawio` for structural issues | Run `validate.py` directly (see Step 5) |

## Workflow (Generate mode)

1. **Locate source** — find the source file, or save pasted code as a temporary `.c` or `.cpp` file.
2. **Identify target** — determine the function to convert. For multi-function or complex files, prefer exactly one function with `--function <name>`.
3. **Read before converting** — read the selected function body and nearby macro definitions. Do not infer control flow from file names, function names, or comments alone.
   **Plan the control flow before layout** — apply the sequence, selection, and loop templates in [references/flowchart-conventions.md](references/flowchart-conventions.md#代码转流程图的结构规范). Identify normal exits separately from break/continue/return/goto, preserve their real targets, then arrange nodes and route edges. If the converter cannot preserve the template's semantics, correct the diagram or mark it partial; documenting the rule alone does not implement it in the converter.
4. **Run converter** — execute the bundled converter (see default command below).
5. **Structural validation (REQUIRED)** — run `python code2flowchart/scripts/validate.py output/<fn>/<fn>.drawio` before proceeding. If errors are found, fix and regenerate. **Max 3 retries.**
6. **Visual self-check** — use vision capability to inspect the PNG preview for the 7 defect categories listed in the self-check table below. Apply the prescribed auto-fix, re-render, and re-validate after each fix. **Max 2 self-check rounds.** Skip if vision is unavailable.
7. **Open/inspect** — examine the `.drawio` result in draw.io desktop or via the browser fallback URL.
8. **AI review** (when requested) — run the full comparison protocol (see AI review section below). Include structural validation results from Step 5.
9. **Review loop** — show the image to the user, collect feedback, apply minimal targeted XML edits, re-export. **Max 5 rounds.** After 5 rounds, suggest the user fine-tune manually in draw.io desktop or at [diagrams.net](https://app.diagrams.net).
10. **Parsing failure degradation** — when the parser cannot handle the code, degrade in this order (**max 3 degradation steps total**):
    1. Isolate the function and expand known macros
    2. Simplify template-heavy syntax or extract the instantiated form
    3. Collapse deeply nested constructs into labelled subflow nodes
    4. Reduce to a smaller function scope
    5. Mark unparseable regions as labelled process nodes and flag the diagram as **partial**
    6. Fall back to manual diagram authoring guidance
    - **Policy:** Never claim success on known-broken output. Degradation stops at "partial diagram with marked uncertainties."

## Default command

```bash
python code2flowchart/scripts/code2flowchart.py source.c --function target
```

The default output is only `<function>.drawio`, written to `output/<function>/`. Every function has its own output folder. Use `-o` or `--out-dir` to override the base output directory.

Optional outputs:

```bash
# Add a PNG preview
python code2flowchart/scripts/code2flowchart.py source.c --preview

# Generate every artifact (includes structural validation)
python code2flowchart/scripts/code2flowchart.py source.c --all
```

## Available flags

- `--function NAME`: convert only the named function.
- `-o DIR` / `--out-dir DIR`: override the base output directory; a function-named subfolder is still created inside it.
- `--preview`: add a PNG preview.
- `--svg`: add an SVG preview.
- `--mermaid`: add the Mermaid intermediate file.
- `--paths`: add function path sequences.
- `--report`: add the conversion report.
- `--analysis`: add structured analysis JSON.
- `--validate`: run `validate.py` structural lint after generation.
- `--dd`: generate Detailed Design document (`.dd.md`) from analysis.
- `--ut`: generate Unit Test design (`.ut.md`) + test code (`.ut.cpp`, `.ut.c`).
- `--project-prefix <PREFIX>`: set Function ID prefix for DD/UT, e.g. `SWDD_CHARGE`.
- `--all`: generate every supported artifact (implies `--validate --dd --ut`).

## Scope limits

- Generate flowcharts from C/C++ code only.
- Keep `.drawio` as the target artifact. Mermaid is allowed only as the converter's intermediate/debug artifact when `--mermaid` or `--all` is requested.
- Do not generate PlantUML, general UML, architecture diagrams, network diagrams, cloud diagrams, or README-only diagrams from this skill.
- Do not infer module architecture or whole-codebase relationships beyond the selected function's visible control flow.
- When a user asks for non-flowchart outputs, explain that this skill is limited to C/C++ flowcharts and route to the appropriate sibling skill (see "When to Use / When NOT to Use").
- Apply the source-first rule: read real code, extract visible decisions/loops/exits, and mark anything inferred or hidden by macros as uncertain.

## Graph rules

Apply the code-to-flowchart structure and path rules in [references/flowchart-conventions.md](references/flowchart-conventions.md#代码转流程图的结构规范), not just its shape styles. Control-flow semantics take precedence over visual symmetry, compactness, or a generic single-exit drawing convention.

- Label the function entry and exit exactly `Start` and `End`.
- Use ellipses for Start, End, return, and throw.
- Use rectangles for declarations, assignments, ordinary calls, and processing.
- Use parallelograms for C stdio and C++ iostream operations.
- Use diamonds for `if`, conditional loops, and `switch`.
- Keep `for (;;)` and equivalent infinite loops free of a false/no exit edge.
- Remove a top-level trailing `break` from each switch case instead of drawing a break box.
- Merge equivalent empty switch cases into a single "No test call" or equivalent branch.
- Add an explicit `no match` route when a switch has no `default` case.
- Merge case exits through one small connector before continuing downward.
- Route loop-back edges on the left and keep forward flow on a dominant vertical spine.
- Route `goto` and complex break exits through staggered side channels.
- Number visible edges consecutively from 1 and append branch meaning such as `yes`, `no`, `case`, `loop`, `return`, or `terminate`. Leave a simple merge's outgoing connector unlabeled when it has no branch meaning; renumber the remaining edges without gaps in every generated artifact.
- Treat known non-returning calls such as `exit`, `abort`, and `osThreadTerminate` as terminating flow. Review `osThreadTerminate` manually if it targets another thread and can return.
- Do not add a separate function-title box above Start.

Read [references/flowchart-conventions.md](references/flowchart-conventions.md) when editing layout or reviewing a branch-heavy diagram.

For embedded retry loops, cleanup labels, task dispatchers, or hardware calls, read [references/c-control-flow-patterns.md](references/c-control-flow-patterns.md).

## Complexity policy

- Prefer one function per diagram.
- If the source contains many functions, ask for or choose the most relevant function rather than creating a crowded file-level chart.
- Keep ordinary function calls as single nodes; do not recursively expand callees.
- Merge adjacent low-value statements when manual simplification is needed.
- Preserve decisions, exits, side effects, cleanup, and externally visible calls.
- Use a labeled process node for code that cannot be parsed reliably instead of inventing control flow.
- Collapse deeply nested retry loops that contain an inner retry loop and success return into a labeled verification subflow; keep its retry, success-return, and exhausted-retry exits visible.
- Treat verbose `TRACE_INFO` and `TRACE_WARN` calls as flow annotations rather than standalone nodes when they would obscure the control flow. Keep error reporting visible with a concise semantic label.
- Treat macros that hide control flow as uncertain until expanded or manually reviewed.
- Review macro-heavy, template-heavy, lambda-heavy, or extension-heavy code manually.

The bundled parser is intentionally lightweight and is not a compiler-verified CFG.

## Visual Self-Check (Step 6)

After rendering the PNG preview, use vision to inspect for these 7 defect categories.
Apply the prescribed auto-fix, then re-export and re-validate. **Max 2 rounds.**

| # | Defect | What to look for | Auto-fix action |
|---|--------|-----------------|-----------------|
| 1 | **Overlapping shapes** | Two or more shapes rendered on top of each other | Shift apart ≥200px; re-run layout |
| 2 | **Clipped labels** | Node/edge text cut off at shape boundaries | Increase shape width or height to fit text |
| 3 | **Missing connections** | Arrows not visually connecting to shape borders | Verify source/target IDs match existing cells |
| 4 | **Off-canvas shapes** | Shapes at extreme coordinates far from the main cluster | Move near the cluster; ensure positive y |
| 5 | **Edge-shape overlap** | Edge line crosses through an unrelated shape interior | Add waypoints (`<Array as="points">`) or increase spacing |
| 6 | **Stacked edges** | Multiple edges sharing the same visual path | Distribute entry/exit points across shape perimeters |
| 7 | **Edge-label overlap** | Edge label text overlaps a node, another label, or the edge line | Add white label background (`labelBackgroundColor=#FFFFFF`) and geometry offset |

## Verification

- Require the `.drawio` file to parse as XML and contain `mxGraphModel/root`.
- **Run `validate.py`** before accepting any diagram: `python code2flowchart/scripts/validate.py output/<fn>/<fn>.drawio`. This catches structural errors (duplicate IDs, dangling edges, bad geometry) that visual inspection misses.
- Prefer `validate.py --strict` for gating CI/CD or automated workflows.
- Use `validate.py --score` to compare layout variants of the same graph (lower is better).
- Visually inspect branch merges, loop exits, switch fallthrough, goto targets, and terminating calls.
- Verify visible edge numbers are unique and consecutive from 1; simple unlabeled merge exits must not consume a number. Match labels across diagrams, path reports, and analysis when those artifacts are requested.
- Inspect the draw.io rendering at both whole-diagram and label-detail scale. Check merge-point labels, arrowheads, and return-to-End routing; a custom preview alone does not prove draw.io rendering is correct. Disclose when draw.io rendering cannot be checked.
- Do not treat XML validation as semantic validation.
- If no function is parsed, do not accept the empty Start-to-End diagram as a successful conversion.
- Check that every visible source-level decision has matching outgoing paths.
- Check that every `return`, `break`, `continue`, `goto`, `throw`, and known non-returning call exits to the correct target.
- Check that every loop has a visible entry path, back edge, and exit path unless it is intentionally infinite.
- Check that every `switch` case either routes to its body, falls through visibly, exits, or merges through the shared connector.
- If a macro or compiler extension changes control flow and is not expanded, flag the diagram as partial instead of silently drawing a guessed path.
- If the selected function is too large to read clearly, split the request into smaller function-level diagrams.
- Check draw.io rendering constraints: required root cells, valid XML escaping, expanded edge cells with geometry, readable labels, and enough spacing for arrowheads.

## Hard Round Limits

All iterative loops have firm caps. When a limit is reached, stop and show current results rather than looping silently.

| Loop | Max rounds | On exhaustion |
|------|-----------|---------------|
| Structural validation retries (Step 5) | 3 | Show the last errors; ask user whether to fix or accept as-is |
| Visual self-check (Step 6) | 2 | Show the last image; note remaining known defects |
| Review loop (Step 9) | 5 | Suggest the user fine-tune manually in draw.io desktop or [diagrams.net](https://app.diagrams.net) |
| Parsing failure degradation (Step 10) | 3 total steps | Stop at "partial diagram with marked uncertainties" — **never claim success on known-broken output** |

## AI review and monitoring

When the user requests AI review, do not only confirm XML validity. Compare the source control flow with the generated diagram, inspect the PNG preview, and record the result as `output/<function>/<function>.ai-review.md`.

- Run `validate.py` first and include its results in the review.
- Verify every decision outcome, loop entry/back/exit, break/continue, return/throw/goto, and relevant terminal call.
- Verify that meaningful calls and cleanup steps remain visible.
- Cross-reference `validate.py` warnings (overlaps, crossings) against the visual inspection.
- Flag unsupported syntax, uncertain semantics, missing paths, misleading exits, clipped labels, crossings, or unreadable layouts.
- Mark the result `PASS`, `WARNING`, or `FAIL`; never claim compiler-verified semantics.
- Return the review findings and artifact links to the user.

Read [references/ai-flowchart-review.md](references/ai-flowchart-review.md) before conducting an AI review.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| No function parsed | Verify source has complete function definitions with braces; check `--function` name matches |
| Empty Start-to-End diagram | Function body may be empty or parser missed it; re-read source and verify braces |
| Macro hides control flow | Expand the macro manually or mark as uncertain with a labelled process node |
| Labels overlap in dense branches | Use `--detail-level overview` for compaction; increase X_GAP/Y_GAP |
| Template-heavy code fails silently | Simplify templates or extract the instantiated form; mark as partial |
| XML valid but diagram has no real content | Run `validate.py --score`; check edge/path counts > 0 |
| PNG preview is blank or too small | Ensure Pillow is installed (`pip install Pillow`); increase diagram spacing |
| Goto target not found in diagram | Verify label name in source matches exactly; check for missing label token |
| `validate.py` reports many warnings | Run with `--score` to quantify; fix highest-impact issue (through-vertex > crossing > overlap) |

## Browser Fallback

When the draw.io desktop CLI is unavailable for viewing/editing, encode the `.drawio` file as a browser URL:

```bash
# Read-only viewer
python code2flowchart/scripts/encode_drawio_url.py output/<fn>/<fn>.drawio

# Editable editor
python code2flowchart/scripts/encode_drawio_url.py --edit output/<fn>/<fn>.drawio
```

The diagram XML is carried in the URL fragment (`#`), so nothing is uploaded to any server.

## PNG Repair

If you later export from draw.io desktop with `-e` (embed XML), the resulting PNG may have a truncated IEND chunk that vision APIs reject. Fix it with:

```bash
python code2flowchart/scripts/repair_png.py <diagram>.drawio.png
```

Idempotent — safe to run unconditionally after any draw.io CLI `-e` export. Not needed for PNGs generated directly by `code2flowchart.py --preview` (those use Pillow, which produces valid PNGs).

## Optional analysis

Use `.analysis.json` and `.paths.md` only when the user requests branch coverage, test planning, or Dify integration. Do not generate them for ordinary flowchart requests.

**Path enumeration caveat:** The `branch_path_count` and listed paths are computed by combinatorial DFS over the control-flow graph — they do **not** incorporate data-flow analysis. Paths that combine contradictory branch outcomes (e.g., a loop that sets `count > 0` followed by `if (count == 0)` taking the `yes` branch) may appear in the listing. Always filter paths against semantic constraints before using them for test planning. The count is an **upper bound**, not a precise reachable-path count.

For Dify integration, read [references/dify-agent-setup.md](references/dify-agent-setup.md). Keep deterministic parsing outside the LLM and pass structured analysis to Dify only when analysis generation is enabled.

## Companion Scripts

All scripts live in `scripts/` alongside the main `code2flowchart.py` converter:

| Script | Purpose |
|--------|---------|
| `code2flowchart.py` | Core C/C++ → drawio flowchart converter |
| `validate.py` | Structural linter: duplicate IDs, dangling edges, geometry, overlaps, crossings. `--strict` for CI gating, `--score` for readability comparison |
| `repair_png.py` | Repair truncated IEND chunk in draw.io CLI `-e` PNG exports |
| `encode_drawio_url.py` | Encode `.drawio` XML into a diagrams.net browser URL (viewer or editor mode) |
| `lang_support.py` | Multi-language extraction framework (ABC + registry) |
| `c_flowchart.py` | C/C++ language support (reference implementation) |
| `py_flowchart.py` | Python language support (stub — not yet implemented) |
| `js_flowchart.py` | JavaScript/TypeScript language support (stub — not yet implemented) |
| `go_flowchart.py` | Go language support (stub — not yet implemented) |
