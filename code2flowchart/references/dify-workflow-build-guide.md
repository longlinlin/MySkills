# code2flowchart × Dify 工作流搭建方案

## 概述

将当前 code2flowchart 技能（流程图生成、DD 详细设计、UT 单元测试）封装为 Dify 工作流，实现：

1. **输入** C/C++ 函数代码 → **自动输出** 流程图 + DD文档 + UT文档 + 测试骨架代码
2. 确定性解析（Python） + LLM 语义增强（Dify 节点）各司其职
3. 支持本地部署和 Dify Cloud 两种模式

---

## 整体架构 / Architecture

```
用户输入 C/C++ 代码
       │
       ▼
┌──────────────────────────────────────────────┐
│                 Dify Workflow                 │
│                                              │
│  Start → HTTP Request → Code Extract →       │
│  → LLM: Description → LLM: Constraint →      │
│  → LLM: Verification → LLM: Test Goals →     │
│  → Answer                                    │
│                                              │
└──────────────┬───────────────────────────────┘
               │ POST /analyze
               ▼
┌──────────────────────────────────────────────┐
│          External API Service (Python)        │
│                                              │
│  POST /analyze                               │
│  ├─ 保存源代码为临时 .c 文件                    │
│  ├─ 调用 code2flowchart.py --all --dd --ut    │
│  ├─ 读取 analysis.json                        │
│  ├─ 跨文件 grep 搜索调用者                     │
│  └─ 返回 analysis + artifacts 路径/URL        │
│                                              │
│  GET /artifacts/<fn>/<file>                  │
│  └─ 提供产物下载                               │
└──────────────────────────────────────────────┘
```

**核心原则**：Python 做确定性分析（解析/布局/校验/路径枚举），LLM 做语义增强（描述/约束/验证标准/测试目标）。

---

## 第一步：搭建外部 API 服务 / Step 1: External API Service

### 1.1 服务代码 `api_server.py`

