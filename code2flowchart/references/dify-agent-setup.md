# Dify Agent Setup

Use this reference when building a Dify Workflow, Chatflow, or Agent around `code2Flowchart`.

## Target Architecture

Keep deterministic code analysis outside the LLM, then feed the structured result into Dify:

1. User inputs a C/C++ function, source file, or project snippet.
2. A wrapper service runs `scripts/code2flowchart.py`.
3. The service returns `.analysis.json` plus the `.drawio` link. Return preview, Mermaid, path, or report links only when explicitly requested.
4. Dify uses `.analysis.json` to generate the function description, cyclomatic-complexity explanation, branch test plan, mock plan, and unit-test code.
5. A final Dify answer node returns the report and artifact links.

Do not ask the LLM to re-parse the raw C/C++ when `.analysis.json` is available. Use the JSON as the source of truth.

## Recommended First Version

Start with a Dify Workflow plus an external HTTP service. This is faster to iterate than a full Dify tool plugin.

### External Service Contract

Expose one endpoint:

```text
POST /analyze
```

Request body:

```json
{
  "source_code": "int add(int a, int b) { return a + b; }",
  "filename": "demo.c",
  "target_function": "add",
  "test_framework": "google_test_fff",
  "options": {
    "generate_png": true,
    "include_paths": true
  }
}
```

Response body:

```json
{
  "ok": true,
  "analysis": {},
  "artifacts": {
    "drawio": "https://example/artifacts/demo.drawio"
  },
  "errors": []
}
```

For local/private deployments, artifact values can be file paths. For Dify Cloud or browser delivery, use downloadable URLs or upload generated files to object storage.

### Dify Workflow Nodes

Create a Workflow app with these nodes:

1. Start node
   - `source_code`: paragraph text.
   - `filename`: text, default `input.c`.
   - `target_function`: text, optional.
   - `test_framework`: select, options from `.analysis.json.test_framework_options`.
   - `project_context`: paragraph text, optional.

2. HTTP Request node
   - Method: `POST`.
   - URL: your wrapper service `/analyze`.
   - Body: pass Start variables as JSON.
   - Output: `analysis_response`.

3. Code/Variable extraction node
   - Extract `analysis_response.analysis`.
   - Extract `analysis_response.artifacts`.
   - Extract `analysis.functions[0]` when the request targets one function.

4. LLM node: function description
   - Input: selected function JSON.
   - Output: polished function purpose, inputs, outputs, side effects, and dependencies.

5. LLM node: branch test plan
   - Input: `branches`, `paths`, `parameters`, `return_value`, `unit_test_scenarios`.
   - Output: table of branch/path tests with setup, stimulus, expected result, mocks, and covered path.

6. LLM node: unit-test code
   - Input: test plan, selected framework, calls, output parameters, return value.
   - Output: compile-oriented test skeleton.

7. Answer node
   - Return function summary, complexity, call list, branch paths, unit-test code, and artifact links.

## Prompt Inputs

Pass these JSON slices into LLM nodes instead of the full source whenever possible:

- `function.name`
- `function.signature`
- `function.parameters`
- `function.input_parameters`
- `function.output_parameters`
- `function.return_value`
- `function.cyclomatic_complexity`
- `function.calls`
- `function.called_by_in_file`
- `function.branches`
- `function.paths`
- `function.unit_test_scenarios`
- `function.recommended_test_frameworks`

## Function Description Prompt

Use a prompt like:

```text
You are generating a C/C++ function analysis report.
Use the JSON as the source of truth.
Describe:
1. Purpose
2. Input parameters: name, type, direction, range, description
3. Output parameters and return value
4. Side effects and called functions
5. Cyclomatic complexity and why

Function JSON:
{{function_json}}
```

## Branch Test Prompt

Use a prompt like:

```text
Generate branch/path test cases from the function JSON.
Each test case must include:
- test name
- covered path edge sequence
- input values
- output parameter expectations
- return value expectation
- mock/fake setup for called functions
- notes for boundary values

Do not invent branches that are not in function.paths.
Function JSON:
{{function_json}}
Selected framework:
{{test_framework}}
```

## Unit Test Code Prompt

Use a prompt like:

```text
Generate unit-test skeleton code.
Use the selected framework and the test plan.
Keep external functions mocked/faked.
Preserve path IDs in comments, for example: // covers path 1-2-3-5
If information is missing, leave TODO comments instead of inventing production APIs.

Framework:
{{test_framework}}
Function JSON:
{{function_json}}
Test plan:
{{test_plan}}
```

## Framework Selection

Use these defaults:

- C++ code: `google_test`, or `catch2` / `doctest` for lightweight projects.
- C code with hardware or OS dependencies: `unity_cmock` or `ceedling`.
- C modules tested from a C++ harness: `google_test_fff`.
- The user name `FSF` is treated as an alias candidate for `FFF/Fake Function Framework` until the exact framework is confirmed.

## Dify Tool Plugin Route

After the HTTP workflow is stable, convert the wrapper into a Dify Tool Plugin.

Recommended tool shape:

```yaml
identity:
  name: code2flowchart_analyze
description:
  human:
    en_US: Analyze C/C++ functions and return flowchart artifacts plus analysis JSON.
  llm: Analyze C/C++ code for flowcharts, branches, parameters, complexity, calls, and unit-test scenarios.
parameters:
  - name: source_code
    type: string
    required: true
    form: llm
  - name: filename
    type: string
    required: false
    form: llm
  - name: target_function
    type: string
    required: false
    form: llm
  - name: test_framework
    type: select
    required: false
    form: form
```

The tool implementation should call `code2flowchart.py`, read the generated `.analysis.json`, and return JSON to Dify.

## Calling A Published Workflow

Dify workflows can be invoked after publishing with:

```bash
curl --request POST \
  --url https://{api_base_url}/workflows/run \
  --header "Authorization: Bearer <token>" \
  --header "Content-Type: application/json" \
  --data '{
    "inputs": {
      "source_code": "int add(int a, int b) { return a + b; }",
      "filename": "demo.c",
      "target_function": "add",
      "test_framework": "google_test_fff"
    },
    "response_mode": "blocking",
    "user": "code2flowchart-user"
  }'
```

If sending source as a file, upload the file first and pass the returned file ID into workflow inputs or the `files` field according to the app design.

## Operational Notes

- Run the wrapper service in a sandboxed workspace.
- Set file size, timeout, and output retention limits.
- Do not expose generated local file paths directly from Dify Cloud; return downloadable URLs.
- Keep `.analysis.json` schema version in prompts so later changes can be handled explicitly.
- Save the raw `.analysis.json` in Dify logs for debugging missed branches or bad tests.
- Add human review before accepting generated unit-test code into a repository.

## Official Dify References

- Workflow API: `https://docs.dify.ai/api-reference/workflows/run-workflow`
- File upload API: `https://docs.dify.ai/api-reference/files/upload-file`
- Tool plugin guide: `https://docs.dify.ai/en/develop-plugin/dev-guides-and-walkthroughs/tool-plugin`
