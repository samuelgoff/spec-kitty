# Design decisions

- Preserve PRIMARY report placement across caller topologies.
- Reuse Git path-scoped canonical commit; no alternate commit-tree or hook policy.
- Fail closed on dirty material inputs and unsupported state. Post-commit races return explicit recovery outcomes; no automatic reset.
- Existing capacity exception allows branch reuse only; no fourth checkout. Immutable qualified runtime keeps sibling work independent of mutable source.
