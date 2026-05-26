# SPDX-License-Identifier: Apache-2.0
"""Run N agent replicates for one experimental cell, write one JSONL per run.

Usage::

    uv run python -m scripts.harness.run_condition \\
        --cell <cell_id> --n 10 --dry-run

The default transport is ``fixture`` (no real agents). Pass ``--live`` to
spawn the ``claude`` CLI in headless mode (cost!). Pass ``--workdir-strategy
worktree|clone`` to choose how each agent gets its own copy of the repo.

Design notes (also in ``README.md``):

* Each agent gets an **isolated working copy** of the repo. Two strategies:
  ``worktree`` (default — uses ``git worktree add``, requires the harness to
  be invoked inside the repo) and ``clone`` (a fresh ``git clone`` for each
  agent — slower but the most reproducible when running from an arbitrary
  shell on CI infrastructure). The ``clone`` strategy is what makes this
  harness usable outside Claude Code.
* The harness does **not** call the GitHub API directly for PR/CI lookup —
  it shells out to ``gh`` when available so credentials are picked up from
  the user's existing config. If ``gh`` is missing, those fields stay
  ``null`` and post-processing can be done offline later.
* JSONL writes are *line-by-line and flushed after each row*, so a crash
  midway through a run loses at most the partial line.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
import random
import shutil
import string
import subprocess
import sys
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from scripts.harness import HARNESS_VERSION, SCHEMA_VERSION
from scripts.harness._calibration import claimed_ci_green
from scripts.harness.agent_runner import (
    AgentSpawnSpec,
    AgentSubmission,
    make_runner,
)
from scripts.harness.conditions import Cell, load_conditions

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "hackathon-runs"
DEFAULT_BRIEFS_DIR = Path(__file__).parent / "briefs"
DEFAULT_FIXTURES_DIR = Path(__file__).parent / "dry_run" / "fixtures"

# Concrete model id mapping. Centralised so JSONL rows stamp the exact
# version-pinned identifier even if the user passed a short name.
MODEL_ID_MAP: dict[str, str] = {
    "opus": "claude-opus-4-7",
    "sonnet": "claude-sonnet-4-7",
    "haiku": "claude-haiku-4-7",
}


# ---------------------------------------------------------------------------
# Workdir strategies.
# ---------------------------------------------------------------------------


@dataclass
class WorkdirHandle:
    path: Path
    cleanup: bool


@contextlib.contextmanager
def make_workdir(
    strategy: str,
    *,
    repo_root: Path,
    base_dir: Path,
    cell_id: str,
    run_idx: int,
) -> Generator[WorkdirHandle, None, None]:
    """Yield an isolated copy of the repo for one agent."""
    base_dir.mkdir(parents=True, exist_ok=True)
    workdir = base_dir / f"{cell_id}-{run_idx}"
    if workdir.exists():
        shutil.rmtree(workdir)

    if strategy == "worktree":
        # Branch name is intentionally local-only; agent will create its own
        # `hackathon/...` branch inside.
        branch = f"harness/{cell_id}-{run_idx}-{_random_token(4)}"
        subprocess.run(  # noqa: S603 — harness-controlled inputs
            ["git", "worktree", "add", "-b", branch, str(workdir), "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )
        try:
            yield WorkdirHandle(path=workdir, cleanup=False)
        finally:
            subprocess.run(  # noqa: S603
                ["git", "worktree", "remove", "--force", str(workdir)],
                cwd=repo_root,
                check=False,
                capture_output=True,
            )
            subprocess.run(  # noqa: S603
                ["git", "branch", "-D", branch],
                cwd=repo_root,
                check=False,
                capture_output=True,
            )

    elif strategy == "clone":
        subprocess.run(  # noqa: S603
            ["git", "clone", "--quiet", str(repo_root), str(workdir)],
            check=True,
            capture_output=True,
        )
        try:
            yield WorkdirHandle(path=workdir, cleanup=True)
        finally:
            if workdir.exists():
                shutil.rmtree(workdir, ignore_errors=True)

    elif strategy == "ephemeral":
        # No git at all — used by --dry-run / fixture transport.
        workdir.mkdir(parents=True, exist_ok=True)
        try:
            yield WorkdirHandle(path=workdir, cleanup=True)
        finally:
            if workdir.exists():
                shutil.rmtree(workdir, ignore_errors=True)

    else:
        raise ValueError(f"unknown workdir strategy: {strategy!r}")


def _random_token(n: int) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choices(alphabet, k=n))  # noqa: S311 — id, not secret


# ---------------------------------------------------------------------------
# Brief rendering.
# ---------------------------------------------------------------------------


def render_brief(brief_specificity: str, briefs_dir: Path) -> tuple[Path, str]:
    """Pick the brief template for a given factor level and return (path, text).

    `open-problems` falls back to `vague.md` if the open-problems doc directory
    does not exist yet (parallel track may not have landed).
    """
    candidate = briefs_dir / f"{brief_specificity}.md"
    if not candidate.exists():
        raise FileNotFoundError(f"No brief for specificity={brief_specificity!r}: {candidate}")
    text = candidate.read_text(encoding="utf-8")

    if brief_specificity == "open-problems":
        problems_dir = REPO_ROOT / "docs" / "hackathon" / "problems"
        if problems_dir.exists():
            problems = sorted(p.name for p in problems_dir.glob("*.md"))
            text = text.replace("{{ PROBLEMS_LIST }}", "\n".join(f"- {p}" for p in problems))
        else:
            fallback = briefs_dir / "vague.md"
            text = (
                "<!-- open-problems track docs not found; falling back to vague brief -->\n\n"
                + fallback.read_text(encoding="utf-8")
            )
    return candidate, text


# ---------------------------------------------------------------------------
# Post-processing: PR / CI lookup via gh CLI (best-effort, optional).
# ---------------------------------------------------------------------------


def enrich_from_github(submission: AgentSubmission) -> dict[str, Any]:
    """Look up PR head SHA, diff size, CI status. Returns a partial row update.

    Always returns a dict — fields stay missing (caller fills `None`) when
    `gh` is unavailable, when the PR URL is malformed, or when the API call
    fails. This is intentionally best-effort: the harness should not refuse
    to write a row just because GitHub is slow.
    """
    out: dict[str, Any] = {}
    if not submission.pr_url:
        return out
    if shutil.which("gh") is None:
        return out

    try:
        repo, number = _parse_pr_url(submission.pr_url)
    except ValueError:
        return out

    pr_json = _gh_json(
        [
            "gh",
            "pr",
            "view",
            str(number),
            "-R",
            repo,
            "--json",
            "headRefOid,additions,deletions,title,headRefName,statusCheckRollup",
        ]
    )
    if pr_json is None:
        return out

    out["head_sha"] = pr_json.get("headRefOid")
    out["lines_added"] = pr_json.get("additions")
    out["lines_removed"] = pr_json.get("deletions")
    out["description"] = pr_json.get("title")
    if not submission.branch:
        out["branch"] = pr_json.get("headRefName")

    rollup_obj: object = pr_json.get("statusCheckRollup") or []
    if isinstance(rollup_obj, list) and rollup_obj:
        rollup = cast("list[Any]", rollup_obj)
        conclusions: list[Any] = []
        for check_obj in rollup:
            if isinstance(check_obj, dict):
                conclusions.append(cast("dict[str, Any]", check_obj).get("conclusion"))
        non_none = [c for c in conclusions if c is not None]
        if non_none and all(c == "SUCCESS" for c in non_none):
            out["first_push_ci_status"] = "success"
            out["first_push_ci_green"] = True
        elif any(c in {"FAILURE", "TIMED_OUT", "CANCELLED"} for c in non_none):
            out["first_push_ci_status"] = "failure"
            out["first_push_ci_green"] = False
        else:
            out["first_push_ci_status"] = "pending"
            out["first_push_ci_green"] = None

    # iterations_to_green: count commits on the branch — proxy for pushes.
    if out.get("first_push_ci_green") is True:
        commits = _gh_json(
            ["gh", "pr", "view", str(number), "-R", repo, "--json", "commits"],
        )
        if commits is not None:
            commit_list_obj: object = commits.get("commits") or []
            if isinstance(commit_list_obj, list):
                commit_list = cast("list[Any]", commit_list_obj)
                out["iterations_to_green"] = max(1, len(commit_list))
    return out


def _parse_pr_url(url: str) -> tuple[str, int]:
    # https://github.com/<owner>/<repo>/pull/<n>
    import re

    m = re.match(r"https://github\.com/([^/]+/[^/]+)/pull/(\d+)", url)
    if not m:
        raise ValueError(f"not a PR URL: {url!r}")
    return m.group(1), int(m.group(2))


def _gh_json(cmd: list[str]) -> dict[str, Any] | None:
    try:
        proc = subprocess.run(  # noqa: S603 — harness-controlled
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    try:
        data: object = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        return cast("dict[str, Any]", data)
    return None


# ---------------------------------------------------------------------------
# Row builder.
# ---------------------------------------------------------------------------


def build_row(
    *,
    cell: Cell,
    run_idx: int,
    seed: int,
    model_level: str,
    prompt_hash: str,
    brief_path: Path,
    transport: str,
    submission: AgentSubmission,
    enrichment: dict[str, Any],
) -> dict[str, Any]:
    """Compose one JSONL row from a submission + GitHub lookup."""
    model_id = MODEL_ID_MAP.get(model_level, model_level)
    final_message = submission.final_message
    fixture_meta = submission.raw_metadata or {}
    row: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "harness_version": HARNESS_VERSION,
        "conditions_version": cell.conditions_version,
        "cell_id": cell.cell_id,
        "factors": dict(cell.factors),
        "run_idx": run_idx,
        "seed": seed,
        "model_id": model_id,
        "prompt_hash": prompt_hash,
        "brief_path": str(brief_path),
        "transport": transport,
        "timestamp_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "duration_seconds": submission.duration_seconds,
        "spawned": submission.spawned,
        "exit_code": submission.exit_code,
        "pr_url": submission.pr_url,
        "branch": submission.branch,
        "head_sha": submission.head_sha,
        "layer_picked": submission.layer_picked,
        "lines_added": None,
        "lines_removed": None,
        "first_push_ci_status": None,
        "first_push_ci_green": None,
        "iterations_to_green": None,
        "claimed_ci_green": claimed_ci_green(final_message),
        "final_message": final_message,
        "transcript_path": submission.transcript_path,
        "description": None,
        "error": submission.error,
    }
    # Fixture transport: trust the fixture's recorded ground truth.
    for key in (
        "lines_added",
        "lines_removed",
        "iterations_to_green",
        "description",
    ):
        if fixture_meta.get(key) is not None:
            row[key] = fixture_meta[key]
    if fixture_meta.get("actual_ci_green_first_push") is not None:
        green = bool(fixture_meta["actual_ci_green_first_push"])
        row["first_push_ci_green"] = green
        row["first_push_ci_status"] = "success" if green else "failure"
    if "claimed_ci_green" in fixture_meta:
        row["claimed_ci_green"] = bool(fixture_meta["claimed_ci_green"])

    # GitHub enrichment wins last (live data > fixture data).
    for key, value in enrichment.items():
        if value is not None:
            row[key] = value
    return row


def derive_seed(seed_base: int, cell_id: str, run_idx: int) -> int:
    payload = f"{seed_base}:{cell_id}:{run_idx}".encode()
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------


def run_cell(
    *,
    cell: Cell,
    n: int,
    transport: str,
    output_dir: Path,
    briefs_dir: Path,
    fixtures_dir: Path,
    workdir_strategy: str,
    workdir_base: Path,
    seed_base: int,
    timeout_seconds: int,
    skip_github: bool,
) -> Path:
    """Run N replicates for one cell and write JSONL to disk. Returns path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{cell.cell_id}.jsonl"

    brief_specificity = cell.factors.get("brief_specificity", "vague")
    brief_path, brief_text = render_brief(brief_specificity, briefs_dir)
    prompt_hash = hashlib.sha256(brief_text.encode("utf-8")).hexdigest()[:16]
    model_level = cell.factors.get("model", "opus")

    runner = make_runner(transport, fixtures_dir=fixtures_dir)

    with out_path.open("w", encoding="utf-8") as fh:
        for run_idx in range(n):
            seed = derive_seed(seed_base, cell.cell_id, run_idx)
            with make_workdir(
                workdir_strategy,
                repo_root=REPO_ROOT,
                base_dir=workdir_base,
                cell_id=cell.cell_id,
                run_idx=run_idx,
            ) as handle:
                spec = AgentSpawnSpec(
                    cell_id=cell.cell_id,
                    run_idx=run_idx,
                    model=model_level,
                    brief_path=brief_path,
                    brief_text=brief_text,
                    prompt_hash=prompt_hash,
                    seed=seed,
                    workdir=handle.path,
                    timeout_seconds=timeout_seconds,
                    extra_env={"NEST_HARNESS_CELL_ID": cell.cell_id},
                )
                submission = runner.run(spec)
                enrichment: dict[str, Any] = {}
                if not skip_github:
                    enrichment = enrich_from_github(submission)
                row = build_row(
                    cell=cell,
                    run_idx=run_idx,
                    seed=seed,
                    model_level=model_level,
                    prompt_hash=prompt_hash,
                    brief_path=brief_path,
                    transport=transport,
                    submission=submission,
                    enrichment=enrichment,
                )
                fh.write(json.dumps(row, sort_keys=True) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one experimental cell.")
    parser.add_argument("--cell", required=True, help="cell_id from conditions.yaml")
    parser.add_argument("--n", type=int, default=10, help="Number of replicates")
    parser.add_argument(
        "--conditions",
        type=Path,
        default=None,
        help="Path to conditions.yaml (default: bundled)",
    )
    parser.add_argument(
        "--briefs-dir",
        type=Path,
        default=DEFAULT_BRIEFS_DIR,
        help="Directory of brief templates",
    )
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=DEFAULT_FIXTURES_DIR,
        help="Fixtures dir (dry-run transport)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Where to write <cell_id>.jsonl",
    )
    parser.add_argument(
        "--workdir-base",
        type=Path,
        default=REPO_ROOT / ".harness-work",
        help="Where to place per-agent workdirs",
    )
    parser.add_argument(
        "--workdir-strategy",
        choices=["worktree", "clone", "ephemeral"],
        default="ephemeral",
        help="How to materialise each agent's workspace",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use the claude-cli transport (spends real money!). Default is fixture.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Force fixture transport. Mutually exclusive with --live.",
    )
    parser.add_argument(
        "--skip-github",
        action="store_true",
        help="Skip gh-CLI enrichment (default off; auto-skipped when gh missing).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=1800,
    )
    parser.add_argument(
        "--seed-base",
        type=int,
        default=None,
        help="Override conditions.yaml `defaults.seed_base`.",
    )
    args = parser.parse_args(argv)

    if args.live and args.dry_run:
        parser.error("--live and --dry-run are mutually exclusive")

    spec = load_conditions(args.conditions)
    cell = spec.get_cell(args.cell)
    if cell is None:
        sys.stderr.write(f"unknown cell_id: {args.cell}\n")
        return 2

    transport = "claude-cli" if args.live else "fixture"
    seed_base = args.seed_base
    if seed_base is None:
        seed_base = int(cell.defaults.get("seed_base", 0))

    out_path = run_cell(
        cell=cell,
        n=args.n,
        transport=transport,
        output_dir=args.output_dir,
        briefs_dir=args.briefs_dir,
        fixtures_dir=args.fixtures_dir,
        workdir_strategy=args.workdir_strategy,
        workdir_base=args.workdir_base,
        seed_base=seed_base,
        timeout_seconds=args.timeout_seconds,
        skip_github=args.skip_github or transport == "fixture",
    )
    sys.stdout.write(f"wrote {out_path}\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
