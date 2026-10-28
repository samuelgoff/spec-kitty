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
        'Path(sys.argv[1]).write_text(\'<testsuite tests="1"><testcase name="ok"/></testsuite>\')\n',
        encoding="utf-8",
    )
    (repo / ".kittify").mkdir()
    (repo / ".kittify/config.yaml").write_text(
        f"review:\n  test_timeout_seconds: {timeout}\n  test_command: {sys.executable} suite.py {{output_file}}\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=repo, check=True)
    return repo


def _capture(repo: Path):
    return capture_baseline(repo, "main", "WP01", "budget", repo / "kitty-specs/budget", "WP01", scope_source=DeclaredCommandScopeSource(repo_root=repo))


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
        ["suite.py"],
        repo_root=repo,
        baseline=baseline,
        scope_source=DeclaredCommandScopeSource(repo_root=repo),
    )
    assert verdict.outcome is pre_review_gate.GateOutcome.NO_NEW_FAILURES
    assert observed == [(1200, False), (1200, True)]
    assert verdict.budget_assessment.effective_budget_seconds == 1200


def test_configured_short_budget_actually_stops_head(tmp_path: Path) -> None:
    repo = _repo(tmp_path, timeout=1, sleep=2)
    verdict = pre_review_gate.evaluate_pre_review_gate(
        ["suite.py"],
        repo_root=repo,
        baseline=None,
        scope_source=DeclaredCommandScopeSource(repo_root=repo),
    )
    assert verdict.outcome is pre_review_gate.GateOutcome.TIMED_OUT
    assert "after 1s" in verdict.reason


@pytest.mark.parametrize("declaration", ["0", "-1", "true", "1.5", ".inf", "null", "'1200'", "86401", "999999999999999999999999"])
def test_invalid_declared_budget_refuses_before_command(tmp_path: Path, declaration: str) -> None:
    from specify_cli.review.test_timeout import InvalidReviewTestTimeout

    repo = _repo(tmp_path, timeout=1200)
    config = repo / ".kittify/config.yaml"
    config.write_text(f"review:\n  test_timeout_seconds: {declaration}\n  test_command: touch SHOULD_NOT_EXIST\n")
    with pytest.raises(InvalidReviewTestTimeout, match="review.test_timeout_seconds"):
        pre_review_gate.evaluate_pre_review_gate(
            ["suite.py"],
            repo_root=repo,
            baseline=None,
            scope_source=DeclaredCommandScopeSource(repo_root=repo),
        )
    assert not (repo / "SHOULD_NOT_EXIST").exists()


def test_default_and_explicit_api_budget(tmp_path: Path) -> None:
    from specify_cli.review.test_timeout import resolve_review_test_timeout

    assert resolve_review_test_timeout(tmp_path) == 300
    repo = _repo(tmp_path, timeout=1200)
    assert resolve_review_test_timeout(repo, 7) == 7


def test_legacy_baseline_honors_configured_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.review import baseline as module

    repo = _repo(tmp_path, timeout=1200)
    observed: list[int] = []
    original = module.run_configured_command_template

    def record(*args, **kwargs):
        observed.append(kwargs["timeout"])
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "run_configured_command_template", record)
    result = capture_baseline(repo, "main", "WP01", "budget", repo / "kitty-specs/budget", "WP01")
    assert result is not None and result.failed == 0
    assert observed == [1200]


def test_short_baseline_budget_is_unknown_not_clean(tmp_path: Path) -> None:
    repo = _repo(tmp_path, timeout=1, sleep=2)
    result = _capture(repo)
    assert result is not None and result.failed != 0


