# NEST Hackathon Brief — Open-Problems Track

You are participating in the NEST research hackathon. Instead of picking a
protocol layer, this track points you at the open research problems we are
currently tracking.

**Task**: Pick one open problem from `docs/hackathon/problems/` and submit
a PR addressing it.

The current open problems are:

{{ PROBLEMS_LIST }}

(If the list above is empty, the open-problems track docs have not been
checked in yet — the runner will fall back to the vague brief automatically.
You should not reach this line in that case.)

## Submission rules

- Branch name: `hackathon/<problem-slug>-<short-handle>`.
- Do not push to `main`, `master`, `hackathon/*` (other branches), or
  `claude/*`.
- Run the standard local checks before you push:
  - `uv sync`
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run pyright`
  - `uv run pytest -v`
- PR body must reference the problem file you picked, summarise the
  approach, and call out what would *invalidate* your fix (failure modes).
