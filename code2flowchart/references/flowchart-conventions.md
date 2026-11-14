# Flowchart Conventions

Use this reference when adjusting the converter or manually reviewing generated diagrams.

## 中文说明

本文件定义 C/C++ 流程图的通用绘制约定。目标是让 `.drawio` 图既能人工阅读，也能追溯回源码控制流。

核心原则：

- 一个函数优先对应一张图。
- `Start` 和 `End` 必须固定命名，函数名放在文件名或报告里，不额外画标题框。
- 判断条件用菱形，普通语句和函数调用用矩形，输入输出用平行四边形，`return/throw` 用终止形状。
- `break/continue/goto/return` 必须连到语义正确的目标，不能为了图好看而合并成错误路径。
- 边要编号并带分支含义，便于和 `.paths.md` 路径报告互相核对。
- 普通流程尽量自上而下，循环回边走左侧，`break/goto` 等退出边走右侧错开通道。
- 同一顺序代码块内连续声明、赋值、自增/自减合并到一个处理框；遇到判断、循环、单独的函数调用、标签或退出语句即停止合并，不跨控制流边界。
- 合流点只用于内部布线，图中不显示黑色圆点；回环线与退出线分别走左、右侧，不能互相交叉。
- 即使目标相同，循环 `no`、`break`、`goto` 等不同来源的退出边也要保留独立竖向通道；只在目标附近合流，不能提前叠成一条长竖线。

## Shapes

- Start: ellipse / terminator shape. The label must be exactly `Start`.
- End: ellipse / terminator shape. The label must be exactly `End`.
- Do not add a separate function header box above Start. Keep function names in reports and filenames, not as an extra top-level flowchart node.
- Return: ellipse connected to the function End.
- Throw: ellipse connected to End with a `throw` edge because it exits normal local control flow.
- Process/declaration/assignment/function call: rectangle.
- Input/output such as `printf`, `scanf`, `puts`, `getchar`, `putchar`, `std::cin`, `std::cout`, `std::cerr`, `std::clog`: parallelogram.
- Decision constructs: diamond.
  - `if` / `else if`
  - `for`
  - `while`
  - `do while`
  - `switch`
- C++ `try`: process rectangle. `catch (...)` clauses are labeled outgoing branches.
- Simple `if (...) { break; }` / `if (...) { continue; }`: labeled edge, not a separate node.
- Standalone or complex `break` and `continue`: highlighted rounded rectangle.
- `goto`: highlighted process node.
- Label such as `__end:`: dashed rounded rectangle.
- Multi-branch merge: an invisible routing junction; do not draw a filled connector circle.

## Edges

- Label every edge with a monotonically increasing sequence number.
- Append branch text after the sequence number:
  - `yes` and `no` for binary decisions.
  - `case ...` and `default` for switch branches.
  - `loop` for loop back edges.
  - Return/throw semantics remain in path data; outgoing edges of return/throw nodes show only the sequence number to avoid repeating the node's action.
  - `goto` for goto-to-label edges.
- Route forward flow downward.
- Route loop back edges on the left side of the loop body.
- Route `break` and `goto` exit edges on staggered right-side channels.
- Keep loop-back and break/goto exit rails on opposite sides; do not let them cross, including near the lower join.
- Inside a loop, route a short branch that skips a process box through the inner left corridor; place its return segment below every skipped box and above the junction.
- A long return-to-End edge may use the left corridor when the right corridor already carries a live decision or break exit; check that it does not cross a loop-back edge.
- Stagger side channels horizontally so two exit lines never share the exact same vertical segment.
- Merge simple break/continue edges above the next ordinary node, then enter that node through the top center.
- Merge switch-case exits through one invisible routing junction before entering the next ordinary node.
- Reserve vertical whitespace after loops with break exits to keep merge lines away from process boxes.
- Include all edge waypoints in preview bounds so long side routes and labels are not clipped.
- Avoid crossing branch edges by placing then/yes branches to the left and else/no branches to the right.
- Keep one dominant downward spine for the normal path of each function.
- Put side branches beside the spine, then merge them back into the next common statement.
- Draw no diagonal spaghetti lines. Use orthogonal segments with explicit waypoints.
- Put edge labels near the source side of the line when possible so the decision that produced the edge is obvious.