def test_configured_budget_does_not_suppress_real_failure(tmp_path: Path) -> None:
    repo = _repo(tmp_path, timeout=1200)
    baseline = _capture(repo)
    (repo / "suite.py").write_text(
        "import sys\nfrom pathlib import Path\n"
        'Path(sys.argv[1]).write_text(\'<testsuite tests="1"><testcase name="new_failure"><failure message="regression"/></testcase></testsuite>\')\n'
        "raise SystemExit(1)\n"
    )
    verdict = pre_review_gate.evaluate_pre_review_gate(
        ["suite.py"],
        repo_root=repo,
        baseline=baseline,
        scope_source=DeclaredCommandScopeSource(repo_root=repo),
    )
    assert verdict.outcome is pre_review_gate.GateOutcome.NEW_FAILURES


def test_changed_budget_recaptures_instead_of_reusing_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, timeout=300)
    first = _capture(repo)
    assert first is not None and first.test_timeout_seconds == 300
    config = repo / ".kittify/config.yaml"
    config.write_text(config.read_text().replace("test_timeout_seconds: 300", "test_timeout_seconds: 1200"))
    second = _capture(repo)
    assert second is not None and second.test_timeout_seconds == 1200
    assert _capture(repo) == second


def test_invalid_budget_is_not_masked_by_cached_receipt(tmp_path: Path) -> None:
    from specify_cli.review.test_timeout import InvalidReviewTestTimeout

    repo = _repo(tmp_path, timeout=300)
    assert _capture(repo) is not None
    config = repo / ".kittify/config.yaml"
    config.write_text(config.read_text().replace("test_timeout_seconds: 300", "test_timeout_seconds: true"))
    with pytest.raises(InvalidReviewTestTimeout):
        _capture(repo)


def test_transition_uses_planning_authority_not_execution_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from specify_cli.cli.commands.agent import tasks_move_task_gates as gates
    from specify_cli.review.gate_registry import get_gate_handler
    from specify_cli.status import Lane

    authority = _repo(tmp_path, timeout=1200)
    execution = tmp_path / "execution"
    execution.mkdir()
    (execution / "suite.py").write_bytes((authority / "suite.py").read_bytes())
    (execution / ".kittify").mkdir()
    (execution / ".kittify/config.yaml").write_text("review:\n  test_timeout_seconds: 1\n  test_command: touch WRONG_AUTHORITY\n")
    monkeypatch.setattr(gates, "_mt_resolve_gate_baseline", lambda _st: None)
    state = SimpleNamespace(force=False, old_lane=Lane.IN_PROGRESS, target_lane=Lane.FOR_REVIEW)
    inputs = gates._TransitionGateInputs(execution, ("suite.py",), execution, authority)
    context = gates._mt_build_transition_gate_context(state, inputs)
    verdict = get_gate_handler("spec-kitty-pre-review").run(context)
    assert context.test_timeout_seconds == 1200
    assert verdict.budget_assessment.effective_budget_seconds == 1200
    assert not (execution / "WRONG_AUTHORITY").exists()


def test_transition_invalid_budget_cannot_fail_open_before_capture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from specify_cli.cli.commands.agent import tasks_move_task_gates as gates
    from specify_cli.review.test_timeout import InvalidReviewTestTimeout
    from specify_cli.status import Lane

    repo = _repo(tmp_path, timeout=0)
    state = SimpleNamespace(target_lane=Lane.FOR_REVIEW, owned=None, main_repo_root=repo)
    monkeypatch.setattr(gates, "_mt_pre_review_gate_skip_reason", lambda _st: None)

    def forbidden(_st):
        pytest.fail("invalid configuration reached baseline execution")

    monkeypatch.setattr(gates, "_mt_capture_baseline_if_missing", forbidden)
    with pytest.raises(InvalidReviewTestTimeout):
        gates._mt_run_transition_gates(state)


