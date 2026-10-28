"""One project-owned execution budget for baseline and candidate review tests."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ruamel.yaml import YAML

DEFAULT_TEST_TIMEOUT_SECONDS = 300
MAX_TEST_TIMEOUT_SECONDS = 86_400


class InvalidReviewTestTimeout(ValueError):
    """A declared review budget cannot safely bound a subprocess run."""


def resolve_review_test_timeout(repo_root: Path, override: int | None = None) -> int:
    """Read a positive, whole-second per-run budget, retaining explicit API overrides.

    The one-day ceiling bounds platform wait conversions and accidental oversized
    declarations. Missing configuration preserves the 300-second default; invalid
    declarations refuse execution rather than becoming an unverified passing gate.
    Resolve against the command's configuration authority, not a detached baseline.
    """
    value: object = override
    if override is None:
        path = repo_root / ".kittify" / "config.yaml"
        config = YAML(typ="safe").load(path) if path.exists() else None
        if config is not None and not isinstance(config, Mapping):
            raise InvalidReviewTestTimeout("Review configuration must be a mapping")
        review = (config or {}).get("review")
        if review is not None and not isinstance(review, Mapping):
            raise InvalidReviewTestTimeout("review must be a mapping")
        value = (review or {}).get("test_timeout_seconds", DEFAULT_TEST_TIMEOUT_SECONDS)
    return validate_review_test_timeout(value)


def validate_review_test_timeout(value: object) -> int:
    """Validate the same budget domain for declarations and persisted receipts."""
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_TEST_TIMEOUT_SECONDS:
        raise InvalidReviewTestTimeout(f"review.test_timeout_seconds must be an integer from 1 to {MAX_TEST_TIMEOUT_SECONDS}")
    return value
