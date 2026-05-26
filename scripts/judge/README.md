<!-- SPDX-License-Identifier: Apache-2.0 -->

# NEST Hackathon Judge Panel

`scripts/judge/` runs an N-judge LLM panel against every open
`hackathon/*` PR and writes a deterministic scoreboard to
`docs/hackathon/scores.json`.

The panel is provider-pluggable. Two live providers are supported today,
plus a deterministic mock for CI smoke runs.

## Providers

| `--provider` | Default model      | API-key env var      | SDK package    |
| ------------ | ------------------ | -------------------- | -------------- |
| `anthropic`  | `claude-opus-4-7`  | `ANTHROPIC_API_KEY`  | `anthropic`    |
| `openai`     | `gpt-5.5`          | `OPENAI_API_KEY`     | `openai`       |

- `anthropic` is the default. The rubric is sent as a
  `cache_control: ephemeral` system block so rubric tokens are billed
  once per 5-min window across N judges.
- `openai` uses `openai.AsyncOpenAI` against `chat.completions` with
  `response_format={"type": "json_object"}` so the JSON contract is
  enforced server-side. OpenAI's caching is implicit per the docs — we
  don't try to be clever.
- Both providers share the same rubric, the same six dimensions, the
  same JSON output schema, and the same median-low aggregation. The
  `scores.json` shape is identical regardless of provider.

If the selected provider's API key is unset, the CLI falls back to a
deterministic `MockJudgeClient` so the scoreboard shape is exercised
end-to-end without spending budget. Use `--mock` to force that path
regardless of env.

## Install

```bash
uv sync --extra judge      # pulls in both anthropic and openai SDKs
# or one provider at a time:
uv pip install "anthropic>=0.30"
uv pip install "openai>=1.0"
```

## Usage

```bash
# Default: Anthropic with claude-opus-4-7
ANTHROPIC_API_KEY=sk-ant-... \
  uv run python -m scripts.judge.run_all --output docs/hackathon/scores.json

# OpenAI with the default gpt-5.5
OPENAI_API_KEY=sk-... \
  uv run python -m scripts.judge.run_all --provider openai

# OpenAI, pinning a specific model
OPENAI_API_KEY=sk-... \
  uv run python -m scripts.judge.run_all --provider openai --model gpt-5.5-pro

# Force mock judges (no API keys required)
uv run python -m scripts.judge.run_all --mock

# Subset of PRs
uv run python -m scripts.judge.run_all --pr 2 --pr 3
```

The scoreboard is idempotent: re-running only re-scores PRs whose HEAD
SHA changed since the last write. Pass `--force` to re-score every PR.

## Tests

```bash
uv run pytest scripts/judge/tests/ -v
```

Live API-touching tests live behind `@pytest.mark.live` and are skipped
unless you pass `-m live` and set the relevant API key.