def test_stale_receipt_load_is_unverified_after_failed_recapture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from specify_cli.cli.commands.agent import tasks_move_task_gates as gates

    repo = _repo(tmp_path, timeout=300)
    assert _capture(repo) is not None
    artifact = repo / "kitty-specs/budget/tasks/WP01/baseline-tests.json"
    config = repo / ".kittify/config.yaml"
    config.write_text(config.read_text().replace("test_timeout_seconds: 300", "test_timeout_seconds: 1200"))
    monkeypatch.setattr(gates, "_mt_baseline_artifact_location", lambda _st: (artifact.parent, "WP01", artifact))
    state = SimpleNamespace(owned=None, main_repo_root=repo)
    assert gates._mt_resolve_gate_baseline(state) is None
    assert artifact.exists()  # Historical evidence is retained; it cannot qualify the new budget.


@pytest.mark.parametrize("budget", [True, False, 0, -1, 1.5, "1200", None, 86401])
def test_malformed_receipt_budget_cannot_match_project_budget(tmp_path: Path, budget: object) -> None:
    import json

    from specify_cli.review.test_timeout import InvalidReviewTestTimeout

    repo = _repo(tmp_path, timeout=1)
    receipt = _capture(repo)
    assert receipt is not None
    data = receipt.to_dict()
    data["test_timeout_seconds"] = budget
    artifact = repo / "kitty-specs/budget/tasks/WP01/baseline-tests.json"
    artifact.write_text(json.dumps(data))
    with pytest.raises(InvalidReviewTestTimeout):
        _capture(repo)


@pytest.mark.parametrize("primary_budget", ["300", "true"])
def test_owned_lazy_capture_uses_owned_command_and_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, primary_budget: str) -> None:
    from types import SimpleNamespace

    from specify_cli.cli.commands.agent import tasks_move_task_gates as gates
    from specify_cli.cli.commands.agent import workflow_executor
    from specify_cli.review.baseline import BaselineTestResult
    from specify_cli.status import Lane

    primary = _repo(tmp_path, timeout=300)
    owned = tmp_path / "owned"
    subprocess.run(["git", "worktree", "add", "-q", "-b", "owned-lane", str(owned), "main"], cwd=primary, check=True)
    selected_marker = tmp_path / "owned-command-ran"
    primary_marker = tmp_path / "primary-command-ran"
    primary_config = primary / ".kittify/config.yaml"
    primary_config.write_text(primary_config.read_text().replace("test_timeout_seconds: 300", f"test_timeout_seconds: {primary_budget}") + f"# primary\n")
    primary_config.write_text(primary_config.read_text().replace("suite.py {output_file}", f"suite.py {{output_file}}; touch {primary_marker}"))
    owned_config = owned / ".kittify/config.yaml"
    owned_config.write_text(
        owned_config.read_text()
        .replace("test_timeout_seconds: 300", "test_timeout_seconds: 1200")
        .replace("suite.py {output_file}", f"suite.py {{output_file}}; touch {selected_marker}")
    )
    feature = owned / "kitty-specs/budget"
    artifact = feature / "tasks/WP01/baseline-tests.json"
    monkeypatch.setattr(gates, "_mt_baseline_artifact_location", lambda _st: (feature, "WP01", artifact))
    monkeypatch.setattr(gates, "_mt_baseline_capture_ref", lambda _st, _ref: "main")
    # This fixture isolates configuration selection; publication placement is a separate seam.
    monkeypatch.setattr(workflow_executor, "_baseline_artifact_needs_commit", lambda *_args: False)
    state = SimpleNamespace(
        old_lane=Lane.IN_PROGRESS,
        target_lane=Lane.FOR_REVIEW,
        main_repo_root=primary,
        repo_root=owned,
        owned=SimpleNamespace(owned_root=owned),
        task_id="WP01",
        mission_slug="budget",
        review_base_ref=None,
        target_branch="owned-lane",
        json_output=True,
    )
    try:
        gates._mt_capture_baseline_if_missing(state)
        result = BaselineTestResult.load(artifact)
        assert result is not None and result.test_timeout_seconds == 1200
        assert selected_marker.exists()
        assert not primary_marker.exists()
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(owned)], cwd=primary, check=True)
