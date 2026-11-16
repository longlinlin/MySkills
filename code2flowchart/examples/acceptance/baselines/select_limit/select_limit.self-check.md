# select_limit 流程图自检

- 范围：[源码](../../multiple_returns.c) 的 `select_limit` 可见控制流，无宏或外部调用。
- 图文件：[select_limit.drawio](select_limit.drawio)。
- 总结：PASS（仅限本样例的可见控制流与替代渲染）。

| 阶段 | 结果 | 证据 |
| --- | --- | --- |
| 源码核对 | PASS | 4 个判断、5 个 return 及其分支结果均保留；提前返回不进入后续判断 |
| 严格校验 | PASS | `validate.py select_limit.drawio --strict`，退出码 0，0 错误、0 警告 |
| 视觉检查 | PASS | Chrome 157.0.8103.78 渲染当前 SVG，实际查看[完整图](select_limit.preview.png)和[End 局部](select_limit.detail.png) |
| C 语法检查 | PASS | GCC `-std=c99 -Wall -Wextra -pedantic -fsyntax-only`，退出码 0 |

## 检查结果

各返回路径保留独立远端通道，在最后一个返回下方按顺序汇入主线，只有一个向下箭头进入 End。公共短线无重复 return 标签、无黑点，合流线连续；当前未见穿框、交叉、标签遮挡或裁切。

## 未验证范围

数值仅用于布局验收，没有工程需求含义。未运行 C 单元测试或验证真实业务边界；未验证 draw.io 原生渲染。[SVG](select_limit.svg) 与 PNG 是替代预览，不是运行日志或覆盖率证据。
