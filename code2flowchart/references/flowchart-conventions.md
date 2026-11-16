# Flowchart Conventions

Use this reference when adjusting the converter or manually reviewing generated diagrams.

## 中文说明

本文件定义使用 draw.io 绘制 C/C++ 函数流程图的设计规范。以可编辑的 `.drawio` 为正式交付文件，PNG、SVG 仅作预览，Mermaid 仅作可选中间产物。目标是让图既能人工阅读，也能追溯回源码控制流。

核心原则：

- 一个函数优先对应一张图。
- `Start` 和 `End` 必须固定命名，函数名放在文件名或报告里，不额外画标题框。
- 判断条件用菱形，普通语句和函数调用用矩形，输入输出用平行四边形，`return/throw` 用终止形状。
- `break/continue/goto/return` 必须连到语义正确的目标，不能为了图好看而合并成错误路径。
- 可见边编号从 1 连续递增，不重复、不跳号；简单合流点的无语义出边不显示编号，也不占用编号。分支含义和路径报告保持一致。
- 普通流程尽量自上而下，循环回边走左侧，`break/goto` 等退出边走右侧错开通道。
- 同一顺序代码块内连续声明、赋值、自增/自减合并到一个处理框；遇到判断、循环、单独的函数调用、标签或退出语句即停止合并，不跨控制流边界。
- 合流点只用于内部布线，图中不显示黑色圆点；回环线与退出线分别走左、右侧，不能互相交叉。
- 即使目标相同，循环 `no`、`break`、`goto` 等不同来源的退出边也要保留独立竖向通道；只在目标附近合流，不能提前叠成一条长竖线。

## 代码转流程图的结构规范

适用于从 C/C++ 函数生成 draw.io 控制流程图，不是通用业务流程图模板。先分析源码执行关系，再按顺序、选择、循环三类结构组合，最后确定坐标与连线路径。以下是生成和审查要求，不代表现有轻量解析器已经完整实现全部语义。

### 生成前的控制流设计

1. 确认函数范围，识别入口、普通语句、判断、循环、跳转、正常结束和提前退出。
2. 为每个结构区分正常继续出口与 `break/continue/return/goto/throw` 出口，并记录所属循环、switch 或目标标签。先确定连接关系，不能根据节点坐标猜测目标。
3. 递归组合结构：前一步的正常出口进入后一步；终止或跳转出口不得自动接到下一条语句。标签可以接收真实 goto 来边，不把不可达语句画成正常可达路径。
4. 仅在不改变执行顺序、分支和副作用的前提下合并普通语句。函数调用默认不展开；宏隐藏控制流时先核查，无法确认则标记不确定。
5. 控制流确定后再安排图形、分支列、回边和合流位置，最后统一可见编号并输出 `.drawio`。

### 顺序结构

- 模板：`入口 -> A -> B -> C -> 正常出口`。上一步执行完成后才能进入下一步。
- 同一结构的普通步骤沿主轴自上而下排列，相邻步骤只保留实际需要的一条有向连接。
- 连续初始化或赋值可合并为一个矩形，但保留语句顺序；不能跨越判断、跳转、关键调用或清理步骤进行合并。

### 选择结构

- `if/else` 模板：入口进入判断菱形，`yes` 进入真分支，`no` 进入假分支；只有仍会继续执行的出口才汇入共同后续步骤。
- 没有 `else` 时，`no` 直接到共同后续步骤；不能创建虚假的“执行 else”处理框。
- 两侧都能继续执行时使用一个清晰的合流；一侧 return 时只合并另一侧，双方都退出时不创建普通后续合流。
- `else if` 是前一判断 no 路径上的下一个判断。复合条件默认完整保留；若拆成多个判断，必须保持 `&&`、`||` 的短路顺序及条件中的副作用。
- `switch` 保留 case/default、真实贯穿和 break 关系；没有 default 时提供未匹配出口。不能把有贯穿的 case 误画成彼此独立的分支。

### 循环结构

