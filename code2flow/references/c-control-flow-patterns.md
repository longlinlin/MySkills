# C Control Flow Pattern Reference

Use this reference for flowcharts modeled after procedural C functions with retry loops, cleanup paths, task dispatchers, labels, hardware-style calls, or similar branch-heavy code. The examples below are drawn from an embedded C test file, but the drawing patterns are not STM32-specific.

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

## Common Patterns

### Guarded Task Start

Use this structure for `startTest`:

1. Assign requested test type.
2. Decision: `flag_intest == 0`.
3. Yes branch: set busy flag, store type, create task.
4. No branch: exit function.

### Infinite Task Dispatcher

Use this structure for `commtest`:

1. Start infinite loop `for (;;)`.
2. Decision: `switch (type)`.
3. One branch per `TESTREG_*` case.
4. Case body calls the matching test routine, then `break`.
5. After switch: reset register, clear flag, terminate task.
6. Route the infinite-loop back edge on the left.

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
