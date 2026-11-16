# code2flowchart — 使用指南 / Usage Guide

## 概述 / Overview

code2flowchart 专注 C/C++ 代码转流程图，以及按需的单元测试、接口与时序集成测试设计。函数详细设计（DD）仍是可选辅助输出，不是必经流程。

以下命令从仓库根目录运行。安装到其他位置时，以实际技能目录定位脚本；默认输出位于技能自身的 `output/`，而不是运行命令时的工作目录。C/C++ 是当前支持的输入语言，其他语言文件仅为未实现的接口草稿。

## 快速开始 / Quick Start

### 1. 基础流程图转换

```bash
python code2flowchart/scripts/code2flowchart.py source.c --function target_func
```

产出：`code2flowchart/output/<function>/<function>.drawio`

### 2. 按需生成全部产物

```bash
python code2flowchart/scripts/code2flowchart.py source.c \
    --function target_func \
    --all \
    --project-prefix SWDD_MODULE
```

| flag | 说明 |
|------|------|
| `--all` | 生成全部产物并校验，包含 PNG、DD 和 UT；已隐含 `--dd --ut` |
| `--dd` | 生成详细设计文档 `.dd.md` |
| `--ut` | 生成单元测试文档+骨架代码 `.ut.md` `.ut.cpp` `.ut.c` |
| `--project-prefix` | 设置 Function ID 前缀，如 `SWDD_CHARGE` |

只需要流程图时，优先使用 `--svg --validate`，不必生成 DD/UT。`--preview` 和 `--all` 都需要 Pillow；缺少依赖时返回非零退出码，不再生成空白 PNG 占位图，已写出的 `.drawio` 和 SVG 保留。已有同名 PNG 不会被覆盖，也不能当作本轮成功输出。

### 条件编译

源码中存在 `#if/#ifdef/#elif` 时，需明确选择编译配置。例如：

```bash
python code2flowchart/scripts/code2flowchart.py source.c --function target_func --define ENABLED --undef LEGACY
```

可重复传入 `--define NAME` 和 `--undef NAME`。目前只识别常量条件及 `defined(...)` 与 `!`、`&&`、`||` 的组合；宏数值比较、头文件提供的未知宏等情况请先用项目编译器预处理源码。无法确定活动分支时转换器会报错，不生成混合两个配置的流程图。`--validate`、`--dd` 或 `--ut` 的执行步骤失败时，命令返回非零退出码。

## 在 Claude Code 中使用 / Using in Claude Code

直接粘贴 C/C++ 函数代码，说：

```
把这个函数转成流程图
```

代理会自动：
1. 保存代码 → 运行 `code2flowchart.py --svg --validate`
2. 严格校验 `.drawio`（`validate.py --strict`，错误和警告均需处理）
3. 视觉自查有效的 PNG 预览或浏览器渲染后的 SVG（7项缺陷检查），不得把未渲染的 XML 校验当作视觉检查
4. 展示结果，收集反馈（最多 5 轮）

### 生成后自动自检

生成或修改图后，使用本 skill 的 AI 必须继续读取[自检规则](references/flowchart-self-check.md)，执行源码核对和 `validate.py --strict`。具备视觉能力时实际查看最新渲染图，特别检查循环、提前返回与 End 上方合流；没有视觉能力或无法渲染时明确标记跳过。

检查结果保存在图旁的 `<basename>.self-check.md`，区分 `PASS/PARTIAL/FAIL`。仅能解析 XML、只检查旧截图，或存在未确认的控制流，都不能当成完整自检通过。这个步骤由 AI 执行，不是 Python CLI 自动调用视觉模型。

### 请求 DD/UT

```
对这个函数生成 DD 和 UT
```

代理会：
1. 先运行 `code2flowchart.py source.c --function target_func --dd --ut --project-prefix SWDD_MODULE`；不需要 PNG 时不用 `--all`
2. **跨文件搜索调用者**：`rg -n -F "函数名" -g '*.c' -g '*.h' -g '*.cpp' -g '*.hpp' <项目根目录>`
3. 生成 `.dd.md`（含完整调用关系）
4. 生成 `.ut.md` + `.ut.cpp` + `.ut.c`
5. LLM 补充 Description / Constraint / Verification / Test Goal / PrePost 条件