- 先判断后执行（`while`）：`入口 -> 条件`；条件为真进入循环体，循环体正常结束回到条件，为假进入循环后续。允许零次执行。
- `for(init; cond; update)`：`初始化 -> 条件 -> 循环体 -> 更新 -> 条件`；初始化只执行一次，条件为假退出。初始化和更新可显式展开；若收在循环头中，也必须保留其执行顺序，不能把更新漏掉。
- `continue` 在 for 中先执行更新再检查条件，在 while 中直接到条件，在 do/while 中到尾部条件；`break` 跳过剩余循环体和 for 更新，进入所属循环后续。
- 先执行后判断（C/C++ `do/while`）：`入口 -> 循环体 -> 条件`；条件为真重复，为假退出，循环体至少执行一次。通用“直到型”图有时采用条件为真退出的表达，不得直接套用而反转 C/C++ 条件含义。
- 无限循环不添加虚假的 no 出口；只有源码中的 break、return 等实际退出才形成离开路径。嵌套时 break/continue 绑定最近适用结构，switch 内 break 不能误跳出外层循环。

### 路径与版式规范

- 阅读方向优先自上而下、分支自左向右；主流程保持稳定竖直轴线。回边和退出边允许逆向绕行，不能为保持方向而修改控制流。
- 同类、相近内容的符号使用一致尺寸、字体和间距；长条件按内容扩展，不强求所有形状宽高完全相同。
- 同一判断的兄弟分支首节点尽量在同一高度，表达可比较的分支关系。左右并排不表示并发，不得把源码顺序调用改画成并行执行。
- 默认每个函数保留一个 Start 和一个公共 End。多个 return 分别保留并连接公共 End，不要求修改源码为单一 return；无正常退出的无限循环不得伪造到 End 的连线。
- “单入口、单正常出口”用于可继续执行的结构化子流程；提前退出和 goto 需单独建模，不能为了满足版式约定删除、改接或隐藏它们。
- 进入真实目标的有向连接只在目标端保留一个方向箭头；进入隐形布线锚点的线段不画箭头，由公共出边继续指向真实目标。不在同一路径重复加箭头或使用双向箭头。多分支在公共后续步骤前清楚合流，不能与循环回边混为一条不明路径。
- 顺序连接能直连就直连；避障和回边采用必要的正交折线。优先通过分支顺序、间距、侧通道消除交叉，不让边穿过无关节点；剩余交叉必须明确不连接，合流必须明确连接。
- 图过密时优先扩大空间或拆为可追溯的子流程，不以删减分支换取无交叉。无法解决的交叉和重叠需列为残留问题，不得宣称已完全满足规范。

### 规范来源与适用范围

