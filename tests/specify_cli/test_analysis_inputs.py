"""Material dependency closure is stable across incidental runtime writes."""

from pathlib import Path

import pytest


def test_declared_authority_and_absent_sentinel(tmp_path: Path):
    from specify_cli.analysis_inputs import collect_material_inputs

    charter = tmp_path / ".kittify/charter"
    charter.mkdir(parents=True)
    (tmp_path / ".kittify/config.yaml").write_text("charter: .kittify/charter/charter.yaml\n")
    (charter / "charter.yaml").write_text(
        "governance:\n  doctrine:\n    authority_paths: [authority]\n    governance_references: [missing.md]\n"
    )
    mission = tmp_path / "kitty-specs/test"
    (mission / "tasks").mkdir(parents=True)
    for name in ("spec.md", "plan.md", "tasks.md", "meta.json"):
        (mission / name).write_text("{}" if name.endswith("json") else name)
    authority = tmp_path / "authority"
    authority.mkdir()
    (authority / "rule.md").write_text("rule")
    before = collect_material_inputs(mission, tmp_path)
    assert before["material:missing.md"]["sha256"] is None
    assert "material:authority/rule.md" in before
    (charter / "context.json").write_text("runtime output")
    (mission / "status.events.jsonl").write_text("runtime output")
    assert collect_material_inputs(mission, tmp_path) == before
    (tmp_path / "missing.md").write_text("new authority")
    assert collect_material_inputs(mission, tmp_path) != before


def test_declared_authority_symlink_escape_rejected(tmp_path: Path):
    from specify_cli.analysis_inputs import MaterialInputError, collect_material_inputs

    root = tmp_path / "repo"
    (root / ".kittify/charter").mkdir(parents=True)
    (root / ".kittify/config.yaml").write_text("charter: .kittify/charter/charter.yaml\n")
    (root / ".kittify/charter/charter.yaml").write_text(
        "governance:\n  doctrine:\n    authority_paths: [authority]\n"
    )
    (root / "authority").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(MaterialInputError, match="symlink"):
        collect_material_inputs(root / "kitty-specs/test", root)