### 请求 AI 审查

```
审查这个流程图对不对
```

代理会：
1. 运行 `validate.py` 获取结构问题
2. 读取源码对照流程图
3. 写出 `.ai-review.md`（PASS / WARNING / FAIL）

### 请求单元测试或时序集成测试

先读取[筛选后的 UVP/ITP 检查规则](references/code-test-checklists.md)。只保留代码、图、用例与执行证据的关联，不引入安全扫描、资源盘点或客户发布流程。

单元测试示例：

```text
基于当前 C 函数和流程图设计单元测试。核对可行分支、等价类、边界值和故障注入；写明真实 mock 签名、输入、初始状态及断言。未执行就写 NE，不把路径数当成覆盖率。
```

现有 `--ut` 会生成 `.ut.md/.ut.cpp/.ut.c` 草稿。没有真实依赖声明时不再套用 I2C 类型或统一成功返回值；骨架默认使用框架的跳过/忽略保护，补齐实际调用和断言后才移除。零退出码不能证明跳过的用例已通过，覆盖率需单独读取实测报告。

时序或集成测试示例：

```text
检查 PortTask、功率管理函数和驱动调用的真实协作代码，设计接口与超时集成测试。列明真实组件和边界外 mock，给出事件顺序、观测点、时钟和时限来源；阈值不明写 TBD，不操作硬件。
```

AI 按[时序集成测试模式](references/integration-test-design.md)撰写所需的 `.it.md` 或 `.timing.md`；追溯矩阵仅按需生成。不存在 `--it/--timing` 参数，不自动产出已经执行的报告。用户要求执行且环境具备时，再运行项目已有框架并记录实际日志；UT 隔离测试不能冒充真实组件集成，主机逻辑超时测试不能冒充实机时序。

## DD 文档格式 / DD Document Format

```markdown
# Detailed Design: charge_i2c_send

| Field | Value |
|-------|-------|
| Function ID | SWDD_CHARGE_F001 |
| Declaration | static LPI2C_Status_t charge_i2c_send(U8, U8, U16) |
| Description | I2C send with retry mechanism... |
| Constraint | chip_addr must be valid 7-bit I2C address... |
| Verification | status reflects final I2C transaction result... |

## Parameter / Returned Value
| Name | I/O | Type | Range | Default | Description |
|------|-----|------|-------|---------|-------------|
| chip_addr | IN | U8 | 0x00-0x7F | N/A | I2C chip address... |

## Called By
- `charge_apply_single_port_power()` in charge_mana.c:1042
- `charge_enter_shutdown()` in charge_mana.c:1266

## Callings
- `lpi2c_send()`
- `osDelay()`

## Function Evaluation
| Metric | Value |
|--------|-------|
| Branch Num | 3 |
| Cyclomatic Complexity | 6 (Medium) |
| Interactivity | 2 |
| Criticality | 5 |
```

## UT 文档格式 / UT Document Format

```markdown
# Unit Test Design: charge_i2c_send

| # | Test Case ID | Sequence | Design Method | Test Method | Goal |
|---|-------------|----------|---------------|-------------|------|
| 1 | SWDD_CHARGE_F001_UT001 | 1-2-3-4-5-6-7-9-10-3-4-12-13-14 | Error Guessing | Walk-through | Verify retry-and-break path |
| 5 | SWDD_CHARGE_F001_UT005 | 1-2-3-4-12-13-14 | Error Guessing | Requirement-based test | Verify immediate success path |

### UT001: SWDD_CHARGE_F001_UT001
- **Sequence:** 1-2-3-4-5-6-7-9-10-3-4-12-13-14
- **Test Goal:** Verify retry-and-break path...
- **Precondition:** lpi2c_send returns non-OK first, then OK on retry
- **Action:** Call charge_i2c_send(chip=0x50, reg=0x00, data=0x1234)
- **Expected Result:** Returns LPI2C_STATUS_OK
- **Post-condition:** status == LPI2C_STATUS_OK
```

## 完整产物清单 / Complete Artifact List

