# NEST research harness

Multi-condition, reproducible, dataset-producing infrastructure for running
hackathon-style A/B experiments against the `nest` repo.

This directory ships:

| file                                  | purpose                                                                  |
| ------------------------------------- | ------------------------------------------------------------------------ |
| `conditions.yaml`                     | declarative experiment design (factors + levels + skip rules)            |
| `conditions.py`                       | YAML loader; `compute_cell_id()` for stable hashes                       |
| `agent_runner.py`                     | transport abstraction — fixture (dry-run) or `claude` CLI (live)         |
| `run_condition.py`                    | CLI: run N replicates of one cell, write per-cell JSONL                  |
| `collect.py`                          | merge per-cell JSONLs into `all.jsonl`                                   |
| `analyze.py`                          | three PNG plots (diversity collapse, calibration, iteration efficiency)  |
| `briefs/{vague,layer-enumerated,open-problems}.md` | brief templates wired to the `brief_specificity` factor       |
| `dry_run/fixtures/*.json`             | replayable mocked agent submissions                                      |
| `dry_run/test_dry_run.py`             | default-suite pytest gate over the whole pipeline                        |
| `SCHEMA.md`                           | JSONL row schema (versioned)                                             |

## TL;DR

```bash
# 1. install the optional harness extra (matplotlib)
uv sync --extra harness

# 2. inspect the cells the current conditions.yaml would expand to
uv run python -c "from scripts.harness.conditions import load_conditions; \
  [print(c.cell_id, c.factors) for c in load_conditions().cells()]"

# 3. dry-run one cell against the fixture transport (no agents spawned)
uv run python -m scripts.harness.run_condition --cell <cell_id> --n 4 --dry-run

# 4. aggregate + plot
uv run python -m scripts.harness.collect
uv run python -m scripts.harness.analyze
```

PNGs land in `data/hackathon-runs/`.

## Worked example (dry-run, end-to-end)

```bash
uv sync --extra harness

# pick the first non-skipped cell
CELL=$(uv run python -c "from scripts.harness.conditions import load_conditions; \
  print(next(iter(load_conditions().cells())).cell_id)")

# run 8 fixture-backed replicates for that cell
uv run python -m scripts.harness.run_condition --cell "$CELL" --n 8 --dry-run

# repeat for another cell
CELL2=$(uv run python -c "from scripts.harness.conditions import load_conditions; \
  cells = list(load_conditions().cells()); print(cells[1].cell_id)")
uv run python -m scripts.harness.run_condition --cell "$CELL2" --n 8 --dry-run

# aggregate
uv run python -m scripts.harness.collect

# plot
uv run python -m scripts.harness.analyze

ls data/hackathon-runs/
# -> <cell_id>.jsonl  <cell_id2>.jsonl  all.jsonl
#    diversity_collapse.png  calibration.png  iteration_efficiency.png
```

## Live experiments (spends money)

When you are ready to run real agents:

```bash
# Use clone strategy: each agent gets a fresh `git clone` of the repo, so the
# harness works from any shell on any machine, not just inside Claude Code.
uv run python -m scripts.harness.run_condition \
    --cell "$CELL" --n 100 --live \
    --workdir-strategy clone \
    --workdir-base /tmp/nest-harness-work
```

Live mode shells out to the `claude` CLI in headless mode
(`claude -p <prompt> --output-format stream-json --model <model>`). This is
the simpler of the two viable live transports — the alternative would be the
Anthropic Python SDK with a hand-rolled tool loop, which forces the harness
to reimplement a lot of what the CLI already does (file editing,
bash-tool-with-permissions, branch hygiene, etc.). The CLI path is what is
documented as the reference live transport.

Required external tooling for live mode:

- `claude` CLI on `PATH`, authenticated (`claude login`).
- `git` for the `worktree`/`clone` strategies.
- (Optional but recommended) `gh` for automatic PR-and-CI lookup. If
  missing, the harness still writes the row — `pr_url` is captured but
  `head_sha` / `first_push_ci_*` stay `null` and you can backfill them
  later from the same JSONL.

## Inside Claude Code vs. headless shell

| feature                                    | inside Claude Code                                | headless shell                                                 |
| ------------------------------------------ | ------------------------------------------------- | -------------------------------------------------------------- |
| dry-run + tests + analysis                 | works                                             | works                                                          |
| `--workdir-strategy worktree`              | works (assumes harness invoked inside the repo)   | works                                                          |
| `--workdir-strategy clone`                 | works                                             | **recommended** — most reproducible                            |
| `--live` transport (`claude` CLI)          | not the intended use case (nested Claude)         | works                                                          |
| `gh`-based PR/CI enrichment                | depends on gh-auth in the session                 | depends on gh-auth in the shell                                |

The harness deliberately keeps the `--live` path runnable from a plain shell
(no Claude Code dependency) so you can run real experiments on dedicated
infra, then come back to Claude Code for analysis.

## Reproducibility notes

Every JSONL row carries:

- `harness_version` — semver of this harness package (`scripts/harness/__init__.py`).
- `schema_version` — integer schema version (see `SCHEMA.md`).
- `conditions_version` — integer from `conditions.yaml`.
- `cell_id` — sha256 prefix of `(conditions_version, sorted factors)`.
- `model_id` — concrete version-pinned model id (e.g. `claude-opus-4-7`).
- `prompt_hash` — sha256[:16] of the rendered brief.
- `seed` — derived from `(seed_base, cell_id, run_idx)` via sha256, so a
  fixed `seed_base` + factor combination always produces the same seed.
- `timestamp_utc` — ISO-8601 UTC wall clock.

The `collect.py` aggregator refuses to merge rows whose `schema_version`
disagrees with the current code, which prevents silent schema drift across
runs.

## Open research questions this harness is designed to answer

1. **Diversity collapse**: how much does the *brief specificity* factor
   reduce variance in which protocol layer an agent picks? Compare the
   top-1 / top-3 layer cluster share across `vague`, `layer-enumerated`,
   `open-problems` at large N.
2. **Calibration**: per (model, pre_push_checklist), what is the gap between
   claimed-CI-green and actual-CI-green on first push?
3. **Iteration efficiency**: pushes-to-green distribution; does the
   pre-push checklist factor actually shift the mean?
4. **Brief-specificity sensitivity**: cross-cut diversity, calibration and
   iteration-efficiency by `brief_specificity` to see which axis matters
   most for which outcome.

## Adding a new factor

1. Add a dimension under `dimensions:` in `conditions.yaml`.
2. Bump `conditions_version` — this invalidates old `cell_id`s on purpose.
3. If the factor affects how the brief is rendered, branch on it in
   `run_condition.render_brief()` or add a new `briefs/<level>.md`.
4. If the factor affects how the agent is spawned, branch on
   `cell.factors[...]` inside `run_condition.run_cell()`.

## Adding a new metric

1. Add a pure helper to `analyze.py` (no matplotlib).
2. Add a `plot_<metric>` function.
3. Add a CLI call site in `analyze.main()`.
4. Extend `dry_run/test_dry_run.py::test_analysis_pure_helpers_have_sane_shape`
   with a tiny ground-truth check.

## Why the dry-run is the default

The fixture transport is intentionally the default. Real agent runs cost
real money — having `pytest` exercise the full pipeline without spending a
cent (and without needing network access) is the only way to catch schema
drift before a live run.

The `--live` flag must be passed explicitly to spawn real agents. There is
no auto-detection.
