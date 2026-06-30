---
name: codex-starhub
description: Design and operate Codex StarHub, a Codex-led orchestration scheme for calling external large language models such as Doubao, GLM, Qwen, Kimi, OpenAI, or browser-based chat services. Use when planning model routing, multi-model review, API or web-model adapters, token budgeting, fallback logic, or a Codex-centered AI workflow that delegates tasks to other models and then integrates their results.
---

# Codex StarHub

## Mission

Use Codex as the main controller and treat external models as callable specialists. Codex StarHub decides which model should handle a task, controls context and token budget, gathers responses, runs verification when needed, and returns the final integrated answer or code change through Codex.

## Operating Model

Prefer API or MCP adapters for stable providers. Use browser automation only as a fallback for models that have no accessible API or when the user explicitly wants to operate a web chat surface.

```text
User request
  -> Codex main controller
  -> Task classifier
  -> Token budget manager
  -> Model router
  -> Provider adapter: Doubao / GLM / Qwen / Kimi / OpenAI / browser chat
  -> Critic and synthesis
  -> Codex final answer or workspace edits
```

## Model Roles

- Codex: primary planner, code executor, file editor, final judge, and integrator.
- Doubao: Chinese writing, dialogue polishing, summaries, and user-facing explanations.
- GLM: Chinese knowledge reasoning, structured analysis, and general review.
- Qwen: Chinese technical reasoning, code assistance, and long-context work when configured.
- Kimi: long document reading, evidence extraction, and document-heavy synthesis.
- OpenAI models: complex reasoning, coding, architecture, and high-stakes final review.

## Routing Rules

Use a simple deterministic rule first, then allow Codex to adjust based on context:

- Send simple rewrite, summary, or tone tasks to a cheaper or writing-focused model.
- Send code, architecture, debugging, and repo edits to Codex or a strong coding model.
- Send long document tasks to a long-context model, or chunk and summarize before routing.
- Send high-risk or ambiguous answers through at least one critic model before finalizing.
- Use fallback models when a provider fails, times out, returns low confidence, or exceeds budget.

## Token Budget

Before calling any model, estimate:

```text
remaining_context = model_context_limit - system_tokens - input_tokens - history_tokens - reserved_output_tokens
```

Keep `reserved_output_tokens` explicit. For web chat models that do not expose usage data, estimate locally:

- Chinese text: roughly 1 token per Chinese character.
- English text: roughly 1 token per 3-4 characters.
- Code: roughly 1 token per 2-4 characters.

If the request exceeds budget, trim irrelevant history, summarize old context, chunk documents, or retrieve only relevant sections instead of sending everything.

## Adapter Contract

Expose each model through the same logical interface:

```json
{
  "model": "doubao",
  "prompt": "task-specific prompt",
  "max_output_tokens": 3000,
  "temperature": 0.2,
  "context": []
}
```

Return a normalized response:

```json
{
  "model": "doubao",
  "answer": "...",
  "usage": {
    "input_tokens": 1200,
    "output_tokens": 800,
    "remaining_tokens": 123000
  },
  "status": "ok"
}
```

## Workflow

1. Classify the task: coding, writing, summary, long-context, research, review, or planning.
2. Select one or more models from the configured roles.
3. Calculate token budget and reserve output tokens before the call.
4. Call the provider through an API, MCP server, or browser adapter.
5. Record model, prompt hash, estimated or returned usage, latency, and status.
6. Ask a critic model to review important outputs.
7. Let Codex synthesize the final answer and perform any local file operations.

## Reference

Read `references/starhub-architecture.md` when the user asks for a concrete implementation plan, file layout, adapter design, token tracking details, or browser-based model integration.
