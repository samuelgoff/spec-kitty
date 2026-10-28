"""Project-owned review budgets apply to the existing baseline/head entry points."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from specify_cli.review import pre_review_gate
from specify_cli.review.baseline import capture_baseline
from specify_cli.review.scope_source import DeclaredCommandScopeSource

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _repo(tmp_path: Path, *, timeout: int, sleep: int = 0) -> Path:
    repo = tmp_path / "project"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "suite.py").write_text(
        f"import time, sys\nfrom pathlib import Path\ntime.sleep({sleep})\n"
        "Path(sys.argv[1]).write_text('<testsuite tests=\"1\"><testcase name=\"ok\"/></testsuite>')\n",
        encoding="utf-8",
    )
    (repo / ".kittify").mkdir()
    (repo / ".kittify/config.yaml").write_text(
        f"review:\n  test_timeout_seconds: {timeout}\n"
        f"  test_command: {sys.executable} suite.py {{output_file}}\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=repo, check=True)
    return repo


def _capture(repo: Path):
    return capture_baseline(repo, "main", "WP01", "budget", repo / "kitty-specs/budget", "WP01",
                            scope_source=DeclaredCommandScopeSource(repo_root=repo))


def test_configured_budget_reaches_both_actual_runners(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, timeout=1200)
    observed: list[tuple[int, bool]] = []
    original = pre_review_gate._run_raw_command

    def record(*args, **kwargs):
        observed.append((kwargs["timeout"], kwargs.get("serialize", True)))
        return original(*args, **kwargs)

    monkeypatch.setattr(pre_review_gate, "_run_raw_command", record)
    baseline = _capture(repo)
    assert baseline is not None and baseline.failed == 0
    verdict = pre_review_gate.evaluate_pre_review_gate(
        ["suite.py"], repo_root=repo, baseline=baseline,
        scope_source=DeclaredCommandScopeSource(repo_root=repo),
    )
    assert verdict.outcome is pre_review_gate.GateOutcome.NO_NEW_FAILURES
    assert observed == [(1200, False), (1200, True)]
    assert verdict.budget_assessment.effective_budget_seconds == 1200


def test_configured_short_budget_actually_stops_head(tmp_path: Path) -> None:
    repo = _repo(tmp_path, timeout=1, sleep=2)
    verdict = pre_review_gate.evaluate_pre_review_gate(
        ["suite.py"], repo_root=repo, baseline=None,
        scope_source=DeclaredCommandScopeSource(repo_root=repo),
    )
    assert verdict.outcome is pre_review_gate.GateOutcome.TIMED_OUT
    assert "after 1s" in verdict.reason
