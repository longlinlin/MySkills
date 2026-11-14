# C 函数流程图调研与采用方案

本参考用于改进 C/C++ 单函数控制流转图，不扩展为架构图、调用关系图或通用绘图工具。调研日期：2026-11-13。以下区分来源事实与本项目的设计取舍；没有复制外部项目实现，也没有执行其下载程序。

## 查看的仓库和官方资料

| 来源 | 已核实内容 | 本项目采用或保留的做法 |
| --- | --- | --- |
| [cxx2flow README](https://github.com/Enter-tainer/cxx2flow/blob/master/README.md)、[控制流图实现](https://github.com/Enter-tainer/cxx2flow/blob/master/src/graph.rs) | 将语法结构转换为图，再清理辅助节点；`do…while` 使用循环体与末尾条件，辅助入口不是普通执行语句；`for` 的初始化、条件、更新分别建模 | 借鉴结构与显示分离：不画仅有 `do` 的处理框，保留不可见入口承接回边。核对 `continue` 时必须考虑循环类型，不能只看箭头是否回到某个菱形 |
| [yFlowGen 使用说明](https://github.com/toowaki/yFlowGen#how-to-run-yflowgenexe) | 提供紧凑显示、隐藏纯声明、禁用附加连接点、判断分支方向等选项，并支持 Graphviz 输出 | 把内容删减和几何布局区分开。本项目仍显示声明、合并连续赋值，不擅自隐藏源码步骤；不显示黑色连接点 |
| [ExecFlow 官方示例](https://execflow.abhinesh.codes/flowchart-from-code) | 展示单函数转图、连续简单语句合框、提前返回分别终止，以及未完整解析部分的说明 | 保持单函数粒度和顺序语句合框。借鉴显式说明解析边界的做法，不采纳多个独立 End、可见连接圆点或固定三语句截断 |
| [draw.io 连线说明](https://www.drawio.com/docs/manual/connectors/)、[自动避障说明](https://www.drawio.com/docs/manual/connectors/connectors-auto-route/) | 固定端口与浮动端口行为不同；显式航点可以约束路径；自动避障主要针对形状，不能直接推导为所有边都无交叉 | 为每条导出边固定出入口，保持 draw.io 模型端点与 SVG 路径一致。手工修改图后仍需重新检查路径，不能把自动避障当作零交叉保证 |
| [Graphviz splines](https://graphviz.org/docs/attrs/splines/)、[concentrate](https://graphviz.org/docs/attrs/concentrate/) | 正交路由有端口及边标签方面的限制；边集中是独立的布局选项 | 不把 `splines=ortho` 当作自动解决问题的开关，不通过集中边来掩盖不同退出分支。暂不替换现有布局器 |
| [ELK libavoid](https://eclipse.dev/elk/reference/algorithms/org-eclipse-elk-alg-libavoid.html) | 专门处理节点位置不变时的避障布线，并提供交叉、共线路径、间距等独立选项 | 继续分别检查穿框、交叉、共线和间距。未来若引入独立路由器，应作为可验证的可选后端，而不是新增不透明的默认依赖 |

## 本项目当前绘图约定

1. 先保留源码控制流，再决定如何合框和布线。不能为了无交叉而删除 `return/break/continue` 或改变其目标。
2. 连续声明、赋值、自增自减按原顺序放进同一处理框；判断、循环、标签、退出和独立调用会结束该组。
3. 普通路径向下，循环回边放左侧，`break/goto` 退出放右侧。不同退出来源保留独立竖向通道，不捆成长线。
4. 同侧回环与退出使用统一的函数外边界基准，长距离提前返回绕在其跨过的循环外侧。最后的返回可在无障碍时直接向下。
5. 合流与 `do…while` 入口可使用不可见锚点，不画黑点，也不画只有语法关键字而无执行内容的处理框。
6. 所有 draw.io 边的出入口显式固定；SVG 与 draw.io 使用同一组逻辑路径端点。
7. 单一 `Start` 和 `End` 继续保留。所有退出与最终返回在 End 上方通过隐形锚点合流，再以唯一的向下箭头进入 End；合流区位于最后执行节点下方并预留回接空间。返回节点出线只显示编号，内部路径仍保留返回语义，公共短线不新增编号或返回动作。
8. 宏和外部调用不自动展开。图只反映当前函数可见流程；断言、配置和未知宏可能隐藏的行为必须说明。

这里的通道间距、不可见锚点和单一出口是本项目取舍，不宣称是所有来源共同遵循的标准。

## 本轮实际改动

- 删除可见的 `do` 处理框，改为不显示的循环入口，循环体仍在条件之前执行。
- 固定正常向下、回边和侧边出口的 draw.io 连接端口，并用测试核对它们与预览路径的端点。
- 终止路径保留独立的长距离通道，最终在 End 上方与最后一个返回合流，用唯一的向下箭头进入 End，不新增公共的返回步骤。
- 新增 [生成后自检技能](../skills/flowchart-self-check/SKILL.md)，要求 AI 在生成或修改图后核对源码、严格校验，并在具备视觉能力时实际查看最新渲染图，输出 `.self-check.md`。
- 移除缺少 Pillow 时生成纯白 PNG 的降级行为。请求 PNG 但缺少依赖时明确失败；已经生成的 draw.io/SVG 可继续使用，旧 PNG 不会被覆盖。
- 仅要求流程图时默认建议 `--svg --validate`，不再建议无条件生成所有 DD/UT 产物。

## 验证方法

- 自动测试控制流目标、连续赋值合框、不可见入口、端口一致性、缺失依赖时的失败状态及旧文件保护。
- 用 I²C 重试样例检查 `while no` 与 `break` 的独立通道。
- 用 Zephyr `ring_buf_item_get()` 检查提前返回与后续 `do…while` 的嵌套通道。
- 对 `.drawio` 运行 `validate.py --strict`，穿框、交叉和长距离共线警告都不能当作成功。
- 再把 SVG 或原生 draw.io 导出结果渲染成图片，检查黑点、文字、箭头和边间距；几何校验通过不等于已完成视觉检查。

本轮没有替换轻量解析器。完整宏展开、编译器扩展和复杂 C++ 语法仍需项目预处理或更完整的解析后端；本参考不将这些能力写成已经实现。

## 本轮验证结果

- `python -B -m unittest discover -s code2flowchart/tests -q`：30 项通过，包含所有返回在 End 上方合流、六条返回保持独立长通道、公共短线只有一支向下箭头、左右终止路径共同合流、单条提前返回的向下出口及导出标签检查。
- I²C 重试样例与 Zephyr `ring_buf_item_get()` 的优化版均通过 `validate.py --strict`：0 错误、0 警告。
- Zephyr 优化版 SVG 已由 Chrome 渲染为 PNG 并检查；这不是 draw.io 原生引擎的渲染验证。
- 本机未安装 Pillow。全产物管线测试模拟了 PNG 写入调用，另有测试验证缺少 Pillow 时失败且不生成空白图、不覆盖旧预览；未运行 Pillow 的正向位图渲染测试。
- `skill-creator/scripts/quick_validate.py` 因缺少 `PyYAML` 无法启动；新建自检子技能的元数据校验也受到同一限制，未为此增加依赖，不能宣称元数据自动校验通过。
- `git diff --check` 未发现空白错误；未执行 C 编译、Zephyr 运行或实板验证，未提交 Git。
