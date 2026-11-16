# 单元测试与可选函数说明

Automated Detailed Design and Unit Test generation from C/C++ function analysis. Consumes `analysis.json` produced by `code2flowchart.py` and produces DD/UT artifacts.

## 中文说明

本文是 `code2flowchart` 主技能的 UT 模式说明，不是独立技能。基于函数分析结果生成测试设计文档和待补齐的 GoogleTest/Unity 骨架，函数详细设计文档（DD）仍为按需输出。

生成 UT 前读取 [代码与测试检查规则](code-test-checklists.md)，落实其中的单元测试和证据要求。先确认需求/源码、候选路径可行性、真实类型与隔离边界，再补齐输入、边界、故障注入、mock 返回序列、断言和状态复位。DD 不必先生成；用户只要求测试时不附加无关文档。

时序与真实组件集成按[集成测试模式](integration-test-design.md)处理，不能将全部 mock 的 UT 直接改名为集成测试。

## When to Use

Use this mode when UT is requested and source/analysis are available. Request `--ut` or use an existing `.analysis.json`; `--all`, DD and PNG are not prerequisites.

**Use for:**
- Generating optional function-level DD descriptions grounded in selected source
- Designing UT cases from reviewed graph paths, parameter classes and boundaries
- Generating draft GoogleTest or Unity skeletons; compilation and execution require real project integration
- When the user asks for "详细设计", "单元测试", "DD", "UT", "test case design"

**Do NOT use for:**
- Functions that fail to parse (fix code2flowchart issues first)
- Architecture/system-level design (this is function-level only)

## Workflow

### Mode 1: UT Without Unrelated Outputs

```bash
python code2flowchart/scripts/code2flowchart.py source.c \
    --function target_func \
    --analysis --ut --validate \
    --project-prefix SWDD_CHARGE
```

This parses source, generates the flowchart and analysis, validates structure, and writes UT drafts. Run the main skill's strict and post-generation checks for the diagram. Add `--dd` only when requested; `--all` additionally requires Pillow and creates every artifact.

### Mode 2: Standalone (from existing analysis.json)

```bash
# Generate DD only
python code2flowchart/scripts/dd_generator.py code2flowchart/output/func/func.analysis.json --project-prefix SWDD_CHARGE

# Generate UT only
python code2flowchart/scripts/ut_generator.py code2flowchart/output/func/func.analysis.json --project-prefix SWDD_CHARGE
```

## Output Artifacts

| File | Content |
|------|---------|
| `<fn>.dd.md` | Detailed Design document: Function ID, declaration, description, constraint, verification, parameter table, called-by/callings, function evaluation (branch num, cyclomatic complexity, interactivity, criticality), remark, flowchart link |
| `<fn>.ut.md` | Unit Test design: Test case overview table, detailed test cases per path (ID, sequence, design method, test method, environment, goal, pre/post conditions) |
| `<fn>.ut.cpp` | GoogleTest draft: `TEST_F()` with explicit `GTEST_SKIP`; configure FFF/gMock only from real declarations |
| `<fn>.ut.c` | Unity draft: `test_*()` with explicit `TEST_IGNORE_MESSAGE`; configure CMock from real declarations |

## DD Document Specification

### Function ID Convention

```
SWDD_<COMPONENT>_F<SEQ>
```

- `SWDD` — Software Detailed Design prefix (fixed)
- `<COMPONENT>` — Component/module name (configurable via `--project-prefix`)
- `F<SEQ>` — Function sequence number (3-digit, auto-incremented)

Example: `SWDD_CHARGE_F001`, `SWDD_CHARGE_F002`

### DD Sections

| Section | Source | Auto/LM |
|---------|--------|---------|
| Function ID | `--project-prefix` + auto-number | Auto |
| Function Declaration | `analysis.json` → `signature` | Auto |
| Description | `analysis.json` → `description_draft` | Needs LLM enrichment |
| Constraint | Placeholder | Needs LLM enrichment |
| Verification Criteria | Placeholder | Needs LLM enrichment |
| Parameter Table | `analysis.json` → `parameters` | Auto |
| Called By | `analysis.json` → `called_by_in_file` + cross-file search | Auto + Agent |
| Callings | `analysis.json` → `calls` | Auto |
| Branch Num | Count of decision nodes | Auto |
| Cyclomatic Complexity | M = N + 1 | Auto |
| Complexity Level | Low (<2), Medium (2-10), High (>10) | Auto |
| Interactivity | Non-deduplicated call count | Auto |
| Criticality | Called-by count | Auto |
| Flowchart | Links to .drawio/.png | Auto |

### Cross-File Caller Search (Called By)

