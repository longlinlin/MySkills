# for_continue_case 流程图自检

- 范围：[源码](../../control_flow.c) 的 `for_continue_case` 可见控制流，无宏或外部调用。
- 图文件：[for_continue_case.drawio](for_continue_case.drawio)。
- 总结：PASS（仅限本样例的可见控制流与替代渲染）。

| 阶段 | 结果 | 证据 |
| --- | --- | --- |
| 源码核对 | PASS | 初始化仅一次；yes continue 跳过 total 更新，先执行 i++，再回到条件 |
| 严格校验 | PASS | `validate.py for_continue_case.drawio --strict`，退出码 0，0 错误、0 警告 |
| 视觉检查 | PASS | Chrome 157.0.8103.78 渲染当前 SVG，实际查看[完整图](for_continue_case.preview.png)和[合流局部](for_continue_case.detail.png) |
| C 语法检查 | PASS | GCC `-std=c99 -Wall -Wextra -pedantic -fsyntax-only`，退出码 0 |

## 问题与修复

原转换器把 for 三段收在判断框中，更新顺序无法从图的独立节点核对。现已分为初始化、条件与更新，测试直接验证 continue 和正常路径都经过 i++。第一轮预览发现普通隐形合流断口，统一中心端点后已重新生成并查看第二轮完整图及局部。

当前回边在左侧，循环退出在右侧，所有合流连续，没有黑点或跨线；End 只保留一条向下入线。

## 未验证范围

未实际运行 C 用例，没有数据流可行性或覆盖率证明；未验证 draw.io 原生渲染。[SVG](for_continue_case.svg) 与 PNG 是当前转换器的替代预览。
