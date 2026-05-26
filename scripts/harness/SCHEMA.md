# Research-harness JSONL schema

Each agent submission produces **one JSONL row**. Rows are written by
`scripts/harness/run_condition.py` to
`data/hackathon-runs/<cell_id>.jsonl`, then aggregated into
`data/hackathon-runs/all.jsonl` by `scripts/harness/collect.py`.

The schema is **versioned**: the integer `schema_version` field is bumped on
any backwards-incompatible change. `collect.py` refuses to merge rows whose
`schema_version` differs from the current one.

## Row fields (schema_version = 1)

| field                          | type                | description                                                                                  |
| ------------------------------ | ------------------- | -------------------------------------------------------------------------------------------- |
| `schema_version`               | int                 | Always `1` for this schema.                                                                  |
| `harness_version`              | str                 | Semver of the harness code that produced the row (see `scripts/harness/__init__.py`).        |
| `conditions_version`           | int                 | `conditions.yaml` version this cell was derived from.                                        |
| `cell_id`                      | str                 | 12-char hash of `(factors, conditions_version)`. Stable across machines.                     |
| `factors`                      | object[str, str]    | Factor name -> level. Sorted keys.                                                           |
| `run_idx`                      | int                 | Replicate index within the cell, `0 <= run_idx < N`.                                         |
| `seed`                         | int                 | Deterministic seed derived from `(seed_base, cell_id, run_idx)`.                             |
| `model_id`                     | str                 | Concrete model identifier passed to the agent (e.g. `claude-opus-4-7`).                      |
| `prompt_hash`                  | str                 | sha256[:16] of the rendered brief.                                                           |
| `brief_path`                   | str                 | Path to the brief template used.                                                             |
| `transport`                    | str                 | `"claude-cli"`, `"fixture"`, ...                                                             |
| `timestamp_utc`                | str (ISO-8601)      | When the row was written.                                                                    |
| `duration_seconds`             | float \| null       | Wall-clock agent duration.                                                                   |
| `spawned`                      | bool                | Whether the agent process started at all.                                                    |
| `exit_code`                    | int \| null         | Agent process exit code (null on timeout).                                                   |
| `pr_url`                       | str \| null         | GitHub PR URL the agent submitted, if any.                                                   |
| `branch`                       | str \| null         | Head branch of the submission.                                                               |
| `head_sha`                     | str \| null         | Head commit SHA of the submission.                                                           |
| `layer_picked`                 | str \| null         | Protocol layer the agent picked (parsed from branch/PR body).                                |
| `lines_added`                  | int \| null         | `+N` from the diff.                                                                          |
| `lines_removed`                | int \| null         | `-N` from the diff.                                                                          |
| `first_push_ci_status`         | str \| null         | `"success"`, `"failure"`, `"pending"`, or null if no CI run was found.                       |
| `first_push_ci_green`          | bool \| null        | Convenience: `first_push_ci_status == "success"`.                                            |
| `iterations_to_green`          | int \| null         | Number of pushes until CI went green (null if it never did).                                 |
| `claimed_ci_green`             | bool                | Did the agent's final message claim CI / tests pass?                                         |
| `final_message`                | str \| null         | The agent's last assistant text block (used for calibration).                                |
| `transcript_path`              | str \| null         | Absolute path to the raw transcript log.                                                     |
| `description`                  | str \| null         | Free-form one-line PR title / summary if available — used by `analyze.py` for clustering.    |
| `error`                        | str \| null         | Set if the spawn failed before producing a submission.                                       |

## Calibration parsing

`claimed_ci_green` is `True` when the agent's `final_message` matches any of
these case-insensitive patterns:

- `all tests pass`
- `tests pass`
- `ruff clean`
- `ci green`
- `ci is green`
- `pipeline green`
- `all checks pass`

These are intentionally loose. The intent is to capture the agent's *belief*,
not to be exhaustive. Adding patterns is backwards-compatible (no schema
bump). Removing patterns requires a schema bump.

## Clustering for diversity collapse

`analyze.py` clusters submissions primarily by `layer_picked`. When
`description` is available (e.g. from the PR title), it is also used as a
finer-grained second-level key in `(layer_picked, description)` pairs. The
analysis script is deterministic and does not call any embedding model — if
embedding-based clustering is added, it must be implemented in a way that is
seedable from `seed_base`.