`code2flowchart.py` only detects callers within the single source file. The agent MUST perform a cross-file search to find all callers across the project:

1. **Identify the project root** — ask the user or infer from the source file path (e.g., `d:\project\code\`).
2. **Search for callers** — use `rg` to search `*.c`, `*.h`, `*.cpp`, `*.hpp` files for function name references:
   ```bash
   rg -n -F "charge_i2c_send" -g '*.c' -g '*.h' -g '*.cpp' -g '*.hpp' <project_root>/
   ```
3. **Filter results** — exclude the function's own definition and comments. A match is a caller if it appears in a function call context (e.g., `charge_i2c_send(...)` in another function body).
4. **Update DD** — if callers are found, list them as `- \`caller_func()\` in \`file.c\``. If none found, write `- (none detected in project)`.

### LLM Enrichment Rules

When the agent runs DD generation, it should:

1. **Description:** Read the function body from source. Describe: what it does, when it's called, main processing logic, external dependencies. Replace the `description_draft` with a 2-4 sentence engineering description.
2. **Constraint:** From the function logic, derive constraints: valid parameter ranges, state preconditions, timing requirements, ordering dependencies. Example: "`chip_addr` must be a valid 7-bit I2C address (0x00-0x7F). `send_buf` must contain exactly 3 bytes."
3. **Verification Criteria:** Based on function exits and side effects: "After call, `status` reflects the final I2C transaction result. On success: `LPI2C_STATUS_OK`. On failure after max retries: last error status."
4. **Called By (cross-file):** Perform the cross-file caller search described above. Update the `called_by_in_file` field with project-wide results before generating the DD document. This is critical because `code2flowchart.py` only scans the single input file.

## UT Document Specification

### Test Case ID Convention

```
<Function ID>_UT<SEQ>
```

Example: `SWDD_CHARGE_F001_UT001`

未提供正式 Function ID 或前缀时使用 `LOCAL_F001_UT001` 等草稿编号，并在交付前确认项目编号。正式 ID、配置前缀和本地编号在设计文档及两种骨架中必须一致。

### Design Methods

由真实接口和源码选择，可组合需求驱动、等价类、边界值、错误推测和故障注入。每种方法写明实际数据及选择理由；不能按用例序号分配，不能把正常 return 认作异常，把 break 认作首次成功，或把一次回边认作重试耗尽。

生成器只给出待复核的需求分析草稿，不自动安排静态分析或资源占用测试。所有候选路径需核对可行性，并根据参数和依赖补充独立用例。

### Test Environments

环境默认 TBD，按真实工程确认 host、SIL、PIL 或 HIL。只有主机上的 mock 测试时，不声称已经验证硬件行为或实机时序。

### LLM Enrichment Rules

The agent should fill in for each test case:

1. **Test Goal:** Read the path conditions from `analysis.json`. Describe what this specific path verifies. Example: "Verify temperature state transition from INIT to 400W on first cycle, charge_enter_shutdown NOT called."
2. **Precondition:** From path conditions + function logic, state the initial state and mock setup.
3. **Action:** The specific function call with concrete argument values.
4. **Expected Result:** What assertions should pass.
5. **Post-condition:** Final state after test execution.

## 骨架补齐规则

- 复用项目实际使用的 GoogleTest/FFF/gMock 或 Unity/CMock，不混用不同框架不存在的宏。
- 未读取依赖函数头文件前，不生成 `FAKE_VALUE_FUNC` 的参数列表，不给所有依赖套 I2C 类型或成功返回值。
- 每个用例明确准备、实际调用与断言，复位全部 mock 和共享状态。调用顺序只验证设计要求的顺序。
- 新骨架默认 `GTEST_SKIP()` 或 `TEST_IGNORE_MESSAGE()`，补齐真实调用、输入和有效断言后才能移除；不得以零退出码将空骨架报为通过。
- 覆盖率来自真实编译运行报告，设计稿保持 DRAFT，未执行保持 NE。代码生成不是编译、测试或 100% 覆盖率的证据。

## Review Checklist

Before accepting DD/UT output:
- [ ] All DD sections are filled (no empty placeholders except Constraint where N/A)
- [ ] Function ID is unique and follows naming convention
- [ ] Parameter table has correct I/O directions and types
- [ ] 候选路径已按可行性处置，额外边界和故障用例也有源码依据
- [ ] Sequence numbers match edge labels in the .drawio diagram
- [ ] Test goals are path-specific (not generic)
- [ ] 不以 `branch_path_count` 或用例数量代替分支覆盖率
- [ ] 骨架未完成时保持跳过，实际执行状态及证据独立记录
- [ ] 只有执行过项目构建和测试命令，才声称代码已编译或测试通过
