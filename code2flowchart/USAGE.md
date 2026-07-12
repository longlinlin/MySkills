# code2flowchart — 使用指南 / Usage Guide

## 概述 / Overview

code2flowchart 是一个 C/C++ 代码 → 流程图 + 详细设计 + 单元测试的自动化技能。

## 快速开始 / Quick Start

### 1. 基础流程图转换

```bash
python code2flowchart/scripts/code2flowchart.py source.c --function target_func
```

产出：`output/<function>/<function>.drawio`

### 2. 生成全部产物（推荐）

```bash
python code2flowchart/scripts/code2flowchart.py source.c \
    --function target_func \
    --all --dd --ut \
    --project-prefix SWDD_<MODULE>
```

| flag | 说明 |
|------|------|
| `--all` | 生成所有基础产物（drawio/png/svg/mermaid/paths/report/analysis/validate） |
| `--dd` | 生成详细设计文档 `.dd.md` |
| `--ut` | 生成单元测试文档+骨架代码 `.ut.md` `.ut.cpp` `.ut.c` |
| `--project-prefix` | 设置 Function ID 前缀，如 `SWDD_CHARGE` |

## 在 Claude Code 中使用 / Using in Claude Code

直接粘贴 C/C++ 函数代码，说：

```
把这个函数转成流程图
```

代理会自动：
1. 保存代码 → 运行 `code2flowchart.py --all --validate`
2. 校验 `.drawio`（`validate.py`，0 errors 才继续）
3. 视觉自查 PNG 预览（7项缺陷检查）
4. 展示结果，收集反馈（最多 5 轮）

### 请求 DD/UT

```
对这个函数生成 DD 和 UT
```

代理会：
1. 先运行 `code2flowchart.py --all --dd --ut --project-prefix <PREFIX>`
2. **跨文件搜索调用者**：`grep -rn "函数名" --include="*.c" --include="*.h" <项目根目录>/`
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
| `<fn>.ut.cpp` | GoogleTest+FFF 骨架 | `--ut` |
| `<fn>.ut.c` | Unity+CMock 骨架 | `--ut` |
| `<fn>.ai-review.md` | AI 审查报告 | 代理模式手动触发 |

## 校验 / Validation

```bash
# 结构校验
python code2flowchart/scripts/validate.py output/<fn>/<fn>.drawio

# 严格模式（CI 门控）
python code2flowchart/scripts/validate.py output/<fn>/<fn>.drawio --strict

# 可读性评分（越低越好）
python code2flowchart/scripts/validate.py output/<fn>/<fn>.drawio --score
```

## 浏览器回退 / Browser Fallback

```bash
# 只读查看
python code2flowchart/scripts/encode_drawio_url.py output/<fn>/<fn>.drawio

# 在线编辑
python code2flowchart/scripts/encode_drawio_url.py --edit output/<fn>/<fn>.drawio
```

## 入口点路由 / Entry-Point Routing

| 你说 | 代理做什么 |
|------|-----------|
| "画流程图" | **Generate** — 完整 10 步流程 |
| "审查这个图" | **Review** — `validate.py` + AI 审查 |
| "改一下这个标签" | **Refine** — 最小化 XML 编辑 |
| "检查这个图" | **Validate** — 仅运行 `validate.py` |

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
grep -rn "charge_i2c_send" --include="*.c" --include="*.h" d:/project/
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
