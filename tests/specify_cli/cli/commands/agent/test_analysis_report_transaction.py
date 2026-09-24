"""Real Git acceptance proof for report-only recording."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.mission import app

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]
SLUG = "analysis-01M38YDX"
REPORT = f"kitty-specs/{SLUG}/analysis-report.md"
BODY = "---\nschema: analysis-findings/v1\nfindings: []\ncounts: {critical: 0, high: 0, medium: 0, low: 0, info: 0}\n---\n\n# Analysis\nNo findings.\n"


def git(root: Path, *args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True).stdout


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "report-work")
    git(root, "config", "user.name", "Test")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "commit.gpgsign", "false")
    charter = root / ".kittify/charter"
    charter.mkdir(parents=True)
    (root / ".kittify/config.yaml").write_text("charter: .kittify/charter/charter.yaml\n")
    (charter / "charter.yaml").write_text("mission_type_activations: [software-dev]\n")
    mission = root / "kitty-specs" / SLUG
    (mission / "tasks").mkdir(parents=True)
    for name in ("spec.md", "plan.md", "tasks.md"):
        (mission / name).write_text(f"# {name}\nMaterial definition.\n")
    (mission / "tasks/WP01-proof.md").write_text("---\nwork_package_id: WP01\ntitle: Proof\n---\nDefinition.\n")
    (mission / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01M38YDX000000000000000001",
                "mission_slug": SLUG,
                "slug": SLUG,
                "mission_type": "software-dev",
                "topology": "single_branch",
                "target_branch": "report-work",
            }
        )
    )
    (root / "application.txt").write_text("baseline\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "seed")
    monkeypatch.chdir(root)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(root))
    monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)
    return root


def invoke(*extra: str):
    return CliRunner().invoke(app, ["record-analysis", "--mission", SLUG, "--json", *extra], input=BODY)


def test_report_only_preserves_unrelated_partial_staging(repo: Path):
    app_file = repo / "application.txt"
    app_file.write_text("staged\n")
    git(repo, "add", "application.txt")
    app_file.write_text("staged\nunstaged\n")
    (repo / "untracked.txt").write_bytes(b"untracked\x00bytes")
    staged = git(repo, "ls-files", "--stage", "-v", "--", "application.txt")
    head = git(repo, "rev-parse", "HEAD").strip()

    result = invoke("--report-only")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["commit_status"] == "committed"
    assert git(repo, "rev-parse", "HEAD^").strip() == head
    assert git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").decode().splitlines() == [REPORT]
    assert git(repo, "ls-files", "--stage", "-v", "--", "application.txt") == staged
    assert app_file.read_text() == "staged\nunstaged\n"
    assert (repo / "untracked.txt").read_bytes() == b"untracked\x00bytes"


def test_default_still_refuses_unrelated_work(repo: Path):
    (repo / "application.txt").write_text("pending\n")
    result = invoke()
    assert result.exit_code == 1
    assert "DIRTY_WORKTREE" in result.output
    assert not (repo / REPORT).exists()


@pytest.mark.parametrize(
    "path", [".kittify/charter/charter.yaml", ".kittify/config.yaml", f"kitty-specs/{SLUG}/spec.md", f"kitty-specs/{SLUG}/tasks/WP01-proof.md"]
)
def test_dirty_material_input_refuses_before_write(repo: Path, path: str):
    with (repo / path).open("a") as stream:
        stream.write("\n# changed\n")
    head = git(repo, "rev-parse", "HEAD")
    result = invoke("--report-only")
    assert result.exit_code == 1, result.output
    assert "DIRTY_ANALYSIS_INPUT" in result.output
    assert not (repo / REPORT).exists()
    assert git(repo, "rev-parse", "HEAD") == head


def test_failed_commit_never_reports_success(repo: Path):
    hook = repo / ".git/hooks/pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    head = git(repo, "rev-parse", "HEAD")
    result = invoke("--report-only")
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["success"] is False
    assert payload["commit_status"] == "written_uncommitted"
    assert git(repo, "rev-parse", "HEAD") == head
