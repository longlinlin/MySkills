# C/C++ Control Flow Pattern Reference

Use this reference for flowcharts modeled after procedural C/C++ functions with retry loops, cleanup paths, task dispatchers, labels, hardware-style calls, iostream/stdout-style calls, or similar branch-heavy code. The examples below are drawn from an embedded C test file, but the drawing patterns are not STM32-specific and can also guide C++ member functions with similar control flow.

## 中文说明

本文件总结嵌入式 C/C++ 函数常见控制流画法，只服务代码转流程图，不用于推断项目架构。下文函数名是模式示例，不代表已扫描用户项目。

重试、等待超时、`goto` 清理、任务派发和 `switch/case` 必须保留真实执行关系。打开或关闭硬件资源、状态寄存器设置、延时、错误处理和任务终止会影响外部行为，不应为简化图形而删除。

硬件动作宏可在确认其含义后保留为处理节点；可能隐藏跳转的宏需要展开或标记不确定。RTOS API 是否终止当前任务必须按实际参数及实现确认，不能只根据函数名判断。

## Function Inventory

- `startTest(uint8_t type)`: sets `testReg`, guards task startup with `flag_intest == 0`, creates the communication test task.
- `commtest(void const *argument)`: infinite task loop with a `switch (type)` dispatcher. Each case calls one test routine or exits the switch, then resets `testReg`, clears `flag_intest`, and terminates the task.
- `onofftest(void)`: opens PLCIO, checks `PLC_POWERON()` in a retry loop, optionally jumps to cleanup, waits for `testReg` to clear, then closes PLCIO.
- `stoptest(void)`: same structural pattern as `onofftest`, but checks `PLC_SGATE()`.
- `almtest(void)`: opens PLCIO, turns alarm on, waits for clear/timeout, turns alarm off, sets `testReg`, waits again, then closes PLCIO.
- `setpowtest(void)`: opens PLCIO, computes formatted set power in a retry loop, checks for `500`, optionally jumps to cleanup, waits for clear, then closes PLCIO.
- `realpowtest(void)`: opens PLCIO, computes DAC output, waits for clear/timeout, then closes PLCIO.
- `test_readREG(void)`: returns `testReg`.

## Drawing Priorities

- Treat `__OPEN_PLCIO` and `__CLOSE_PLCIO` as important process nodes, not ignorable macros.
- Treat `testReg == TESTREG_END` as an early-exit decision.
- Treat `retry == 0` as a timeout decision.
- Treat `osDelay(10)` as a delay/process node inside retry loops.
- Treat `PLC_*` reads and `HAL_*` calls as hardware interaction process nodes.
- Treat `osThreadCreate` and `osThreadTerminate` as task lifecycle process nodes.

## 宏与条件编译

- 简单硬件动作宏可保留名称，不凭空补画内部执行步骤。
- 宏可能含有 `return/goto/break/continue`、隐藏判断或 `do { ... } while (0)` 时，先确认展开内容；无法确认则标记部分验证。
- 活动编译配置不明时，不把 `#if/#else` 的两个版本混成一条确定路径。使用 `--define/--undef` 指定受支持的配置，其他条件先用项目编译器预处理。
- 宏影响重试或资源释放时，优先展开宏或缩小函数范围，再核对流程图。

## Common Patterns

### Guarded Task Start

Use this structure for `startTest`:

1. Assign requested test type.
2. Decision: `flag_intest == 0`.
3. Yes branch: set busy flag, store type, create task.
4. No branch: exit function.

### Infinite Task Dispatcher

Use this structure for `commtest`:

1. Start infinite loop `for (;;)` without a false/no exit edge.
2. Decision: `switch (type)`.
3. Use one branch per test routine and combine cases that perform no call into one `No test call` branch.
4. Omit top-level trailing `break` nodes and merge case exits through one connector.
5. Add `no match` when the switch has no `default` case.
6. After switch: reset register, clear flag, terminate task.
7. Connect `osThreadTerminate` to End with a `terminate` edge when it terminates the current task; otherwise route its normal return back to the loop.

### Retry Loop With Cleanup

Use this structure for `onofftest`, `stoptest`, and `setpowtest`:

1. `__OPEN_PLCIO` process.
2. Retry loop `for (retry = MAX_RETUR;;)`.
3. First decision: `testReg == TESTREG_END`.
4. Yes branch: `goto __end` or cleanup label.
5. Hardware/read decision such as `PLC_POWERON() == GPIO_PIN_RESET`.
6. Success branch: set `testReg = 0xff`, then break the loop.
7. Failure branch: decrement retry, then decision `retry == 0`.
8. Timeout branch: break the loop.
9. Normal retry branch: `osDelay(10)`, then loop back.
10. Optional second wait loop for register clear.
11. Label `__end:` merges early-exit and normal flow.
12. `__CLOSE_PLCIO` process before End.

### Wait-Only Retry Loop

Use this structure for repeated wait loops:

1. Decision: `testReg == TESTREG_END`.
2. Yes branch: break loop.
3. No branch: decrement retry.
4. Decision: `retry == 0`.
5. Yes branch: break loop.
6. No branch: `osDelay(10)`, then loop back.

## Goto And Labels

- Draw `goto __end` as a distinct red/orange process node.
- Draw `__end:` as a dashed label/merge node.
- Connect `goto __end` directly to `__end:` with a labeled edge.
- Do not let the goto node fall through to the next statement.
- After the label, continue normal downward flow into cleanup.

## Path Reporting

For this pattern family, `.paths.md` is especially useful:

- Early cancel paths should include the edge from `testReg == TESTREG_END` to `goto __end` or cleanup.
- Timeout paths should include the `retry == 0` yes branch.
- Success paths should include the hardware success branch and loop break.
- Dispatcher paths should show one path per `switch` case branch where practical.
