# 固定验收样例

这是一组专门构造的 C 控制流样例，不是业务项目代码、真实硬件驱动或已经执行的 UT/集成测试。用于复核源码到图的关系、布局和渲染。

## 三个图形基线

| 样例 | 验证重点 | 产物 |
| --- | --- | --- |
| [retry_write.c](retry_write.c) | 5 条连续声明/赋值合框；循环回边与 break 分开；跳过延时后正确合流 | [draw.io](baselines/retry_write/retry_write.drawio)、[SVG](baselines/retry_write/retry_write.svg)、[预览](baselines/retry_write/retry_write.preview.png)、[自检](baselines/retry_write/retry_write.self-check.md) |
| [multiple_returns.c](multiple_returns.c) | 5 个 return 保留，独立通道在 End 上方合流，只向下进入一次 End | [draw.io](baselines/select_limit/select_limit.drawio)、[SVG](baselines/select_limit/select_limit.svg)、[预览](baselines/select_limit/select_limit.preview.png)、[自检](baselines/select_limit/select_limit.self-check.md) |
| [control_flow.c](control_flow.c) 中的 `for_continue_case` | 初始化只执行一次；continue 和正常路径先进入更新，再回条件 | [draw.io](baselines/for_continue_case/for_continue_case.drawio)、[SVG](baselines/for_continue_case/for_continue_case.svg)、[预览](baselines/for_continue_case/for_continue_case.preview.png)、[自检](baselines/for_continue_case/for_continue_case.self-check.md) |

[cases.json](cases.json) 保存独立结构预期：判断、返回、回边和隐形合流点数量，以及赋值合框要求。`baselines/` 保存已核对的图和预览，不是转换命令的默认输出目录。

## 高风险语义覆盖

`control_flow.c` 还包含：for 的 break、switch 内 break/continue、内层循环 break、向前清理 goto、向后 goto、跨块 goto、带自增/自减和函数调用的短路条件、嵌套 return、无限 for、do/while continue。

对应测试直接核对可执行后继和跳转目标，不仅验证 XML 可解析。缺失/重复标签、for 字符串中含分号和常真条件另有独立用例。短路表达式整体保留，比较有序 token，既不拆成无条件调用，也不声称已经执行 C 表达式。

## 运行检查

从仓库根目录执行：

```bash
python -B -m unittest discover -s code2flowchart/tests -v
```

验收检查包括：

- 重新生成三个 `.drawio/.svg` 并与已核对基线比对，忽略平台换行差异，不自动覆盖。
- 独立检查控制结构数量、连续赋值合框、不可见锚点、`jumpStyle=none`、锚点入出线中心一致，以及 End 的单一向下箭头。
- 对基线执行结构和几何检查，错误或警告均导致失败。
- PNG 是人工视觉复核证据，不做逐像素 CI 比对；自动检查不能代替实际看图。

可选的 C 语法检查，不链接或执行被测函数：

```bash
gcc -std=c99 -Wall -Wextra -pedantic -fsyntax-only code2flowchart/examples/acceptance/control_flow.c code2flowchart/examples/acceptance/retry_write.c code2flowchart/examples/acceptance/multiple_returns.c
```

## 更新基线

先生成到临时评审目录，避免无意覆盖已核对结果：

```bash
python code2flowchart/scripts/code2flowchart.py code2flowchart/examples/acceptance/retry_write.c --function retry_write --svg --out-dir code2flowchart/output/acceptance-review
python code2flowchart/scripts/validate.py code2flowchart/output/acceptance-review/retry_write/retry_write.drawio --strict
```

依次对照源码、结构预期和新旧图的差异。有视觉能力时必须查看最新完整图和合流/回边/End 的局部；优先 draw.io 原生渲染，不可用时明确记录替代方式。确认没有语义与视觉退化后，再主动更新基线、预览及 `.self-check.md`，并重跑测试。

不要仅因快照测试失败就更新快照；独立结构预期发生变化时也必须说明源码依据。`for` 显式展开会改变边编号，相关路径、分析及测试设计需要同轮更新。`--detail-level` 保留兼容，但不再按嵌套 return 自动编造功率发送或回读子流程。

## 本轮验证边界

三个样例均执行了源码核对、严格校验及 Chrome 157.0.8103.78 的完整/局部 SVG 渲染检查，另通过 GCC C99 语法检查。第一轮发现普通隐形合流点的 2 像素断口，统一中心端点后第二轮已复查。

没有执行 C 链接、单元测试、外设操作或实板时序验证；Chrome SVG 渲染也不等于 draw.io 原生渲染。只有可见函数控制流与当前预览在本次验收范围内。
