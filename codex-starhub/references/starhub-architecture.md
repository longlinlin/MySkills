# Codex StarHub Architecture

## Purpose

Codex StarHub is a practical design for using Codex as the central controller while delegating selected tasks to external large language models such as Doubao, GLM, Qwen, Kimi, OpenAI, or browser-only chat services.

## Recommended Directory Layout

```text
codex-starhub/
  SKILL.md
  agents/
    openai.yaml
  references/
    starhub-architecture.md
```

A runtime implementation can later use this layout:

```text
starhub-runtime/
  config/
    models.yaml
  core/
    router.py
    token_budget.py
    task_classifier.py
    critic.py
  adapters/
    doubao.py
    glm.py
    qwen.py
    kimi.py
    openai_provider.py
    browser_chat.py
  logs/
    calls.jsonl
```

## Model Registry

Keep provider details in configuration rather than hard-coding them:

```yaml
models:
  doubao:
    type: api
    strengths: ["Chinese writing", "summary", "dialogue"]
    max_context_tokens: 128000
    default_output_tokens: 4000
    fallback: qwen

  glm:
    type: api
    strengths: ["Chinese knowledge", "reasoning", "structured analysis"]
    max_context_tokens: 128000
    default_output_tokens: 4000
    fallback: openai

  qwen:
    type: api
    strengths: ["Chinese technical tasks", "code", "long context"]
    max_context_tokens: 128000
    default_output_tokens: 4000
    fallback: openai

  doubao_web:
    type: browser
    url: "https://www.doubao.com"
    strengths: ["temporary browser chat"]
    token_usage_available: false
    fallback: doubao
```

## API Adapter Path

Use the API path when the provider offers an official endpoint. This is preferred because it is stable, returns structured errors, and may expose token usage.

```text
Codex -> local MCP/tool adapter -> provider API -> normalized response -> Codex synthesis
```

Normalize every provider response into:

```json
{
  "model": "qwen",
  "answer": "...",
  "usage": {
    "input_tokens": 1000,
    "output_tokens": 600,
    "total_tokens": 1600,
    "remaining_tokens": 122400
  },
  "status": "ok",
  "error": null
}
```

## Browser Adapter Path

Use browser automation only when API access is unavailable or the user specifically wants to use a web chat product.

```text
Codex -> Playwright/Selenium adapter -> logged-in web chat -> copied answer -> Codex synthesis
```

Expect these limitations:

- Login sessions may expire.
- Page structure can change without notice.
- Captchas or anti-automation checks may block calls.
- Token usage is usually unavailable and must be estimated locally.
- Provider terms should be checked before automating high-volume use.

## Routing Policy

Use this baseline routing policy:

```python
def choose_model(task):
    if task.kind in {"repo_edit", "debugging", "architecture"}:
        return "codex"
    if task.language == "zh" and task.kind in {"writing", "summary", "polish"}:
        return "doubao"
    if task.kind in {"knowledge", "analysis", "structured_review"}:
        return "glm"
    if task.kind in {"code_explanation", "long_context", "technical_summary"}:
        return "qwen"
    return "openai"
```

Use a critic model when:

- The answer will guide code changes, architecture, money, safety, or policy.
- The first model reports uncertainty.
- The answer conflicts with local evidence.
- The task benefits from comparing Chinese model behavior.

## Token Budget Policy

Track both actual and estimated usage:

```text
usable_context = max_context_tokens - reserved_output_tokens
remaining_context = usable_context - system_tokens - history_tokens - task_tokens
```

Recommended defaults:

- Reserve 2000 tokens for short answers.
- Reserve 4000 tokens for normal technical answers.
- Reserve 8000 or more tokens for code review, design docs, or long synthesis.
- Refuse or chunk work when `remaining_context` becomes negative.

For browser-only models, write `"usage_source": "estimated"` in logs.

## Logging

Log each call as JSONL:

```json
{
  "time": "2026-07-01T08:00:00+08:00",
  "model": "doubao",
  "task_type": "zh_summary",
  "adapter": "api",
  "input_tokens": 1200,
  "output_tokens": 900,
  "usage_source": "provider",
  "latency_ms": 2400,
  "status": "ok"
}
```

Do not log raw secrets, API keys, session cookies, or private user content unless the user explicitly asks for auditable prompt archives.

## Implementation Priorities

1. Build `models.yaml` with provider capabilities and context limits.
2. Build a token estimator and budget guard.
3. Build one API adapter first, then add providers gradually.
4. Add a browser adapter only after API routing works.
5. Add critic and fallback flows.
6. Add logging and cost reporting.