```python
#!/usr/bin/env python3
"""
code2flowchart HTTP API service.
POST /analyze  — 分析 C/C++ 函数，返回 analysis.json + 产物列表
GET /artifacts/<fn>/<file>  — 下载产物文件
"""
import json
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

SKILL_DIR = Path(__file__).resolve().parent.parent  # code2flowchart 根目录
SCRIPTS = SKILL_DIR / "scripts"
OUTPUT_BASE = SKILL_DIR / "output"
ARTIFACT_STORE = Path("./artifact_store")  # 产物持久化目录
ARTIFACT_STORE.mkdir(exist_ok=True)

CODEFILE = SKILL_DIR / "scripts" / "code2flowchart.py"
VALIDATE = SKILL_DIR / "scripts" / "validate.py"
DD_GEN = SKILL_DIR / "scripts" / "dd_generator.py"
UT_GEN = SKILL_DIR / "scripts" / "ut_generator.py"


@app.route("/analyze", methods=["POST"])
def analyze():
    body = request.get_json(force=True)
    source_code = body.get("source_code", "")
    target_function = body.get("target_function", "")
    project_prefix = body.get("project_prefix", "SWDD_AUTO")
    project_root = body.get("project_root", "")  # 用于跨文件搜索调用者
    generate_all = body.get("generate_all", True)

    if not source_code:
        return jsonify({"ok": False, "error": "source_code is required"}), 400

    # 1. 保存源码到临时文件
    job_id = uuid.uuid4().hex[:8]
    src_file = Path(tempfile.gettempdir()) / f"cf_{job_id}.c"
    src_file.write_text(source_code, encoding="utf-8")

    # 2. 调用 code2flowchart.py
    cmd = [sys.executable, str(CODEFILE), str(src_file)]
    if target_function:
        cmd += ["--function", target_function]
    if generate_all:
        cmd += ["--all", "--dd", "--ut"]
    if project_prefix:
        cmd += ["--project-prefix", project_prefix]
    cmd += ["-o", str(OUTPUT_BASE)]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    # 3. 找到生成的文件
    fn_name = target_function or "unknown"
    out_dir = OUTPUT_BASE / fn_name
    analysis_path = out_dir / f"{fn_name}.analysis.json"

    if not analysis_path.exists():
        # 尝试查找
        for d in OUTPUT_BASE.iterdir():
            if d.is_dir():
                candidate = d / f"{d.name}.analysis.json"
                if candidate.exists():
                    out_dir = d
                    analysis_path = candidate
                    fn_name = d.name
                    break

    if not analysis_path.exists():
        return jsonify({
            "ok": False,
            "error": f"Analysis failed. stdout: {result.stdout[-500:]}, stderr: {result.stderr[-500:]}"
        }), 500

    # 4. 读取 analysis.json
    with open(analysis_path, encoding="utf-8") as f:
        analysis = json.load(f)

    # 5. 运行 validate.py
    drawio_path = out_dir / f"{fn_name}.drawio"
    validate_result = {"ok": False, "score": 0, "errors": 0, "warnings": 0}
    if drawio_path.exists():
        vr = subprocess.run(
            [sys.executable, str(VALIDATE), str(drawio_path), "--score"],
            capture_output=True, text=True, timeout=30
        )
        validate_result["output"] = vr.stdout
        validate_result["ok"] = vr.returncode == 0

    # 6. 跨文件搜索调用者
    callers = _search_callers(target_function or analysis["functions"][0]["name"], project_root)

    # 7. 拷贝产物到持久化目录
    job_store = ARTIFACT_STORE / job_id
    job_store.mkdir(parents=True, exist_ok=True)
    artifacts = {}
    for f in out_dir.iterdir():
        if f.is_file():
            dest = job_store / f.name
            shutil.copy2(f, dest)
            artifacts[f.suffix.lstrip(".")] = f"/artifacts/{job_id}/{f.name}"

    return jsonify({
        "ok": True,
        "job_id": job_id,
        "function_name": fn_name,
        "analysis": analysis,
        "callers": callers,
        "validate": validate_result,
        "artifacts": artifacts,
        "errors": result.stderr if result.returncode != 0 else "",
    })


@app.route("/artifacts/<job_id>/<filename>")
def get_artifact(job_id, filename):
    path = ARTIFACT_STORE / job_id / filename
    if not path.exists():
        return jsonify({"error": "not found"}), 404
    return send_file(path)


def _search_callers(func_name: str, project_root: str) -> list[dict]:
    """跨文件搜索调用者"""
    if not project_root or not Path(project_root).exists():
        return []
    callers = []
    root = Path(project_root)
    for ext in ("*.c", "*.h", "*.cpp", "*.hpp"):
        for f in root.rglob(ext):
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for i, line in enumerate(content.split("\n"), 1):
                if func_name + "(" in line and "static" not in line.split(func_name)[0].strip():
                    # 排除函数定义行（前面有类型声明）
                    stripped = line.strip()
                    if stripped.startswith("//") or stripped.startswith("/*"):
                        continue
                    if any(kw in stripped.split("(")[0] for kw in
                           ("void", "int", "U8", "U16", "static", "LPI2C_Status_t")):
                        if func_name in stripped and stripped.index(func_name) < 15:
                            continue  # 这很可能是函数定义
                    callers.append({
                        "file": str(f.relative_to(root)),
                        "line": i,
                        "code": stripped[:120]
                    })
    return callers


@app.route("/health")
def health():
    return jsonify({"status": "ok", "scripts": {
        "code2flowchart": str(CODEFILE.exists()),
        "validate": str(VALIDATE.exists()),
        "dd_generator": str(DD_GEN.exists()),
        "ut_generator": str(UT_GEN.exists()),
    }})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5100, debug=False)
```

### 1.2 安装依赖并启动

```bash
pip install flask
python api_server.py
# 服务运行在 http://localhost:5100
```

### 1.3 测试 API

```bash
curl -X POST http://localhost:5100/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "source_code": "static int add(int a, int b) { if (a > 0) return a + b; return b; }",
    "target_function": "add",
    "project_prefix": "SWDD_TEST",
    "project_root": "/path/to/project"
  }'
```

---

## 第二步：Dify 工作流设计 / Step 2: Dify Workflow

### 2.1 创建 Workflow App

在 Dify 中创建 **Workflow** 类型应用（非 Chatflow/Agent）。

### 2.2 节点清单

| 顺序 | 节点类型 | 作用 |
|------|----------|------|
| 1 | **Start** | 接收用户输入 |
| 2 | **HTTP Request** | 调用 `/analyze` API |
| 3 | **Code** | 提取 analysis JSON 关键字段 |
| 4 | **LLM** | 生成函数描述 + 约束 |
| 5 | **LLM** | 生成验证标准 |
| 6 | **LLM** | 生成测试目标（每路径） |
| 7 | **Answer** | 组装最终输出 |

### 2.3 节点详细配置

#### 节点 1：Start — 输入变量

