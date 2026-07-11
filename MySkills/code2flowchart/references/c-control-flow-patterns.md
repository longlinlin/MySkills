# C/C++ Control Flow Pattern Reference

Use this reference for flowcharts modeled after procedural C/C++ functions with retry loops, cleanup paths, task dispatchers, labels, hardware-style calls, iostream/stdout-style calls, or similar branch-heavy code. The examples below are drawn from an embedded C test file, but the drawing patterns are not STM32-specific and can also guide C++ member functions with similar control flow.

## 中文说明

本文件总结嵌入式 C/C++ 函数常见控制流画法，重点服务“代码转流程图”，不是项目架构分析。

适用场景包括：重试循环、等待超时、`goto` 清理出口、任务派发函数、`switch/case` 分支、硬件读写、HAL/驱动调用、RTOS 任务创建和终止。画图时要保留会影响外部行为的语句，例如打开/关闭硬件资源、设置状态寄存器、延时、错误处理和任务终止。

如果宏看起来只是包装硬件动作，例如 `__OPEN_PLCIO`，应画成普通处理节点；如果宏可能隐藏 `return/goto/break` 等控制流，应标记为不确定并要求展开后再确认。

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

## Macro And Preprocessor Handling

- Treat simple hardware/action macros as process nodes when their expanded body is not needed for local control flow.
- Treat macros that may contain `return`, `goto`, `break`, `continue`, `do { ... } while (0)`, or hidden `if` blocks as uncertain until expanded.
- Preserve visible `#if`, `#ifdef`, and `#else` differences as notes or partial paths when the active build configuration is unknown.
- Do not merge two preprocessor variants into one confident path unless the active configuration is provided.
- If a macro guards cleanup or retry behavior, prefer expanding that macro or isolating a smaller function before accepting the diagram.

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