| 文件 | 用途 | 触发方式 |
|------|------|----------|
| `<fn>.drawio` | 可编辑流程图 | 默认 |
| `<fn>.png` | 位图预览 | `--preview` / `--all` |
| `<fn>.svg` | 矢量预览 | `--svg` / `--all` |
| `<fn>.mmd` | Mermaid 文本 | `--mermaid` / `--all` |
| `<fn>.paths.md` | 分支路径序列 | `--paths` / `--all` |
| `<fn>.report.md` | 转换报告 | `--report` / `--all` |
| `<fn>.analysis.json` | 结构化分析数据 | `--analysis` / `--all` |
| `<fn>.dd.md` | DD 详细设计文档 | `--dd` |
| `<fn>.ut.md` | UT 测试用例设计 | `--ut` |
| `<fn>.ut.cpp` | GoogleTest 跳过态草稿，FFF/gMock 按真实声明配置 | `--ut` |
| `<fn>.ut.c` | Unity 忽略态草稿，CMock 按真实声明配置 | `--ut` |
| `<fn>.ai-review.md` | AI 审查报告 | 代理模式手动触发 |
| `<fn>.self-check.md` | 源码、严格结构与可用视觉自检结果 | 生成或修改后由 AI 执行，不是 CLI 自动生成 |
| `<scope>.it.md` / `.timing.md` | 接口或时序集成测试设计 | AI 按需撰写，不是 CLI 参数 |
| `<scope>.test-traceability.md` | 代码、图版本、UT/IT 与证据映射 | AI 按需撰写 |
| `<scope>.test-result.md` | 真实运行结果、实测值和日志 | 实际执行后记录，未执行不能报 PASS |

## 校验 / Validation

```bash
# 结构校验
python code2flowchart/scripts/validate.py code2flowchart/output/<fn>/<fn>.drawio

# 严格模式（CI 门控）
python code2flowchart/scripts/validate.py code2flowchart/output/<fn>/<fn>.drawio --strict

# 可读性评分（越低越好）
python code2flowchart/scripts/validate.py code2flowchart/output/<fn>/<fn>.drawio --score
```

## 浏览器回退 / Browser Fallback

```bash
# 只读查看
python code2flowchart/scripts/encode_drawio_url.py code2flowchart/output/<fn>/<fn>.drawio

# 在线编辑
python code2flowchart/scripts/encode_drawio_url.py --edit code2flowchart/output/<fn>/<fn>.drawio
```

## 入口点路由 / Entry-Point Routing

| 你说 | 代理做什么 |
|------|-----------|
| "画流程图" | **Generate** — 完整 10 步流程 |
| "审查这个图" | **Review** — `validate.py` + AI 审查 |
| "改一下这个标签" | **Refine** — 最小化 XML 编辑 |
| "检查这个图" | **Validate** — 仅运行 `validate.py` |
| "生成单元测试" | **UT** — 审查候选路径，生成待补齐的设计与跳过态骨架 |
| "做时序/集成测试" | **IT/Timing** — 确认真实协作与判据，按需设计或复核执行证据 |

## 硬性限制 / Hard Limits

| 环节 | 最大轮次 | 超限后 |
|------|----------|--------|
| 结构校验重试 | 3 | 展示最后的错误 |
| 视觉自查 | 2 | 展示最后的图片 |
| 用户审查 | 5 | 建议 draw.io 桌面微调 |
| 解析降级 | 3 步 | 标记为 partial |

## 跨文件搜索调用者 / Cross-File Caller Search

代理在生成 DD 时必须搜索项目根目录下的所有 `*.c` `*.h` 文件：

```bash
rg -n -F "charge_i2c_send" -g '*.c' -g '*.h' -g '*.cpp' -g '*.hpp' d:/project/
```

过滤掉函数定义和注释，提取调用者函数名 → 写入 DD 的 Called By 章节。

## 技能路由 / Skill Routing

| 需求 | 用哪个技能 |
|------|-----------|
| C/C++ 控制流流程图 | **code2flowchart** |
| 通用架构/网络/云图 | drawio-skill |
| Markdown 文本图表 | mermaid-skill |
| 严格 UML 图 | plantuml-skill |
| 手绘/白板风格 | excalidraw-skill |