```
变量名            类型        默认值           说明
─────────────────────────────────────────────────────
source_code       paragraph   ""               C/C++ 函数源码
target_function   text        ""               目标函数名
project_prefix    text        "SWDD_AUTO"      Function ID 前缀
project_root      text        ""               项目根目录（跨文件搜索用）
test_framework    select      google_test_fff  google_test_fff / unity_cmock / ceedling
test_env          select      software-in-the-loop  SIL / MIL / PIL / HIL
```

#### 节点 2：HTTP Request — 调用分析服务

```
Method:       POST
URL:          http://<your-server>:5100/analyze
Body (JSON):
{
  "source_code": "{{#start.source_code#}}",
  "target_function": "{{#start.target_function#}}",
  "project_prefix": "{{#start.project_prefix#}}",
  "project_root": "{{#start.project_root#}}",
  "generate_all": true
}
Timeout:      120s
Output var:   analysis_response
```

#### 节点 3：Code — 提取结构化数据

```python
import json

def main(analysis_response: str) -> dict:
    resp = json.loads(analysis_response)
    if not resp.get("ok"):
        return {"error": resp.get("error", "Unknown error")}

    analysis = resp.get("analysis", {})
    fn = analysis.get("functions", [{}])[0]
    fe = fn.get("function_evaluation", {})

    return {
        "ok": True,
        "job_id": resp.get("job_id", ""),
        "function_id": fn.get("function_id", ""),
        "function_name": fn.get("name", ""),
        "signature": fn.get("signature", ""),
        "description_draft": fn.get("description_draft", ""),
        "parameters": json.dumps(fn.get("parameters", []), ensure_ascii=False),
        "return_value": json.dumps(fn.get("return_value", {}), ensure_ascii=False),
        "branches": json.dumps(fn.get("branches", []), ensure_ascii=False),
        "paths": json.dumps(fn.get("paths", []), ensure_ascii=False),
        "calls": json.dumps(fn.get("calls", []), ensure_ascii=False),
        "calls_detail": json.dumps(fe.get("calls_detail", []), ensure_ascii=False),
        "branch_num": fe.get("branch_num", 0),
        "cyclomatic_complexity": fe.get("cyclomatic_complexity", 0),
        "complexity_level": fe.get("complexity_level", ""),
        "interactivity": fe.get("interactivity", 0),
        "criticality": fe.get("criticality", 0),
        "callers": json.dumps(resp.get("callers", []), ensure_ascii=False),
        "validate": json.dumps(resp.get("validate", {}), ensure_ascii=False),
        "artifacts": json.dumps(resp.get("artifacts", {}), ensure_ascii=False),
    }
```

#### 节点 4：LLM — 函数描述 + 约束

```
System Prompt:
你是一个嵌入式 C/C++ 软件详细设计工程师。
基于 code2flowchart 的结构化分析结果，生成函数的 Description 和 Constraint。

规则：
1. Description: 用 2-4 句话描述函数功能、使用场景、主要处理逻辑、外部依赖
2. Constraint: 列出参数有效范围、状态前置条件、时序要求、调用顺序约束
3. 不要编造不存在的分支和条件

User Prompt:
## 函数信息
- 函数名: {{#code.function_name#}}
- 签名: {{#code.signature#}}
- 初始描述: {{#code.description_draft#}}
- 参数: {{#code.parameters#}}
- 返回值: {{#code.return_value#}}
- 调用函数: {{#code.calls#}}
- 分支数: {{#code.branch_num#}}
- 圈复杂度: {{#code.cyclomatic_complexity#}} ({{#code.complexity_level#}})
- 交互性: {{#code.interactivity#}}
- 关键性: {{#code.criticality#}}
- 被调用者: {{#code.callers#}}

请输出：
## Description
(英文描述)

## Constraint
(约束条件)

Output变量: description_constraint
```

#### 节点 5：LLM — 验证标准

```
System Prompt:
你是一个嵌入式软件测试工程师。
基于函数分析结果，生成 Verification Criteria（验证标准）。

规则：
1. 说明如何验证函数成功执行
2. 列出关键断言点（返回值、输出参数、副作用）
3. 指出需要 mock 的外部依赖

User Prompt:
## 函数信息
- 函数名: {{#code.function_name#}}
- 签名: {{#code.signature#}}
- 参数: {{#code.parameters#}}
- 返回值: {{#code.return_value#}}
- 调用函数: {{#code.calls#}}
- 分支: {{#code.branches#}}

请输出验证标准（每条一行，以 - 开头）。

Output变量: verification_criteria_text
```

#### 节点 6：LLM — 测试目标

