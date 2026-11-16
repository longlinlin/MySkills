# retry_write 流程图自检

- 范围：[源码](../../retry_write.c) 的 `retry_write` 可见控制流，无条件编译配置。
- 图文件：[retry_write.drawio](retry_write.drawio)。
- 总结：PASS（仅限本样例的可见控制流与替代渲染）。

| 阶段 | 结果 | 证据 |
| --- | --- | --- |
| 源码核对 | PASS | 5 条声明/赋值合框；while 重试、成功 break、可选延时与自增顺序均保留 |
| 严格校验 | PASS | `validate.py retry_write.drawio --strict`，退出码 0，0 错误、0 警告 |
| 视觉检查 | PASS | Chrome 157.0.8103.78 渲染当前 SVG，实际查看[完整图](retry_write.preview.png)和[局部图](retry_write.detail.png) |
| C 语法检查 | PASS | GCC `-std=c99 -Wall -Wextra -pedantic -fsyntax-only`，退出码 0 |

## 问题与修复

第一轮发现普通隐形合流点使用上下边界，留下约 2 像素断口。已统一所有入线、出线的中心端点，重新生成并检查第二轮完整图及局部。当前未见黑点、跨线、长距离捆线、穿框、裁切或多个箭头进入 End。

## 未验证范围

仅将外部函数作为黑盒调用，未验证发送和延时的实现。未链接或运行 C 测试、未访问外设；未验证 draw.io 原生渲染。[SVG](retry_write.svg) 和 PNG 仅表示当前转换器的替代预览，不是实测执行结果。