### 独立退出通道与参考来源

- 同侧重叠范围内的分支不能复用竖线。本项目通道横向错开 72px，避免标签和来源混在一起；范围不重叠时可以复用通道。
- 采用内短外长的顺序：较晚出发、较短的退出边走内侧，较早出发、较长的退出边走外侧；同目标分支的回接横线按来源顺序错开 18px，外侧边在更低处合流，避免横穿内侧竖线。
- 回环线、返回线和其他退出线必须共用该函数的节点外边界基准，不能分别计算不同的起始偏移；否则通道编号正确也可能出现实际位置倒置。提前返回若跨过后续循环，应位于该循环回边外侧。
- 最后一个 `return` 与终点之间没有其他节点时沿主线向下直连，不添加侧向绕线；提前返回仍需绕开后续流程，不能以直连优化为由穿过普通节点。
- 所有退出路径在 End 上方的隐形锚点合流，包括最后一个 `return`；End 只保留一条从顶部进入的向下箭头，不再使用侧面入箭头。只有一条已对齐的退出路径时可以直接向下连接，无须增加锚点。
- 合流区必须位于最后执行节点下方，按侧面回接线数量预留空间，不能让横线穿过 `return 0` 或其他执行框。远距离通道保持独立，只在最终合流区共用短主线。
- 公共短线不编号、不重复写 `return`，不画黑点，不产生新的返回动作；源码没有退出的无限循环不能为了外观伪造到 End 的边。
- 隐形合流锚点不等于允许长距离捆线。到达锚点前保持通道独立，只允许目标中心线上必要的末段合流。
- 校验不仅检查交叉，也检查侧边超过 40px 的共用竖线；`--strict` 将该警告视为失败。图形渲染检查仍需独立执行，零几何警告不等于已确认渲染效果。

借鉴而非直接搬入外部实现：

