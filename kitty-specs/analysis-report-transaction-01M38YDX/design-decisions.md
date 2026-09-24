# Design decisions

- Preserve PRIMARY report placement across caller topologies.
- Reuse Git path-scoped canonical commit; no alternate commit-tree or hook policy.
- Fail closed on dirty material inputs and unsupported state. Post-commit races return explicit recovery outcomes; no automatic reset.
- Existing capacity exception allows branch reuse only; no fourth checkout. Immutable qualified runtime keeps sibling work independent of mutable source.
- Dependency closure conservatively covers declared project governance and resolved pack roots rather than guessing an incomplete per-file selection. Explicitly exclude runtime/status/cache outputs so context loading does not invalidate its own report. Mutable external roots without qualified cleanliness are refused. Legacy/default freshness remains compatible.
- Read-only Aletheia config inspection confirms a local charter pointer and no declared org pack. Its charter catalog references generated local library files; those declarations belong in the manifest. Actual dirty authority still refuses until its owner reconciles it.
