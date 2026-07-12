# code2flowchart × Dify 工作流详细搭建方案

## 目录

1. [概述与架构](#1-概述与架构)
2. [环境准备](#2-环境准备)
3. [API 服务完整实现](#3-api-服务完整实现)
4. [Dify 工作流节点逐一配置](#4-dify-工作流节点逐一配置)
5. [LLM Prompt 模板（含Few-Shot）](#5-llm-prompt-模板含few-shot)
6. [产物管理与存储](#6-产物管理与存储)
7. [部署方案](#7-部署方案)
8. [测试与验证](#8-测试与验证)
9. [CI/CD 集成](#9-cicd-集成)
10. [故障排查](#10-故障排查)

---

## 1. 概述与架构

### 1.1 设计目标

| 输入 | 处理 | 输出 |
|------|------|------|
| C/C++ 函数源码（粘贴或文件上传） | Python 确定性解析 + LLM 语义增强 | 流程图(.drawio/.png) + DD文档(.dd.md) + UT文档(.ut.md) + 测试骨架(.ut.cpp/.ut.c) |

### 1.2 职责划分

```
┌─────────────────────────────────────────────────┐
│              Python (确定性)                     │
│  ├─ C/C++ 词法/语法解析                          │
│  ├─ 控制流图构建 + 正交布局                       │
│  ├─ drawio/PNG/SVG 渲染                         │
│  ├─ 圈复杂度/路径枚举/交互性/关键性 计算            │
│  ├─ DD/UT 模板文档生成（占位符）                    │
│  ├─ validate.py 结构校验                          │
│  └─ 跨文件 grep 搜索调用者                        │
└─────────────────────────────────────────────────┘
                      │
                      │ analysis.json (结构化数据)
                      ▼
┌─────────────────────────────────────────────────┐
│              LLM (语义增强)                       │
│  ├─ 函数功能描述（Description）                    │
│  ├─ 约束条件（Constraint）                        │
│  ├─ 验证标准（Verification Criteria）              │
│  ├─ 每条路径的 Test Goal / Pre / Action / Expected │
│  └─ 测试骨架代码中 TODO 的补充                     │
└─────────────────────────────────────────────────┘
```

### 1.3 整体拓扑

```
用户
 │
 ├─ (方式A) 粘贴源码 → Dify Start 节点
 │
 ├─ (方式B) 上传 .c 文件 → Dify File Upload → Start 节点
 │
 ▼
┌──────────────────────────────────────────────────────┐
│                    Dify Workflow                      │
│                                                      │
│  ┌──────┐   ┌───────────┐   ┌──────┐                │
│  │ Start │→│ HTTP Req   │→│ Code │                 │
│  │       │  │ POST /ana │  │Extract│                 │
│  └──────┘   └───────────┘   └──┬───┘                │
│                                │                      │
│                    ┌───────────┼───────────┐          │
│                    ▼           ▼           ▼          │
│              ┌─────────┐ ┌─────────┐ ┌─────────┐     │
│              │ LLM #1  │ │ LLM #2  │ │ LLM #3  │     │
│              │Desc+Cons│ │ Verify  │ │TestGoals│     │
│              └────┬────┘ └────┬────┘ └────┬────┘     │
│                   │          │          │            │
│                   ▼          ▼          ▼            │
│              ┌──────────────────────────────┐        │
│              │     Template / Code 节点       │        │
│              │   组装完整 DD.md + UT.md       │        │
│              └──────────────┬───────────────┘        │
│                             ▼                         │
│                    ┌───────────────┐                  │
│                    │    Answer     │                  │
│                    └───────────────┘                  │
└──────────────────────┬───────────────────────────────┘
                       │ POST /analyze
                       ▼
┌──────────────────────────────────────────────────────┐
│              External API Service (Flask)             │
│  POST /analyze          GET /artifacts/<id>/<file>   │
│  PUT  /enrich           GET /health                  │
│                                                      │
│  内部调用:                                            │
│    code2flowchart.py --all --dd --ut                 │
│    validate.py --score                               │
│    dd_generator.py                                   │
│    ut_generator.py                                   │
│    grep -rn (cross-file caller search)               │
│    repair_png.py                                     │
└──────────────────────────────────────────────────────┘
```

---

## 2. 环境准备

### 2.1 Python 环境

```bash
# 确保 Python 3.10+
python --version

# 安装依赖
pip install flask gunicorn Pillow

# 验证 code2flowchart 可运行
cd /path/to/code2flowchart
python scripts/code2flowchart.py --help
```

### 2.2 Dify 环境

```bash
# 本地部署 Dify (Docker)
git clone https://github.com/langgenius/dify.git
cd dify/docker
cp .env.example .env
docker compose up -d

# 访问 http://localhost:3000
# 初始账号: 安装时设置
```

### 2.3 网络连通性验证

```bash
# 从 Dify 容器内测试 API 服务可达性
docker exec -it docker-api-1 curl http://host.docker.internal:5100/health

# 预期返回:
# {"status":"ok","scripts":{"code2flowchart":"True","validate":"True",...}}
```

---

## 3. API 服务完整实现

### 3.1 目录结构

```
code2flowchart/
├── api_server/
│   ├── __init__.py
│   ├── app.py              # Flask 主应用
│   ├── analysis.py         # 核心分析逻辑
│   ├── callers.py          # 跨文件调用者搜索
│   ├── artifacts.py        # 产物管理
│   ├── config.py           # 配置
│   └── wsgi.py             # Gunicorn 入口
├── scripts/                # 现有脚本
├── output/                 # 产物输出
└── artifact_store/         # 持久化产物存储
```

### 3.2 配置文件 `api_server/config.py`

```python
import os
from pathlib import Path

# 项目根目录
ROOT_DIR = Path(__file__).resolve().parent.parent

# code2flowchart 脚本路径
SCRIPTS_DIR = ROOT_DIR / "scripts"
CODEFILE     = SCRIPTS_DIR / "code2flowchart.py"
VALIDATE     = SCRIPTS_DIR / "validate.py"
DD_GEN       = SCRIPTS_DIR / "dd_generator.py"
UT_GEN       = SCRIPTS_DIR / "ut_generator.py"
REPAIR_PNG   = SCRIPTS_DIR / "repair_png.py"

# 产物目录
OUTPUT_BASE = ROOT_DIR / "output"
ARTIFACT_STORE = Path(os.getenv("ARTIFACT_STORE", str(ROOT_DIR / "artifact_store")))

# 服务配置
HOST = os.getenv("API_HOST", "0.0.0.0")
PORT = int(os.getenv("API_PORT", "5100"))
MAX_SOURCE_SIZE = int(os.getenv("MAX_SOURCE_SIZE", str(2 * 1024 * 1024)))  # 2MB
ANALYSIS_TIMEOUT = int(os.getenv("ANALYSIS_TIMEOUT", "120"))  # 秒
ARTIFACT_RETENTION_DAYS = int(os.getenv("ARTIFACT_RETENTION_DAYS", "30"))

# 安全配置
ALLOWED_EXTENSIONS = {".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hxx"}
API_TOKEN = os.getenv("API_TOKEN", "")  # 若设置，请求必须带 Bearer token
```

### 3.3 核心分析逻辑 `api_server/analysis.py`

```python
"""核心分析逻辑：调用 code2flowchart.py 并收集结果"""
import json
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from .config import CODEFILE, VALIDATE, DD_GEN, UT_GEN, REPAIR_PNG, OUTPUT_BASE, ANALYSIS_TIMEOUT


def run_analysis(
    source_code: str,
    target_function: str = "",
    project_prefix: str = "SWDD_AUTO",
    generate_all: bool = True,
    detail_level: str = "standard",
) -> dict:
    """
    执行完整分析流水线：
    1. 保存源码 → 2. code2flowchart.py → 3. validate.py → 4. 读取产物
    """

    job_id = uuid.uuid4().hex[:8]
    src_file = Path(tempfile.gettempdir()) / f"cf_{job_id}.c"
    src_file.write_text(source_code, encoding="utf-8")

    # ---------- Step 1: code2flowchart.py ----------
    cmd = [sys.executable, str(CODEFILE), str(src_file)]
    if target_function:
        cmd += ["--function", target_function]
    if generate_all:
        cmd += ["--all", "--dd", "--ut"]
    if project_prefix:
        cmd += ["--project-prefix", project_prefix]
    if detail_level != "standard":
        cmd += ["--detail-level", detail_level]
    cmd += ["-o", str(OUTPUT_BASE)]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=ANALYSIS_TIMEOUT)

    # ---------- Step 2: 定位产物目录 ----------
    fn_name, out_dir, analysis_path = _locate_output(target_function)

    if not analysis_path or not analysis_path.exists():
        return {
            "ok": False,
            "job_id": job_id,
            "error": "Analysis produced no valid output",
            "stdout": result.stdout[-1000:],
            "stderr": result.stderr[-1000:],
        }

    # ---------- Step 3: 读取 analysis.json ----------
    with open(analysis_path, encoding="utf-8") as f:
        analysis = json.load(f)

    # ---------- Step 4: validate.py ----------
    drawio_path = out_dir / f"{fn_name}.drawio"
    validate_result = _run_validate(drawio_path)
    analysis["xml_validation"] = validate_result

    # ---------- Step 5: repair_png.py（如果 PNG 存在）----------
    png_path = out_dir / f"{fn_name}.png"
    if png_path.exists():
        subprocess.run([sys.executable, str(REPAIR_PNG), str(png_path)],
                       capture_output=True, timeout=10)

    # ---------- Step 6: 更新 function_id ----------
    _update_function_ids(analysis, project_prefix)

    # ---------- Step 7: 收集产物列表 ----------
    artifacts = {}
    for f in sorted(out_dir.iterdir()):
        if f.is_file():
            ext = f.suffix.lstrip(".").replace(".", "_")
            artifacts[ext] = str(f)

    return {
        "ok": True,
        "job_id": job_id,
        "function_name": fn_name,
        "analysis": analysis,
        "validate": validate_result,
        "artifacts": artifacts,
        "stdout": result.stdout,
        "stderr": result.stderr if result.returncode != 0 else "",
    }


def _locate_output(target_function: str) -> tuple[str, Path, Path]:
    """在 OUTPUT_BASE 中定位产出的 analysis.json"""
    fn_name = target_function or "unknown"
    out_dir = OUTPUT_BASE / fn_name
    analysis_path = out_dir / f"{fn_name}.analysis.json"

    if not analysis_path.exists():
        # 枚举所有子目录查找
        for d in sorted(OUTPUT_BASE.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if d.is_dir():
                for f in d.glob("*.analysis.json"):
                    out_dir = d
                    analysis_path = f
                    fn_name = f.stem.split(".analysis")[0] if ".analysis" in f.stem else f.stem
                    return fn_name, out_dir, analysis_path
    return fn_name, out_dir, analysis_path


def _run_validate(drawio_path: Path) -> dict:
    """运行 validate.py 结构校验"""
    if not drawio_path.exists():
        return {"ok": False, "error": "drawio file not found"}
    vr = subprocess.run(
        [sys.executable, str(VALIDATE), str(drawio_path), "--score"],
        capture_output=True, text=True, timeout=30
    )
    # 解析输出
    errors = warnings = score = 0
    for line in vr.stdout.split("\n"):
        if line.startswith("error:"):
            errors += 1
        elif line.startswith("warning:"):
            warnings += 1
        elif line.startswith("score:"):
            try:
                score = int(line.split(":")[1].strip().split()[0])
            except Exception:
                pass
    return {
        "ok": vr.returncode == 0 and errors == 0,
        "errors": errors,
        "warnings": warnings,
        "score": score,
        "output": vr.stdout,
    }


def _update_function_ids(analysis: dict, prefix: str) -> None:
    """为每个函数填充 function_id"""
    for i, fn in enumerate(analysis.get("functions", []), 1):
        if not fn.get("function_id"):
            fn["function_id"] = f"{prefix}_F{i:03d}"
```

### 3.4 跨文件调用者搜索 `api_server/callers.py`

```python
"""跨文件搜索函数调用者"""
import re
from pathlib import Path


def search_callers(func_name: str, project_root: str) -> list[dict]:
    """
    在 project_root 下所有 C/C++ 文件中搜索 func_name 的调用位置。
    排除函数定义行、注释、字符串字面量。
    """
    if not func_name or not project_root:
        return []

    root = Path(project_root)
    if not root.exists():
        return []

    callers = []
    # 用于识别函数定义行的模式：返回类型 + 函数名 + (
    # 例如: "static LPI2C_Status_t charge_i2c_send("
    definition_pattern = re.compile(
        r'^\s*(static\s+)?(inline\s+)?(const\s+)?(volatile\s+)?'
        r'(void|int|char|short|long|float|double|U8|U16|U32|U64|S8|S16|S32|S64|'
        r'BOOL|bool|LPI2C_Status_t|Charge_PortStatus|'
        r'[a-zA-Z_]\w*)\s*[*\s]+\s*' + re.escape(func_name) + r'\s*\('
    )

    for pattern in ("**/*.c", "**/*.h", "**/*.cpp", "**/*.hpp", "**/*.cc", "**/*.cxx"):
        for f in root.glob(pattern):
            # 跳过第三方库和构建目录
            if any(part in f.parts for part in ("build", "vendor", "third_party", ".git")):
                continue
            try:
                lines = f.read_text(encoding="utf-8", errors="ignore").split("\n")
            except Exception:
                continue

            in_block_comment = False
            for line_no, raw_line in enumerate(lines, 1):
                line = raw_line.strip()

                # 跳过预处理指令
                if line.startswith("#"):
                    continue

                # 处理块注释
                if "/*" in line:
                    in_block_comment = True
                if "*/" in line:
                    in_block_comment = False
                    continue
                if in_block_comment:
                    continue

                # 跳过行注释
                if line.startswith("//") or line.startswith("*"):
                    continue

                # 必须是包含函数名的行
                if func_name + "(" not in line:
                    continue

                # 排除函数定义行
                if definition_pattern.match(raw_line):
                    continue

                # 排除声明（只有类型+函数名+分号）
                if line.endswith(";") and line.count("(") == line.count(")"):
                    # 可能是 forward declaration
                    decl_match = re.match(r'^extern\s+.*' + re.escape(func_name), line)
                    if decl_match or line.endswith(";"):
                        # 检查是否在函数体外部（粗略判断：前面最近的 { 在上一行）
                        continue

                callers.append({
                    "file": str(f.relative_to(root)),
                    "line": line_no,
                    "code": raw_line.strip()[:150],
                })

    # 按文件+行号排序
    callers.sort(key=lambda x: (x["file"], x["line"]))
    return callers


def resolve_caller_function_name(caller: dict, project_root: str) -> str:
    """
    尝试找出调用发生的函数名。
    从 caller 位置向上搜索最近的函数定义。
    """
    filepath = Path(project_root) / caller["file"]
    if not filepath.exists():
        return "(unknown)"

    try:
        lines = filepath.read_text(encoding="utf-8", errors="ignore").split("\n")
    except Exception:
        return "(unknown)"

    # 从调用行向上搜索最近的函数定义
    func_pattern = re.compile(
        r'^\s*(static\s+)?(inline\s+)?(const\s+)?(volatile\s+)?'
        r'(\w+(\s*\*)?)\s+(\w+)\s*\([^)]*\)\s*$'
    )
    brace_count = 0
    for i in range(caller["line"] - 1, -1, -1):
        line = lines[i].strip()
        if "}" in line:
            brace_count += line.count("}")
        if "{" in line:
            brace_count -= line.count("{")
        if brace_count < 0 and func_pattern.match(line):
            m = func_pattern.match(line)
            return m.group(7)  # 函数名在捕获组7
    return "(unknown)"
```

### 3.5 产物管理 `api_server/artifacts.py`

```python
"""产物持久化管理"""
import os
import shutil
import time
from pathlib import Path
from .config import ARTIFACT_STORE, ARTIFACT_RETENTION_DAYS


def init_store() -> Path:
    """初始化产物存储目录"""
    ARTIFACT_STORE.mkdir(parents=True, exist_ok=True)
    return ARTIFACT_STORE


def save_artifacts(job_id: str, out_dir: Path) -> dict[str, str]:
    """拷贝产物到持久化存储，返回 URL 路径映射"""
    job_store = ARTIFACT_STORE / job_id
    job_store.mkdir(parents=True, exist_ok=True)

    urls = {}
    for f in sorted(out_dir.iterdir()):
        if f.is_file():
            dest = job_store / f.name
            shutil.copy2(f, dest)
            ext = f.suffix.lstrip(".")
            urls[ext] = f"/artifacts/{job_id}/{f.name}"

    return urls


def cleanup_old_artifacts() -> int:
    """清理超过保留期的旧产物，返回删除数量"""
    now = time.time()
    deleted = 0
    for job_dir in ARTIFACT_STORE.iterdir():
        if job_dir.is_dir():
            age_seconds = now - job_dir.stat().st_mtime
            if age_seconds > ARTIFACT_RETENTION_DAYS * 86400:
                shutil.rmtree(job_dir)
                deleted += 1
    return deleted
```

### 3.6 Flask 主应用 `api_server/app.py`

```python
"""Flask 主应用"""
import json
import sys
from pathlib import Path

from flask import Flask, request, jsonify, send_file
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import HOST, PORT, ARTIFACT_STORE, MAX_SOURCE_SIZE, API_TOKEN
from .analysis import run_analysis
from .callers import search_callers, resolve_caller_function_name
from .artifacts import init_store, save_artifacts

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)  # type: ignore


def _check_auth():
    """Token 认证（如果配置了 API_TOKEN）"""
    if API_TOKEN:
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {API_TOKEN}":
            return jsonify({"error": "unauthorized"}), 401
    return None


# ═══════════════════════════════════════════════════════
# POST /analyze  — 主分析端点
# ═══════════════════════════════════════════════════════
@app.route("/analyze", methods=["POST"])
def analyze():
    auth_err = _check_auth()
    if auth_err:
        return auth_err

    body = request.get_json(force=True, silent=True)
    if not body:
        return jsonify({"ok": False, "error": "invalid JSON body"}), 400

    source_code = body.get("source_code", "")
    if not source_code:
        return jsonify({"ok": False, "error": "source_code is required"}), 400

    if len(source_code) > MAX_SOURCE_SIZE:
        return jsonify({
            "ok": False,
            "error": f"source_code exceeds max size ({MAX_SOURCE_SIZE} bytes)"
        }), 413

    target_function = body.get("target_function", "")
    project_prefix = body.get("project_prefix", "SWDD_AUTO")
    project_root = body.get("project_root", "")
    generate_all = body.get("generate_all", True)
    detail_level = body.get("detail_level", "standard")

    # 运行分析
    result = run_analysis(
        source_code=source_code,
        target_function=target_function,
        project_prefix=project_prefix,
        generate_all=generate_all,
        detail_level=detail_level,
    )

    if not result.get("ok"):
        return jsonify(result), 500

    # 跨文件搜索调用者
    fn_name = result["function_name"]
    raw_callers = search_callers(fn_name, project_root)
    callers = []
    for c in raw_callers:
        caller_fn = resolve_caller_function_name(c, project_root)
        callers.append({
            "function": caller_fn,
            "file": c["file"],
            "line": c["line"],
            "code": c["code"],
        })

    # 保存产物
    out_dir = Path(list(result["artifacts"].values())[0]).parent if result["artifacts"] else None
    artifact_urls = {}
    if out_dir and out_dir.exists():
        artifact_urls = save_artifacts(result["job_id"], out_dir)

    return jsonify({
        "ok": True,
        "job_id": result["job_id"],
        "function_name": fn_name,
        "analysis": result["analysis"],
        "callers": callers,
        "validate": result["validate"],
        "artifacts": artifact_urls,
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
    })


# ═══════════════════════════════════════════════════════
# PUT /enrich  — 接收 LLM 增强后的内容，写回 DD/UT
# ═══════════════════════════════════════════════════════
@app.route("/enrich", methods=["PUT"])
def enrich():
    """接收 LLM 增强后的 description/constraint/verification/test_cases，
    写回 analysis.json 和产物文件"""
    auth_err = _check_auth()
    if auth_err:
        return auth_err

    body = request.get_json(force=True, silent=True)
    if not body:
        return jsonify({"ok": False, "error": "invalid JSON body"}), 400

    job_id = body.get("job_id", "")
    function_name = body.get("function_name", "")
    enriched = body.get("enriched", {})

    # 更新 analysis.json
    job_store = ARTIFACT_STORE / job_id
    analysis_path = job_store / f"{function_name}.analysis.json"
    if analysis_path.exists():
        with open(analysis_path, encoding="utf-8") as f:
            analysis = json.load(f)

        fn = analysis["functions"][0]
        if enriched.get("description"):
            fn["description_draft"] = enriched["description"]
        if enriched.get("constraint"):
            fn["constraint"] = enriched["constraint"]
        if enriched.get("verification_criteria"):
            fn["verification_criteria"] = enriched["verification_criteria"]
        if enriched.get("test_cases"):
            fn["enriched_test_cases"] = enriched["test_cases"]

        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)

    return jsonify({"ok": True})


# ═══════════════════════════════════════════════════════
# GET /artifacts/<job_id>/<filename>  — 产物下载
# ═══════════════════════════════════════════════════════
@app.route("/artifacts/<job_id>/<filename>")
def get_artifact(job_id, filename):
    # 防止路径遍历攻击
    if ".." in filename or "/" in filename or "\\" in filename:
        return jsonify({"error": "invalid filename"}), 400
    path = ARTIFACT_STORE / job_id / filename
    if not path.exists():
        return jsonify({"error": "not found"}), 404
    return send_file(path)


# ═══════════════════════════════════════════════════════
# GET /health  — 健康检查
# ═══════════════════════════════════════════════════════
@app.route("/health")
def health():
    from .config import CODEFILE, VALIDATE, DD_GEN, UT_GEN
    return jsonify({
        "status": "ok",
        "scripts": {
            "code2flowchart": str(CODEFILE.exists()),
            "validate": str(VALIDATE.exists()),
            "dd_generator": str(DD_GEN.exists()),
            "ut_generator": str(UT_GEN.exists()),
        },
        "store": str(ARTIFACT_STORE.exists()),
    })


# ═══════════════════════════════════════════════════════
# 启动
# ═══════════════════════════════════════════════════════
init_store()

if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False)
```

### 3.7 启动命令

```bash
# 开发模式
python -m api_server.app

# 生产模式（多 worker）
gunicorn -w 4 -b 0.0.0.0:5100 \
  --timeout 180 \
  --access-logfile /var/log/cf-access.log \
  --error-logfile /var/log/cf-error.log \
  api_server.app:app
```

---

## 4. Dify 工作流节点逐一配置

### 4.1 节点总览

```
Start
  │
  ├──[source_code 为空?]──→ IF/ELSE ──→ (Error Answer: 请提供源码)
  │
  ▼
HTTP Request (POST /analyze, 120s)
  │
  ├──[response.ok == false?]──→ IF/ELSE ──→ (Error Answer: 分析失败)
  │
  ▼
Code Extract (提取结构化字段)
  │
  ├──────────────────────────────────────┐
  ▼                    ▼                 ▼
LLM #1               LLM #2           LLM #3
Description+         Verification     Test Goals
Constraint           Criteria         per Path
  │                    │                 │
  └────────────────────┼─────────────────┘
                       ▼
              Template (组装最终 Markdown)
                       │
                       ▼
                    Answer
```

### 4.2 Start 节点

```
┌──────────────────────────────────────────────────────┐
│ 变量名             类型        必填  默认值           │
├──────────────────────────────────────────────────────┤
│ source_code        paragraph   是    ""              │
│ target_function    text        否    ""              │
│ project_prefix     text        否    "SWDD_AUTO"    │
│ project_root       text        否    ""             │
│ test_framework     select      否    google_test_fff│
│   options: google_test_fff, unity_cmock, ceedling    │
│ test_env           select      否    software-in-the-loop │
│   options: model-in-the-loop, software-in-the-loop,  │
│            processor-in-the-loop, hardware-in-the-loop│
└──────────────────────────────────────────────────────┘
```

### 4.3 IF/ELSE — 输入校验

```
条件: {{#start.source_code#}} is empty

IF 分支 → Answer 节点:
  "请提供 C/C++ 函数源码。"

ELSE 分支 → HTTP Request 节点
```

### 4.4 HTTP Request 节点

```
┌─────────────────────────────────────────────────────┐
│ API:          POST http://<server>:5100/analyze     │
│ Authorization: Bearer {{#sys.api_token#}}           │
│ Content-Type:  application/json                     │
│ Timeout:       120s                                 │
│ Retry:         1 次                                  │
│                                                     │
│ Body (JSON):                                        │
│ {                                                   │
│   "source_code": "{{#start.source_code#}}",          │
│   "target_function": "{{#start.target_function#}}",  │
│   "project_prefix": "{{#start.project_prefix#}}",    │
│   "project_root": "{{#start.project_root#}}",        │
│   "generate_all": true                              │
│ }                                                   │
│                                                     │
│ 输出变量: analysis_response (text)                    │
└─────────────────────────────────────────────────────┘
```

### 4.5 IF/ELSE — 分析结果校验

```
条件: analysis_response 中 ok == false

IF 分支 → Answer:
  "分析失败: {{#analysis_response.error#}}"
  "stderr: {{#analysis_response.stderr#}}"

ELSE 分支 → Code Extract 节点
```

### 4.6 Code Extract 节点

```python
import json

def main(analysis_response: str) -> dict:
    resp = json.loads(analysis_response)
    analysis = resp.get("analysis", {})
    fn = analysis.get("functions", [{}])[0]
    fe = fn.get("function_evaluation", {})
    callers = resp.get("callers", [])
    validate = resp.get("validate", {})
    artifacts = resp.get("artifacts", {})

    # ── 构建调用者列表 ──
    caller_lines = []
    if callers:
        for c in callers:
            caller_lines.append(
                f"- `{c['function']}()` in `{c['file']}:{c['line']}`"
            )
    called_by_text = "\n".join(caller_lines) if caller_lines else \
                     "- (none detected in project)"

    # ── 构建 Callings 列表（不去重，带次数）──
    calls_detail = fe.get("calls_detail", [])
    calling_lines = []
    for cd in calls_detail:
        calling_lines.append(f"- `{cd['name']}()` called {cd['count']} time(s)")
    callings_text = "\n".join(calling_lines) if calling_lines else "- None"

    # ── 参数表 ──
    params = fn.get("parameters", [])
    param_rows = []
    for p in params:
        direction = p.get("direction", "")
        io = "IN" if direction == "input" else "OUT" if direction == "output" else \
             "IN/OUT" if direction == "input_output" else direction
        param_rows.append(
            f"| `{p['name']}` | {io} | `{p['type']}` | {p.get('range','N/A')} | "
            f"{_param_desc(p)} |"
        )
    param_table = "\n".join(param_rows) if param_rows else "| (none) | - | - | - | - |"

    # ── 路径摘要 ──
    paths = fn.get("paths", [])
    path_summaries = []
    for i, path in enumerate(paths, 1):
        seq = path.get("edge_sequence_text", "")
        conditions = path.get("conditions", [])
        labels = path.get("labels", [])
        has_loop = any("loop" in (l or "") for l in labels)
        has_break = any("break" in (l or "") for l in labels)
        if has_break and has_loop:
            flavor = "retry-and-break"
        elif has_break:
            flavor = "immediate-success"
        elif has_loop:
            flavor = "retry-exhaust"
        else:
            flavor = "early-return" if "return" in " ".join(labels) else "normal"
        path_summaries.append({
            "index": i,
            "sequence": seq,
            "flavor": flavor,
            "labels": labels,
            "conditions": conditions,
        })

    return {
        # 基础标识
        "job_id": resp.get("job_id", ""),
        "function_id": fn.get("function_id", ""),
        "function_name": fn.get("name", ""),
        "signature": fn.get("signature", ""),
        "description_draft": fn.get("description_draft", ""),
        "source_file": analysis.get("source", ""),

        # 参数 & 返回值 (JSON 字符串)
        "parameters_json": json.dumps(fn.get("parameters", []), ensure_ascii=False),
        "return_value_json": json.dumps(fn.get("return_value", {}), ensure_ascii=False),
        "branches_json": json.dumps(fn.get("branches", []), ensure_ascii=False),

        # 调用关系
        "called_by_text": called_by_text,
        "callings_text": callings_text,
        "calls_json": json.dumps(fn.get("calls", []), ensure_ascii=False),
        "calls_detail_json": json.dumps(fe.get("calls_detail", []), ensure_ascii=False),

        # 函数评估
        "branch_num": fe.get("branch_num", 0),
        "cyclomatic_complexity": fe.get("cyclomatic_complexity", 0),
        "complexity_level": fe.get("complexity_level", ""),
        "interactivity": fe.get("interactivity", 0),
        "criticality": fe.get("criticality", 0),

        # 校验结果
        "validate_errors": validate.get("errors", 0),
        "validate_warnings": validate.get("warnings", 0),
        "validate_score": validate.get("score", 0),
        "validate_ok": str(validate.get("ok", False)),

        # 产物列表
        "artifacts_json": json.dumps(artifacts, ensure_ascii=False, indent=2),

        # 路径 (结构化，供 LLM 使用)
        "paths_json": json.dumps(path_summaries, ensure_ascii=False),
        "path_count": len(paths),
        "paths_note": fn.get("paths_note", ""),
    }


def _param_desc(p: dict) -> str:
    parts = []
    name = p.get("name", "")
    t = p.get("type", "")
    if p.get("is_pointer"):
        parts.append("pointer")
    if p.get("is_const"):
        parts.append("const")
    desc = ", ".join(parts)
    return f"{desc} parameter" if desc else f"`{t}` parameter"
```

### 4.7 LLM #1 — Description + Constraint

```
┌─────────────────────────────────────────────────────┐
│ 模型:       GPT-4o / Claude Sonnet 5                │
│ 上下文窗口:  16K                                     │
│ Temperature: 0.3                                     │
│ Max Tokens:  1024                                    │
├─────────────────────────────────────────────────────┤
│ SYSTEM 提示词 → 见 5.2 节                             │
│ USER 提示词   → 见 5.2 节                             │
├─────────────────────────────────────────────────────┤
│ 输出变量:    desc_constraint (text)                   │
│ 输出格式:    自由文本（Markdown）                      │
└─────────────────────────────────────────────────────┘
```

### 4.8 LLM #2 — Verification Criteria

```
┌─────────────────────────────────────────────────────┐
│ 模型:       GPT-4o / Claude Sonnet 5                │
│ Temperature: 0.3                                     │
│ Max Tokens:  512                                     │
├─────────────────────────────────────────────────────┤
│ SYSTEM 提示词 → 见 5.3 节                             │
│ USER 提示词   → 见 5.3 节                             │
├─────────────────────────────────────────────────────┤
│ 输出变量:    verification_text (text)               │
└─────────────────────────────────────────────────────┘
```

### 4.9 LLM #3 — Test Goals per Path

```
┌─────────────────────────────────────────────────────┐
│ 模型:       GPT-4o / Claude Sonnet 5                │
│ Temperature: 0.3                                     │
│ Max Tokens:  2048                                    │
├─────────────────────────────────────────────────────┤
│ SYSTEM 提示词 → 见 5.4 节                             │
│ USER 提示词   → 见 5.4 节                             │
├─────────────────────────────────────────────────────┤
│ 输出变量:    test_goals_json (text)                  │
│ 输出格式:    JSON 数组 [{path_index, test_case_id,    │
│              test_goal, precondition, action,         │
│              expected_result, post_condition}]        │
└─────────────────────────────────────────────────────┘
```

### 4.10 Template — 组装最终输出

```markdown
# {{code.function_name}} — Detailed Design / 详细设计

**Function ID:** `{{code.function_id}}`
**Declaration:** `{{code.signature}}`
**Source File:** {{code.source_file}}

---

## Description / 功能描述

{{llm_desc.desc_constraint}}

---

## Constraint / 约束条件

*(contained in LLM #1 output)*

---

## Verification Criteria / 验证标准

{{llm_verify.verification_text}}

---

## Parameter / Returned Value / 参数与返回值

| Name | I/O | Type | Range | Description |
|------|-----|------|-------|-------------|
*(auto-generated from analysis.json)*

---

## Function Evaluation / 函数评估

| Metric | Value |
|--------|-------|
| Branch Count / 分支数 | {{code.branch_num}} |
| Cyclomatic Complexity / 圈复杂度 | {{code.cyclomatic_complexity}} ({{code.complexity_level}}) |
| Interactivity / 交互性 | {{code.interactivity}} |
| Criticality / 关键性 | {{code.criticality}} |

---

## Called By / 被调用

{{code.called_by_text}}

---

## Callings / 调用

{{code.callings_text}}

---

## Validation / 校验

- Errors: {{code.validate_errors}}
- Warnings: {{code.validate_warnings}}
- Score: {{code.validate_score}}

---

## Flowchart / 流程图

![{{code.function_name}}]({{code.artifacts_json.png_url}})

---

## Test Cases / 测试用例

### Overview / 概览

*(table from LLM #3 output)*

### Detailed / 详细

{{llm_tests.test_goals_json}}

---

## Artifacts / 产物

{{code.artifacts_json}}

---

## Notes / 备注

- 路径数={{code.path_count}}（理论组合上界，需语义过滤）
- {{code.paths_note}}
- 校验状态: {{code.validate_ok}}
```

### 4.11 Answer 节点

```
输出变量: result (text) = {{#template.output#}}

同时通过 API 返回给调用方。
```

---

## 5. LLM Prompt 模板（含Few-Shot）

### 5.1 通用 SYSTEM 前缀

```text
You are an embedded C/C++ software engineer working on automotive-grade
detailed design documentation. Your output must be:

1. Technically precise — use correct C/C++ terminology
2. Concise — prefer bullet points over long paragraphs
3. Traceable — every claim must reference specific code constructs
4. Bilingual — key headings in English and Chinese

The function has been analyzed by a deterministic parser (code2flowchart).
The structured analysis data (branches, paths, calls, parameters) is the
source of truth. You enhance it with semantic understanding — do NOT invent
branches, paths, or calls that are not in the analysis data.
```

### 5.2 LLM #1 — Description + Constraint

```text
## Task

Based on the function analysis JSON below, generate:

### 1. Description (2-4 sentences)
Describe: WHAT the function does, WHEN it is called (use case), HOW it works
(main processing logic), and what external dependencies it has.

### 2. Constraint (bullet list)
List constraints on:
- Parameter validity ranges
- State preconditions before calling
- Timing/ordering requirements
- Any invariants that must hold

## Function Data

- Name: {{code.function_name}}
- Signature: {{code.signature}}
- Parser description: {{code.description_draft}}
- Parameters: {{code.parameters_json}}
- Return: {{code.return_value_json}}
- Calls: {{code.calls_json}}
- Call detail (non-deduplicated): {{code.calls_detail_json}}
- Branch count: {{code.branch_num}}
- Cyclomatic Complexity: {{code.cyclomatic_complexity}} ({{code.complexity_level}})
- Called by: {{code.called_by_text}}

## Few-Shot Example

### Input:
Function: charge_i2c_send
Signature: static LPI2C_Status_t charge_i2c_send(U8 chip_addr, U8 reg_addr, U16 data)
Parser: "contains 3 control-flow branch point(s); calls lpi2c_send, osDelay"
Parameters: [{name: "chip_addr", direction: "input", type: "U8", ...}]
CC: 6 (Medium)

### Output:
## Description
I2C register write with automatic retry. Prepares a 3-byte send buffer
(reg_addr + data LSB/MSB), then calls lpi2c_send() in a retry loop bounded
by I2C_RETRY_COUNT. On LPI2C_STATUS_OK/NACK/ERROR, exits immediately.
Between retries, inserts osDelay(I2C_RETRY_DELAY_MS) to meet I2C bus
timing. Used by charge_apply_single_port_power, charge_enter_shutdown,
charge_exit_shutdown, set_port_power, and ctrl_pd.

## Constraint
- chip_addr: valid 7-bit I2C address (0x00–0x7F). Hardware-dependent; confirm
  LPI2C_CH0 is the correct channel for the target board.
- reg_addr: device-specific register address. Must be supported by the
  target I2C device.
- data: 16-bit register value. Upper/lower byte order follows device spec.
- Precondition: LPI2C peripheral must be initialized (LPI2C_Init).
- Timing: I2C_RETRY_DELAY_MS must be >= device minimum inter-byte delay.
- Re-entrancy: Not thread-safe — uses shared send_buf on stack.
```

### 5.3 LLM #2 — Verification Criteria

```text
## Task

Based on the function analysis, generate Verification Criteria.
Each criterion should be a bullet point describing:
- What to verify (return value, output parameter, side effect)
- Under what condition
- Expected behavior

## Function Data

- Name: {{code.function_name}}
- Parameters: {{code.parameters_json}}
- Return: {{code.return_value_json}}
- Calls: {{code.calls_json}}
- Branches: {{code.branches_json}}

## Few-Shot Example

### Output:
- Verify when lpi2c_send returns LPI2C_STATUS_OK on first attempt:
  function returns LPI2C_STATUS_OK, osDelay is NOT called, retry count = 0.
- Verify when lpi2c_send returns non-terminal error (not OK/NACK/ERROR):
  osDelay is called, retry counter increments, lpi2c_send is retried.
- Verify after I2C_RETRY_COUNT+1 attempts with non-terminal errors:
  function returns the last error status, loop exits via retry<=I2C_RETRY_COUNT
  becoming false.
- Verify send_buf is correctly populated: buf[0]=reg_addr, buf[1]=data&0xFF,
  buf[2]=(data>>8)&0xFF.
- Mock lpi2c_send to validate the correct channel (LPI2C_CH0) and parameters
  (chip_addr, send_buf pointer, length=3, stop=TRUE, timeout=I2C_TIMEOUT_MS).
```

### 5.4 LLM #3 — Test Goals per Path

```text
## Task

For each code path listed below, generate a detailed test case specification.
Return a JSON array — one object per path.

## Path Data (JSON)

{{code.paths_json}}

## Function Context

- Name: {{code.function_name}}
- Signature: {{code.signature}}
- Parameters: {{code.parameters_json}}
- Calls: {{code.calls_json}}
- Test Framework: {{start.test_framework}}
- Test Environment: {{start.test_env}}

## Output JSON Schema

[
  {
    "path_index": 1,
    "test_case_id": "SWDD_XXX_F001_UT001",
    "test_goal": "One sentence describing what this path verifies",
    "design_method": "Equivalence Classes | Boundary Values | Error Guessing | Analysis of requirements",
    "test_method": "Requirement-based test | Fault injection test | Walk-through | Static code analysis",
    "precondition": "Mock setup, initial state, input values",
    "action": "The specific function call with concrete parameter values",
    "expected_result": "What assertions must pass (return value, output params, side effects)",
    "post_condition": "System state after test execution"
  },
  ...
]

## Few-Shot Example

### Input Path:
{
  "index": 5,
  "sequence": "1-2-3-4-12-13-14",
  "flavor": "immediate-success",
  "labels": ["1","2","3 yes","4","12 yes break","13","14 return"],
  "conditions": [
    "while (retry <= I2C_RETRY_COUNT) -> 3 yes -> status = lpi2c_send(...)",
    "if (...) -> 12 yes break -> ",
    "return status -> 14 return -> End"
  ]
}

### Output:
{
  "path_index": 5,
  "test_case_id": "SWDD_CHARGE_F001_UT005",
  "test_goal": "Verify first I2C send attempt returns OK immediately — no retry, no delay",
  "design_method": "Equivalence Classes",
  "test_method": "Requirement-based test",
  "precondition": "Mock lpi2c_send to return LPI2C_STATUS_OK. Mock osDelay — should NOT be called.",
  "action": "Call charge_i2c_send(chip_addr=0x50, reg_addr=0x00, data=0x1234)",
  "expected_result": "Returns LPI2C_STATUS_OK. osDelay is never called (Times(0)). lpi2c_send called exactly once with (LPI2C_CH0, 0x50, send_buf, 3, TRUE, I2C_TIMEOUT_MS).",
  "post_condition": "No state changes beyond function return. retry counter not visible externally."
}
```

---

## 6. 产物管理与存储

### 6.1 本地文件存储

```
artifact_store/
├── a1b2c3d4/                          # job_id
│   ├── charge_i2c_send.drawio
│   ├── charge_i2c_send.png
│   ├── charge_i2c_send.svg
│   ├── charge_i2c_send.analysis.json
│   ├── charge_i2c_send.dd.md
│   ├── charge_i2c_send.ut.md
│   ├── charge_i2c_send.ut.cpp
│   └── charge_i2c_send.ut.c
├── e5f6g7h8/
│   └── ...
```

### 6.2 定时清理

```bash
# crontab: 每天凌晨 3 点清理超过 30 天的产物
0 3 * * * cd /path/to/code2flowchart && python -c "
from api_server.artifacts import cleanup_old_artifacts
n = cleanup_old_artifacts()
print(f'Cleaned {n} old artifact directories')
"
```

### 6.3 S3/MinIO 扩展（可选）

```python
# 在 api_server/artifacts.py 中添加 S3 后端
import boto3

def save_to_s3(job_id: str, out_dir: Path, bucket: str, endpoint: str) -> dict:
    s3 = boto3.client("s3", endpoint_url=endpoint)
    urls = {}
    for f in out_dir.iterdir():
        if f.is_file():
            key = f"artifacts/{job_id}/{f.name}"
            s3.upload_file(str(f), bucket, key)
            urls[f.suffix.lstrip(".")] = f"{endpoint}/{bucket}/{key}"
    return urls
```

---

## 7. 部署方案

### 7.1 Docker Compose（推荐）

```yaml
# docker-compose.yml
version: "3.8"

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "5100:5100"
    environment:
      - API_HOST=0.0.0.0
      - API_PORT=5100
      - ARTIFACT_STORE=/data/artifacts
      - ARTIFACT_RETENTION_DAYS=30
      - ANALYSIS_TIMEOUT=180
      - MAX_SOURCE_SIZE=2097152
    volumes:
      - artifact_data:/data/artifacts
      - /etc/localtime:/etc/localtime:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5100/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  artifact_data:
```

```dockerfile
# Dockerfile
FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl graphviz && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖
RUN pip install --no-cache-dir flask gunicorn Pillow

# 复制应用代码
COPY api_server/ /app/api_server/
COPY scripts/ /app/scripts/
COPY references/ /app/references/
COPY skills/ /app/skills/
COPY output/ /app/output/

# 创建 artifact store 目录
RUN mkdir -p /data/artifacts

EXPOSE 5100

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5100", \
     "--timeout", "180", \
     "--access-logfile", "-", \
     "api_server.app:app"]
```

```bash
# 启动
docker compose up -d

# 查看日志
docker compose logs -f api
```

### 7.2 Nginx 反向代理

```nginx
# /etc/nginx/sites-available/code2flowchart
server {
    listen 443 ssl;
    server_name cf.example.com;

    ssl_certificate     /etc/ssl/cf.crt;
    ssl_certificate_key /etc/ssl/cf.key;

    client_max_body_size 5m;

    location / {
        proxy_pass http://127.0.0.1:5100;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 180s;
    }
}
```

### 7.3 Dify 中配置 HTTP Request

```
本地 Docker:  URL = http://host.docker.internal:5100/analyze
局域网:       URL = http://192.168.1.100:5100/analyze
公网:         URL = https://cf.example.com/analyze
              Header: Authorization: Bearer <API_TOKEN>
```

---

## 8. 测试与验证

### 8.1 API 服务测试

```bash
# 1. 健康检查
curl http://localhost:5100/health

# 2. 基础分析
curl -s -X POST http://localhost:5100/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "source_code": "int add(int a, int b) { if (a > 0) return a + b; return b; }",
    "target_function": "add",
    "project_prefix": "SWDD_TEST"
  }' | python -m json.tool | head -40

# 3. 带项目根目录的调用者搜索
curl -s -X POST http://localhost:5100/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "source_code": "static int helper(int x) { return x * 2; }\nint main() { return helper(5); }",
    "target_function": "helper",
    "project_prefix": "SWDD_TEST",
    "project_root": "/path/to/project"
  }' | python -c "import json,sys; d=json.load(sys.stdin); print(json.dumps(d.get('callers',[]), indent=2))"

# 4. LLM 增强回写
curl -s -X PUT http://localhost:5100/enrich \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "abc123",
    "function_name": "add",
    "enriched": {
      "description": "Simple integer addition with sign check.",
      "constraint": "No constraints.",
      "verification_criteria": "- Verify a>0 case returns a+b.\n- Verify a<=0 returns b.",
      "test_cases": []
    }
  }'

# 5. 产物下载
curl -O http://localhost:5100/artifacts/abc123/add.drawio
```

### 8.2 Dify 工作流测试

在 Dify 工作室中点击 **Run**，输入：

```
source_code:
static LPI2C_Status_t charge_i2c_read(U8 chip_addr, U8 reg_addr,
    U8 *data, U16 len) {
    LPI2C_Status_t status = LPI2C_STATUS_ERROR;
    U8 retry = 0U;
    while (retry <= I2C_RETRY_COUNT) {
        status = lpi2c_receive(LPI2C_CH0, chip_addr, reg_addr,
                               data, len, 1U, I2C_TIMEOUT_MS);
        if ((status == LPI2C_STATUS_OK) ||
            (status == LPI2C_STATUS_NACK) ||
            (status == LPI2C_STATUS_ERROR)) break;
        if (retry < I2C_RETRY_COUNT) osDelay(I2C_RETRY_DELAY_MS);
        retry++;
    }
    return status;
}

target_function: charge_i2c_read
project_prefix: SWDD_CHARGE
test_framework: google_test_fff
test_env: software-in-the-loop
```

预期输出包含：流程图 PNG、DD 文档、6 个测试用例、GoogleTest 骨架代码。

### 8.3 验证清单

- [ ] API `/health` 返回 200
- [ ] API `/analyze` 返回 `"ok": true`
- [ ] analysis.json 中 `function_evaluation` 字段完整
- [ ] callers 数组不为空（如果提供了 project_root）
- [ ] validate.errors == 0
- [ ] DD.md 包含所有章节
- [ ] UT.md 路径数与 analysis 一致
- [ ] Dify 工作流无超时
- [ ] 产物可下载

---

## 9. CI/CD 集成

### 9.1 GitHub Actions

```yaml
# .github/workflows/code2flowchart-check.yml
name: code2flowchart API check

on:
  push:
    paths:
      - "code2flowchart/**"

jobs:
  test-api:
    runs-on: ubuntu-latest
    services:
      api:
        image: code2flowchart-api:latest
        ports:
          - 5100:5100
    steps:
      - name: Health check
        run: curl -f http://localhost:5100/health
      - name: Smoke test
        run: |
          curl -s -X POST http://localhost:5100/analyze \
            -H "Content-Type: application/json" \
            -d '{"source_code":"int f(){return 0;}","project_prefix":"CI"}' \
            | python -c "import json,sys; assert json.load(sys.stdin)['ok']"
```

---

## 10. 故障排查

| 症状 | 可能原因 | 排查方法 |
|------|----------|----------|
| Dify HTTP Request 超时 | 函数太大，分析耗时 >120s | 增大 `ANALYSIS_TIMEOUT` 和 Dify 超时设置 |
| analysis.json 为空 | 解析器不认识函数签名（模板/宏） | 查看 API 返回的 stderr；手动展开宏后重试 |
| Called By 始终为空 | `project_root` 路径不正确 | 在 API 服务器上手动执行 grep 验证路径 |
| validate.errors > 0 | drawio XML 结构问题 | 查看 API 返回的 validate.output |
| LLM 节点输出格式错误 | Prompt 中 JSON schema 描述不清 | 调低 temperature，增强 few-shot 示例 |
| 产物下载 404 | job_id 或文件名不匹配 | 检查 `artifacts_json` 中的 URL |
| Docker 内无法访问 API | 网络隔离 | 使用 `host.docker.internal` 替代 localhost |