- [Agents365-ai/drawio-skill](https://github.com/Agents365-ai/drawio-skill/blob/main/skills/drawio-skill/SKILL.md)：吸收显式拐点、独立端口和渲染后定向修正的做法，不扩大为架构图或其他语言分析工具。
- [ELK Merge Edges](https://eclipse.dev/elk/reference/options/org-eclipse-elk-layered-mergeEdges.html)：借鉴不合并边时各边独立连接的思路。
- [ELK Spacing Options](https://eclipse.dev/elk/documentation/tooldevelopers/graphdatastructure/spacingdocumentation.html)：将边与边、边与节点、边与标签的间距分别考虑；上面的 72/18/40px 是本项目约定，不是 ELK 默认值。

## draw.io Rendering Rules

- Keep required root cells `id="0"` and `id="1"` in every `.drawio` file.
- Never emit self-closing edge cells. Every edge needs `<mxGeometry relative="1" as="geometry" />`.
- Escape XML label characters: `&amp;`, `&lt;`, `&gt;`, and `&quot;`.
- Use `&#xa;` for line breaks inside draw.io label values; do not use literal `\n`.
- Avoid `--` inside XML comments because it is invalid XML.
- Use `html=1` in shape and edge styles so labels render consistently.
- Pin entry/exit points when a node has multiple incoming or outgoing edges; distribute them across the side of the shape instead of stacking lines.
- Leave enough straight-line distance before a target so the arrowhead does not overlap the last bend.
- For branch-heavy functions, leave routing corridors around side exits, `goto` paths, and loop-back edges.

### draw.io 官方连线规则落地

官方文档说明的是编辑器能力；右栏是本 skill 为 C 控制流采用的约束，并非声称官方强制所有图都采用这些限制。

| 官方能力与来源 | 本 skill 的落地规则 |
| --- | --- |
| [固定与浮动连接](https://www.drawio.com/docs/manual/connectors/connector-fixed-vs-floating/) | 所有导出边显式设置 `exitX/exitY/entryX/entryY`。普通流程从源节点底部连接目标顶部；最终退出在 End 上方合流，只保留一条向下连接到顶部中心的箭头 |
| [航点与路径调整](https://www.drawio.com/docs/manual/connectors/waypoints-connectors/) | 使用正交折线和明确航点；调整节点后重新检查路径与标签。手动航点与自动重路由不是同一种行为，不能假定挪动节点后原路径仍正确 |
| [连接线标签](https://www.drawio.com/docs/manual/connectors/connector-labels/) | 分支含义靠近来源，标签避开弯角、箭头和节点；需要时使用实色背景。节点已经显示 `return/throw` 时，出线仅显示编号，不能在公共出口线再重复一个 `return` |
| [箭头样式](https://www.drawio.com/docs/manual/connectors/change-connector-arrows/) | 控制流只在目标端显示实心箭头，源码中非双向关系不得画双向箭头。进入不可见布线锚点的线段不画箭头，继续进入真实目标的线段恢复箭头 |
| [连接线合流](https://www.drawio.com/docs/manual/connectors/connectors-join/) | 几何相交不等于控制流合流；普通分支仅在真实共同后继处合流。最终退出与最后一个返回共同指向 End 上方的独立合流锚点，再以一支向下箭头进入 End。按用户要求不显示实心合流点 |
| [自动避障](https://www.drawio.com/docs/manual/connectors/connectors-auto-route/) | 只能把避开形状视为一项能力，不能由此宣称边与边零交叉。仍分别检查穿框、交叉、共线、端口与标签，并进行渲染检查 |
| [连线总览中的捆线与跨线桥](https://www.drawio.com/docs/manual/connectors/) | 虽然编辑器支持 Bundle 与 line jumps，本 skill 不用它们掩盖退出线重合或交叉；显式设置 `jumpStyle=none`，优先重新分配通道和航点 |

## Construct Patterns

- `if`: one incoming edge to the diamond, `yes` to the true body, `no` to the false body or the next statement. Both normal exits merge before the next statement.
- `else`: do not create a separate decision. Treat it as the `no` branch of the preceding `if`.
- `else if`: represent as a second diamond on the `no` side of the previous `if`.
- `for`: use a diamond for the loop condition/header. `yes` enters the body; normal body exit and `continue` route back to the loop diamond; `no` exits to the next statement.
- Infinite `for (;;)` / `while (1)` / `while (true)`: keep the loop node but do not draw a false/no exit. Route only a real terminating statement to End.
- `while`: same as `for`, but the condition diamond appears before the body.
- `do while`: draw the body first, then the condition diamond. `yes` loops back to the body; `no` exits.
- `switch`: use one diamond. Each meaningful case body is an outgoing branch. Remove a top-level trailing `break` instead of drawing a break node. Combine cases with no action into one labeled branch, add `no match` when no `default` exists, align case bodies horizontally, and merge them through an invisible junction.
- `break`: exits the nearest loop or switch and connects to the statement after that construct.
- `continue`: connects to the nearest loop condition/update.
- `goto`: connects directly to the matching label and does not fall through to the next statement.
- Label: acts as a merge point, then continues downward through cleanup or subsequent statements.
- `return`: terminates at the function End, optionally through the final downward terminal junction, and never merges into later executable statements.
- `throw`: connects directly to End unless a local `catch` branch is modeled.
- Known non-returning calls such as `exit`, `abort`, and `osThreadTerminate` connect to End with a `terminate` edge. Review `osThreadTerminate` when it may target another thread and return.
- `try/catch`: draw the try body as normal flow and each catch as a labeled side branch. Keep catch branches orthogonal and merge after the catch body when execution can continue.

## Semantics

- `return` terminates the current function flow; a local routing junction may combine equivalent terminal paths before End without creating another executable return.
- `break` exits the nearest loop or switch.
- `continue` returns to the nearest loop condition/update.
- `switch` cases are visual branches. Fallthrough can be ambiguous; review generated case exits manually when a case does not contain `break` or `return`.
- An infinite loop has no normal path to End. End is reachable only through return, throw, terminating calls, or another explicit exit modeled by the source.

## C++ Notes

- Accept `.cpp`, `.cc`, `.cxx`, `.hpp`, and similar pasted snippets as C++ inputs.
- Parse visible function bodies only. Declarations, pure virtual functions, `= default`, and `= delete` do not produce flowcharts.
- Prefer readable member names such as `Class::method` in reports when the scope is visible.
- Treat `std::cout << ...`, `std::cin >> ...`, `std::cerr << ...`, and `std::clog << ...` as input/output nodes.
- Expect manual review for lambdas, overloaded operators, template-heavy code, and macro-generated functions.

## Mermaid Intermediate

Mermaid is used as a human-readable intermediate representation. Treat `.drawio` as the editable target artifact, and `.svg` / `.png` as previews.

- Use Mermaid only as an intermediate/debug artifact, not as the final answer for this skill.
- Keep Mermaid flow direction top-to-bottom for function control flow.
- Use decision nodes for source decisions and quote labels that contain special characters such as `:`, `()`, `[]`, or comparison operators.
- Preserve branch labels such as `yes`, `no`, `case`, `loop`, `return`, and `goto` so the Mermaid file remains traceable to the `.drawio` edge numbering.

## Path Sequences

The converter writes `.paths.md` with function-level path sequences.

- A path is a complete Start-to-End sequence of edge numbers.
- Example shape: `1-2-3-5`.
- The path list is useful for branch coverage, test-case planning, and checking that generated lines are traceable.
- Loops are represented with zero-iteration and one-iteration style paths. Infinite repeated loop paths are intentionally not expanded.

## Structural Validation / 结构校验

Run `validate.py` to catch structural errors that visual inspection misses / 运行 `validate.py` 发现肉眼检查遗漏的结构错误：

```bash
python code2flowchart/scripts/validate.py output/<fn>/<fn>.drawio       # lint 校验
python code2flowchart/scripts/validate.py output/<fn>/<fn>.drawio --score  # + readability score 可读性评分
python code2flowchart/scripts/validate.py output/<fn>/<fn>.drawio --strict # gate CI/CD 门控
```

The validator checks / 校验项：duplicate IDs / 重复ID, reserved ID reuse / 保留ID复用, dangling edge endpoints / 悬空边端点, broken parent references / 父引用断裂, missing/invalid geometry / 缺少几何体, negative-y position (above canvas) / y负坐标, non-positive size / 非正尺寸, sibling overlap / 兄弟节点重叠, edge-through-vertex routing / 边穿过顶点, and edge-edge crossings / 边边交叉.

Geometry checks for edge routing only apply to edges with explicit `<Array as="points">` waypoints — auto-routed edges are not geometry-checked, so warnings are free of false positives. / 几何检查仅适用于带有显式航点的边；自动路由的边不检查，因此警告零误报。

**Readability score / 可读性评分：** weighted sum of / 加权和 `20×through_vertex + 10×crossings + 5×overlaps`. Lower is better / 越低越好. Useful for comparing layout variants of the same graph / 用于比较同一图的布局变体.

## Browser Fallback / 浏览器回退

When the draw.io desktop CLI is unavailable, encode the `.drawio` for browser viewing / 当 draw.io 桌面CLI不可用时，编码图表为浏览器URL：

```bash
python code2flowchart/scripts/encode_drawio_url.py output/<fn>/<fn>.drawio        # viewer 只读
python code2flowchart/scripts/encode_drawio_url.py --edit output/<fn>/<fn>.drawio  # editor 编辑
```

The diagram XML is deflate-compressed and base64-encoded into the URL fragment — never uploaded to a server. / 图表XML经deflate压缩和base64编码后放入URL片段，不上传任何服务器.

## PNG Repair / PNG修复

draw.io CLI `-e` exports produce PNGs with a truncated IEND chunk that some PNG decoders (including Claude's vision API) reject. Fix with / draw.io CLI `-e` 导出的PNG存在截断的IEND块，部分PNG解码器（含Claude视觉API）拒绝解析。修复命令：

```bash
python code2flowchart/scripts/repair_png.py <diagram>.drawio.png
```

Not needed for PNGs generated by `code2flowchart.py --preview` (those use Pillow, which produces valid PNGs). / `code2flowchart.py --preview` 生成的PNG不需要（Pillow生成合法PNG）. Idempotent / 幂等 — 可无条件运行.