结构分类与阅读方向参考用户提供的万兴图示文章摘录：[知乎原文](https://zhuanlan.zhihu.com/p/347119698)，作者：万兴图示。此处为结合代码控制流改写的项目约定，非文章全文转载，也不宣称为国家或国际标准。原文及配图著作权归原作者；本规范不复制配图。发生冲突时，以源码真实执行语义及本项目明确约定为准。

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

- Assign visible edge labels consecutive sequence numbers starting at 1, with no duplicates or gaps.
- Leave the outgoing edge of a simple merge connector unlabeled when it has no semantic text. Keep the connector and edge in the control-flow graph; do not delete them to hide a label.
- Normalize numbering after deciding which connector labels are omitted, not only in the renderer. Preserve meaningful merge-exit labels such as `loop` or `return` and give them a visible sequence number.
- Use the same normalized labels in draw.io, optional Mermaid/SVG/PNG, path reports, and analysis. Unlabeled connector edges remain in the graph but contribute no number to path sequences; internal cell IDs need not match visible numbers.
- Example: if two sequence-only merge exits previously consumed 9 and 13 in a 14-edge diagram, the remaining visible labels must be 1 through 12, not 1 through 14 with gaps.
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
- Merge simple jump edges only when they have the same semantic target: break reaches its enclosing construct's exit, while continue reaches its loop condition/update. Never merge them merely because a process node is nearby.
- Merge only switch-case exits that normally leave the switch through one invisible routing junction before entering the next ordinary node; preserve fallthrough and return/continue/goto targets separately.
- Reserve vertical whitespace after loops with break exits to keep merge lines away from process boxes.
- Include all edge waypoints in preview bounds so long side routes and labels are not clipped.
- Avoid crossing branch edges by placing then/yes branches to the left and else/no branches to the right.
- Keep one dominant downward spine for the normal path of each function.
- Connect an aligned return node downward through the final terminal junction to End when the intervening corridor is clear; a single terminal path may connect directly. Use a side route only when needed to avoid other shapes or conflicting paths; do not add a large detour solely because the edge is labeled `return`.
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

## 绘制与验收细节

- 图形、文字和连线应作为 draw.io 的可编辑对象保存，不用整张截图代替流程图。
- 同类节点保持一致的字体、线宽和尺寸基准；长条件按逻辑换行并扩展节点，不能截断源码条件或用过小字体挤入。
- 合流锚点保持不可见、无文字，不作为额外处理步骤。入边应连续汇入，公共出边连接下一节点；不显示黑点，不在锚点处重复画箭头。
- 连线采用正交折线，进入真实节点的箭头明确落到目标边界。标签放在有足够长度的直线段旁，与节点、合流位置、箭头和其他标签留出间隔；必要时使用白色标签背景和偏移。
- 保留 `yes/no`、`case/default`、`loop`、`break` 等分支含义及内部的 `return/throw` 语义。节点已写明返回动作时，出边只显示编号；公共出口短线不重复写 `return`。隐藏简单合流出边编号不能改变控制流。
- 修改已有图时保留未涉及节点、边和标识符，优先局部调整，避免无关布局变化。

交付前逐项检查：

1. `.drawio` 可以解析，节点和边可编辑，结构校验无错误；警告逐项复核并说明残留问题。
2. 对照源码确认条件分支、循环回边、提前退出和公共后续步骤没有丢失或误连。
3. 收集所有非空边标签的编号，确认排序后恰好为 `1..N`，且每条有语义的边仍有对应标签。
4. 简单合流出边保持无编号；编号重排同步到本次要求生成的路径报告和分析文件。没有重新生成的旧辅助文件不得声称已同步。
5. 在 draw.io 实际渲染中分别检查全图和局部细节，重点检查合流点、长条件、侧向通道、return 到 End、标签间距和画布裁剪。
6. 若 draw.io 渲染工具不可用，明确标注只完成 XML/结构检查或替代预览检查，不能把替代预览当作 draw.io 验收结果。

## draw.io Rendering Rules

### XML 生成与连线

使用 draw.io 原生 XML 进行程序化绘制，默认写为未压缩 `.drawio`：`mxfile > diagram > mxGraphModel > root`。保留 `id=0` 根单元和 `id=1` 默认图层。每个节点为独立 `mxCell vertex=1`，每条连线为独立 `mxCell edge=1`，而不是在 XML 中嵌入整张流程图图片。

- 使用 XML 库构造和序列化内容，不拼接未经转义的源码文本。节点保存位置和宽高，边通过唯一 `source/target` ID 引用端点，不能仅靠坐标或视觉接触表达连接。
- 默认使用正交路由 `edgeStyle=orthogonalEdgeStyle`；必要时在边的 `mxGeometry` 中添加 `Array as=points` 和 `mxPoint` 航点。多入口/出口时设置 entry/exit 锚点，并随节点尺寸调整航点。
- 进入真实节点的边使用 `startArrow=none;endArrow=block;endFill=1`，只在目标端显示箭头；进入隐形 merge 锚点的边使用 `endArrow=none`。普通控制流使用实线；虚线注释不得冒充实际执行路径。
- draw.io 支持跳线桥与断口，但本 skill 按用户约定显式设置 `jumpStyle=none`。通过分支顺序、间距、独立侧通道和航点消除交叉，不启用跳线桥掩盖问题。
- 几何相交不表示连接：相交处不加实心圆，不拆成公共图节点，也不因几何相交而改变 source/target。无法消除的交叉必须记录为残留缺陷，不能标记为验收通过。
- 实际合流表示“连接”：多条边显式指向同一不可见 merge 节点，再由该节点连接公共后续。不要只让两条线在坐标上碰到而缺少图连接；最终出口只以一条向下箭头进入 End。
- 独立连线长距离共线时应分开侧通道，仅在真实共同后继前保留必要的短合流。检查折点、节点边界和边标签的间距，不能靠跳线桥解决重叠。
- 在 draw.io 中核实实际连线、箭头及标签；Pillow 等替代预览不能替代原生渲染验收。结构检查仍需记录真实交叉和重叠，XML 合法不等于布局已验收。

下面是 root 内的一条边示例，前提是 `n1`、`n2` 已作为节点定义；它不是独立可打开的完整文件。完整文件还需上述容器与根单元：

```xml
<mxCell id="e1" value="1 yes" parent="1" edge="1"
        source="n1" target="n2"
        style="edgeStyle=orthogonalEdgeStyle;html=1;startArrow=none;endArrow=block;endFill=1;jumpStyle=none;labelBackgroundColor=#FFFFFF;">
  <mxGeometry relative="1" as="geometry">
    <Array as="points">
      <mxPoint x="320" y="240" />
      <mxPoint x="320" y="360" />
    </Array>
  </mxGeometry>
</mxCell>
```

格式与样式依据：[draw.io XML 导出说明](https://www.drawio.com/docs/manual/export/export-to-xml/)、[官方生成样式参考](https://www.drawio.com/docs/reference/diagram-generation/style-reference/)。XML 结构合法、控制流语义正确、实际渲染清楚是三项独立验收要求；添加 XML 样例或规范并不代表转换器已完整实现全部规则。

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
- `for`: model initialization once, then condition, body, update, and condition again. `yes` enters the body; normal body exit and `continue` execute update before the next test; `no` and `break` leave the loop without executing update. A compact loop header must preserve these semantics.
- Infinite `for (;;)` / `while (1)` / `while (true)`: keep the loop node but do not draw a false/no exit. Route only a real terminating statement to End.
- `while`: test the condition before the body; `yes` enters the body, normal body exit and `continue` return to the condition, and `no` exits. There is no implicit for-style initialization or update.
- `do while`: draw the body first, then the condition diamond. `yes` loops back to the body; `no` exits.
- `switch`: use one diamond. Each meaningful case body is an outgoing branch. Remove a top-level trailing `break` instead of drawing a break node. Combine cases with no action into one labeled branch, add `no match` when no `default` exists, align case bodies horizontally, and merge them through an invisible junction.
- `break`: exits the nearest loop or switch and connects to the statement after that construct.
- `continue`: targets the nearest loop's update for `for`, condition for `while`, or trailing condition for `do while`.
- `goto`: connects directly to the matching label and does not fall through to the next statement.
- Label: acts as a merge point, then continues downward through cleanup or subsequent statements.
- `return`: terminates at the function End, optionally through the final downward terminal junction, and never merges into later executable statements.
- `throw`: connects directly to End unless a local `catch` branch is modeled.
- Known non-returning calls such as `exit`, `abort`, and `osThreadTerminate` connect to End with a `terminate` edge. Review `osThreadTerminate` when it may target another thread and return.
- `try/catch`: draw the try body as normal flow and each catch as a labeled side branch. Keep catch branches orthogonal and merge after the catch body when execution can continue.

## Semantics

- `return` terminates the current function flow; a local routing junction may combine equivalent terminal paths before End without creating another executable return.
- `break` exits the nearest loop or switch.
- `continue` runs the nearest loop's `for` update before its next condition test; in `while` and `do while` it goes directly to that loop's condition.
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

- A path is a complete Start-to-End traversal represented by its visible edge numbers. Unlabeled merge connectors are traversed but omitted from the numeric sequence.
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
