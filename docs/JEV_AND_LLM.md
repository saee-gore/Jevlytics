# Jev and Claude

Jevlytics uses two models. Jev is a classifier from the TypeSafe SDK. Claude is an Anthropic language model. Each one suggests an answer. Neither one authorises a tool to run.

## Jev

The adapter in `app/jev/adapter.py` is the only code that calls the TypeSafe SDK. Everything else uses the typed decisions in `app/jev/decisions.py`.

### Scope and risk

For each message, Jev answers two questions.

- **Scope.** One label from this fixed set:
  - `SUPPORTED_ANALYTICS`: a question about the caller's own aggregate analytics with a clear metric.
  - `NEEDS_CLARIFICATION`: an analytics question missing details, such as a time period.
  - `OUT_OF_SCOPE`: a question outside payment analytics.
  - `SENSITIVE_OR_UNSAFE`: a request for credentials, raw customer or card records, or harmful content.
  - `PROMPT_INJECTION_OR_POLICY_BYPASS`: an attempt to override instructions, reveal configuration, run SQL or shell commands, or read another merchant's data.
- **Risk.** A rating compared with `JEV_RISK_BLOCK_THRESHOLD`.

Jev is given the caller's merchant, which the server sets, and the message. The message is marked as untrusted. The scope criteria are fixed text in `app/jev/decisions.py`.

### Tool choice

If the scope is `SUPPORTED_ANALYTICS`, Jev chooses one tool from the enabled tools the caller's role allows, or none. An answer outside that list is rejected.

### Settings

| Setting | Default | Purpose |
|---|---|---|
| `TYPESAFE_API_KEY` | none | Required for Jev |
| `TYPESAFE_DEFAULT_MODEL` | `jev-latest` | Model alias sent to the SDK |
| `JEV_SCOPE_MIN_CONFIDENCE` | set in `app/config.py` | Minimum confidence for the scope label |
| `JEV_TOOL_MIN_CONFIDENCE` | set in `app/config.py` | Minimum confidence for the tool choice |
| `JEV_RISK_BLOCK_THRESHOLD` | set in `app/config.py` | Risk level that blocks a request |

The thresholds have not been calibrated against the live service. Calibration needs the evaluation run described below.

### Failures

Jev errors are `JevUnavailableError` (the service cannot be reached or is not configured) and `JevInvalidOutputError` (the answer does not match the label set). Either error returns `temporarily_unavailable`, and no tool runs.

## Claude

The provider in `app/llm/provider.py` makes two calls.

- **Parameter extraction.** Claude turns the message into the parameters of the tool Jev chose. The answer must match a strict schema. The policy engine checks the parameters again.
- **Explanation.** Claude writes the answer from the approved result only. It does not receive credentials or SQL.

### Settings

| Setting | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | none | Required for Claude |
| `LLM_MODEL` | `claude-haiku-5-5` | Model name |
| `LLM_TIMEOUT_SECONDS` | set in `app/config.py` | Time limit for each call |
| `LLM_MAX_TOKENS` | set in `app/config.py` | Output limit for each call |

Analytics questions need this key, because parameter extraction uses Claude. Without it, they return `temporarily_unavailable`.

### Failures

`LLMUnavailableError` (the service cannot be reached or is not configured) and `LLMOutputError` (the answer does not match the schema) each lead to a fixed status. Neither lets an unchecked answer reach the analytics layer.

## What neither model can do

- Add a tool, enable a disabled tool, or change a user's role.
- Set or change the merchant. The merchant comes from the signed-in token.
- Write or run SQL.
- Read credentials or configuration.
- Authorise a tool to run. The policy engine does that, and the audit entry must be written first.

## Evaluation

`scripts/run_jev_eval.py` runs the cases in `data/jev_eval/jev_eval_cases.jsonl`. The file holds 73 cases. The cross-merchant cases are `xm-001` to `xm-009`.

The evaluation has not been run against the live Jev service. No accuracy figures are available yet.

## Cross-merchant screening

A deterministic screen runs before Jev and does not depend on it. Jev is also told the caller's merchant and labelled to refuse other merchants' data. See [CROSS_MERCHANT_ACCESS.md](CROSS_MERCHANT_ACCESS.md).
