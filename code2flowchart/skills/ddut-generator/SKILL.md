---
name: ddut-generator
description: Generate Detailed Design (DD) documents and Unit Test (UT) design + skeleton code from C/C++ functions. USE THIS SKILL after code2flowchart has produced analysis.json. Generates .dd.md (detailed design), .ut.md (test case design), .ut.cpp (GoogleTest+FFF skeleton), and .ut.c (Unity+CMock skeleton). Supports configurable Function ID prefix via --project-prefix.
---

# DD/UT Generator for code2flowchart

Automated Detailed Design and Unit Test generation from C/C++ function analysis. Consumes `analysis.json` produced by `code2flowchart.py` and produces DD/UT artifacts.

## 中文说明

这个子技能基于 code2flowchart 的函数分析结果，自动生成详细设计文档（DD）和单元测试设计文档+骨架代码（UT）。输出包括：函数详细设计文档、测试用例设计文档、GoogleTest+FFF 测试骨架、Unity+CMock 测试骨架。

## When to Use

Trigger this skill **after** `code2flowchart.py` has succeeded with `--all` (which implies `--dd --ut`), or run the scripts directly against an existing `analysis.json`.

**Use for:**
- Generating SW-DD (Software Detailed Design) documents per automotive/embedded standards
- Generating UT test case design documents with path coverage
- Generating compilable test skeleton code (GoogleTest or Unity+CMock)
- When the user asks for "详细设计", "单元测试", "DD", "UT", "test case design"

**Do NOT use for:**
- Functions that fail to parse (fix code2flowchart issues first)
- Architecture/system-level design (this is function-level only)

## Workflow

### Mode 1: Full Pipeline (recommended)

```bash
python code2flowchart/scripts/code2flowchart.py source.c \
    --function target_func \
    --all --dd --ut \
    --project-prefix SWDD_CHARGE
```

This runs the full pipeline: parse → flowchart → validate → DD → UT.

### Mode 2: Standalone (from existing analysis.json)

```bash
# Generate DD only
python code2flowchart/scripts/dd_generator.py output/func/func.analysis.json --project-prefix SWDD_CHARGE

# Generate UT only
python code2flowchart/scripts/ut_generator.py output/func/func.analysis.json --project-prefix SWDD_CHARGE
```

## Output Artifacts

| File | Content |
|------|---------|
| `<fn>.dd.md` | Detailed Design document: Function ID, declaration, description, constraint, verification, parameter table, called-by/callings, function evaluation (branch num, cyclomatic complexity, interactivity, criticality), remark, flowchart link |
| `<fn>.ut.md` | Unit Test design: Test case overview table, detailed test cases per path (ID, sequence, design method, test method, environment, goal, pre/post conditions) |
| `<fn>.ut.cpp` | GoogleTest + FFF skeleton: `TEST_F()` per path with Arrange/Act/Assert structure, `@Test Case ID` doxygen headers |
| `<fn>.ut.c` | Unity + CMock skeleton: `test_*()` per path with Arrange/Act/Assert structure, `@Test Case ID` comment headers |

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
2. **Search for callers** — use `grep` to search `*.c`, `*.h`, `*.cpp`, `*.hpp` files for function name references:
   ```bash
   grep -rn "charge_i2c_send" --include="*.c" --include="*.h" <project_root>/
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

### Design Methods

Assigned per path based on path characteristics:
- **Error Guessing:** Paths with break/return exits (abnormal flow)
- **Equivalence Classes:** First path (normal/typical flow)
- **Boundary Values:** Last path (edge conditions)
- **Analysis of requirements:** Paths with loops/retries

### Test Environments

Configurable; default: `software-in-the-loop`
Options: `model-in-the-loop`, `software-in-the-loop`, `processor-in-the-loop`, `hardware-in-the-loop`

### LLM Enrichment Rules

The agent should fill in for each test case:

1. **Test Goal:** Read the path conditions from `analysis.json`. Describe what this specific path verifies. Example: "Verify temperature state transition from INIT to 400W on first cycle, charge_enter_shutdown NOT called."
2. **Precondition:** From path conditions + function logic, state the initial state and mock setup.
3. **Action:** The specific function call with concrete argument values.
4. **Expected Result:** What assertions should pass.
5. **Post-condition:** Final state after test execution.

## Test Code Templates

### GoogleTest + FFF Pattern

```cpp
/**
 * @Test Case ID: SWDD_CHARGE_F001_UT005
 * @Function ID: SWDD_CHARGE_F001
 * @Function Name: charge_i2c_send
 * @Sequence: 1-2-3-4-12-13-14
 * @Case Design Method: Equivalence Classes
 * @Test Environment: software-in-the-loop
 * @Test Method: Requirement-based test
 * @Test Goal: Verify first I2C send returns OK immediately
 * @Precondition: lpi2c_send returns LPI2C_STATUS_OK
 * @Action: Call charge_i2c_send(chip=0x50, reg=0x00, data=0x1234)
 * @Expected Result: Returns LPI2C_STATUS_OK, osDelay NOT called
 * @Post-condition: status == LPI2C_STATUS_OK
 */
TEST_F(ChargeI2cSendTest, SWDD_CHARGE_F001_UT005)
{
    // Arrange
    FSF_MOCK(lpi2c_send);
    FSF_MOCK(osDelay);
    EXPECT_CALL(FSF_MOCK_OBJ(lpi2c_send), lpi2c_send(...))
        .WillOnce(Return(LPI2C_STATUS_OK));
    EXPECT_CALL(FSF_MOCK_OBJ(osDelay), osDelay(_)).Times(0);

    // Act
    LPI2C_Status_t result = charge_i2c_send(0x50, 0x00, 0x1234);

    // Assert
    EXPECT_EQ(LPI2C_STATUS_OK, result);
}
```

### Unity + CMock Pattern

```c
/**
 * @Test Case ID: SWDD_CHARGE_F001_UT005
 * ...
 */
void test_SWDD_CHARGE_F001_UT005(void)
{
    // Arrange
    lpi2c_send_IgnoreAndReturn(LPI2C_STATUS_OK);
    osDelay_Ignore();

    // Act
    LPI2C_Status_t result = charge_i2c_send(0x50, 0x00, 0x1234);

    // Assert
    TEST_ASSERT_EQUAL(LPI2C_STATUS_OK, result);
}
```

## Review Checklist

Before accepting DD/UT output:
- [ ] All DD sections are filled (no empty placeholders except Constraint where N/A)
- [ ] Function ID is unique and follows naming convention
- [ ] Parameter table has correct I/O directions and types
- [ ] Test Case IDs map to actual paths in the flowchart
- [ ] Sequence numbers match edge labels in the .drawio diagram
- [ ] Test goals are path-specific (not generic)
- [ ] Path count matches `branch_path_count` in analysis.json
- [ ] Test code compiles (manual verification)