```
System Prompt:
你是一个单元测试设计工程师。
基于函数分支路径，为每条路径生成具体的 Test Goal / Precondition / Action / Expected Result。

规则：
1. 每个 path 生成一个测试用例字段
2. Test Goal: 一句话描述这个路径验证什么
3. Precondition: mock 设置、初始状态、输入值
4. Action: 具体的函数调用（含参数值）
5. Expected Result: 断言检查
6. 不编造路径

User Prompt:
## 函数信息
- 函数名: {{#code.function_name#}}
- 路径: {{#code.paths#}}
- 调用函数: {{#code.calls#}}
- 参数: {{#code.parameters#}}
- 测试框架: {{#start.test_framework#}}
- 测试环境: {{#start.test_env#}}

请为每条路径输出测试用例（JSON 格式）。

Output变量: test_cases_json
```

#### 节点 7：Answer — 组装最终输出

```markdown
# {{#code.function_name}} — 详细设计 / Detailed Design

**Function ID:** {{#code.function_id#}}
**Cyclomatic Complexity:** {{#code.cyclomatic_complexity#}} ({{#code.complexity_level#}})
**Branch Count:** {{#code.branch_num#}}
**Interactivity:** {{#code.interactivity#}}
**Criticality:** {{#code.criticality#}}

## Description

{{#llm_desc.description_constraint#}}

## Verification Criteria

{{#llm_verify.verification_criteria_text#}}

## Called By

{{#code.callers#}}

## Callings

{{#code.calls#}}

## Test Cases

{{#llm_tests.test_cases_json#}}

## Artifacts

{{#code.artifacts#}}

## Validation

{{#code.validate#}}
```

---

## 第三步：部署 / Step 3: Deployment

### 3.1 本地部署

```bash
# 1. 启动 API 服务
cd /path/to/code2flowchart
pip install flask gunicorn
gunicorn -w 2 -b 0.0.0.0:5100 api_server:app

# 2. 在 Dify 中配置 HTTP Request 节点 URL 指向 localhost:5100

# 3. 如果 Dify 也在本地 Docker 中，使用 host.docker.internal:5100
```

### 3.2 Docker 部署

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y graphviz && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY code2flowchart/ /app/
RUN pip install flask gunicorn Pillow
EXPOSE 5100
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5100", "api_server:app"]
```

### 3.3 Dify Cloud 部署

如果使用 Dify Cloud，API 服务需部署在公网可访问的服务器上：
- 使用 Nginx 反向代理 + HTTPS
- 在 HTTP Request 节点中使用公网 URL
- 产物通过 `/artifacts/<job_id>/<file>` 端点提供下载

---

## 第四步：发布与调用 / Step 4: Publishing

### 4.1 发布 Workflow

在 Dify 中点击 **Publish**，获得 API endpoint：

```bash
curl -X POST https://api.dify.ai/v1/workflows/run \
  -H "Authorization: Bearer <API_SECRET>" \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {
      "source_code": "int add(int a, int b) { return a + b; }",
      "target_function": "add",
      "project_prefix": "SWDD_DEMO",
      "test_framework": "google_test_fff"
    },
    "response_mode": "blocking",
    "user": "dev-user"
  }'
```

### 4.2 嵌入其他应用

```
前端 (React/Vue) → HTTP POST → Dify Workflow API → API Service → code2flowchart.py
                                                      ↓
                                                  analysis.json + artifacts
```

---

## 第五步：文件上传方式 / Step 5: File Upload

如果源码很长，使用 Dify 文件上传：

```bash
# 1. 上传文件
curl -X POST https://api.dify.ai/v1/files/upload \
  -H "Authorization: Bearer <API_SECRET>" \
  -F "file=@source.c" \
  -F "user=dev-user"

# 2. 在 Workflow 中接收文件 ID
# Start 节点增加变量: file_id (类型: File)
```

---

## 关键注意事项 / Notes

| 注意点 | 说明 |
|--------|------|
| 沙箱隔离 | API 服务应在容器/沙箱中运行，限制文件系统和网络访问 |
| 超时设置 | code2flowchart.py 大函数可能耗时 >30s，HTTP Request 节点超时设 120s |
| 产物清理 | `artifact_store` 定期清理旧文件（cron job） |
| Schema 版本 | analysis.json 的 `schema_version` 变化时更新 Prompt |
| 人工审查 | 生成的 UT 代码合并前必须人工 Review |
| 跨文件搜索 | `project_root` 必须指向项目根目录，否则 Called By 为空 |
