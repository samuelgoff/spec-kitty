# Design decisions

- Preserve PRIMARY report placement across caller topologies.
- Reuse Git path-scoped canonical commit; no alternate commit-tree or hook policy.
- Fail closed on dirty material inputs and unsupported state. Post-commit races return explicit recovery outcomes; no automatic reset.
- Existing capacity exception allows branch reuse only; no fourth checkout. Immutable qualified runtime keeps sibling work independent of mutable source.
- Dependency closure conservatively covers declared project governance and resolved pack roots rather than guessing an incomplete per-file selection. Explicitly exclude runtime/status/cache outputs so context loading does not invalidate its own report. Mutable external roots without qualified cleanliness are refused. Legacy/default freshness remains compatible.
- Read-only Aletheia config inspection confirms a local charter pointer and no declared org pack. Its charter catalog references generated local library files; those declarations belong in the manifest. Actual dirty authority still refuses until its owner reconciles it.
- Qualification is local and explicit: report frontmatter binds a random transaction identifier; its Git-directory receipt starts pending before the report is written and becomes qualified only after parent/tree/input/index/working-byte verification. Freshness rejects missing/pending receipts and requires the verified commit remain reachable. This prevents retained reports from unlocking a mission after HEAD/index-only races or process interruption. A copied report requires fresh analysis/recording in its destination checkout; receipts are not portable attestations.
- The transaction detects cooperative-writer races rather than claiming a filesystem-wide lock. Failed transactions preserve all concurrent state and report the observed commit when HEAD advanced. No reset or rollback is authorized.
- Bundled authority is content-pinned without machine-local paths. Canonical selected-template resolution rejects mutable global templates; project overrides and org roots must be inside the repository and committed. Aletheia's selected global spec/plan templates matched the bundled defaults byte-for-byte; hashes and supported mission-scoped override paths were sent to the owner for reconciliation, with no Aletheia mutation by this work package.

## Implementation log

### User experience findings

- Missing qualification receipts deliberately fail closed after copying an opt-in report to another clone. The command documents rerunning analysis/recording; no silent portable-success claim.
- Task directories can contain ordinary README files; only WP definition frontmatter receives runtime-field normalization.
- `agent action implement` lacks `--owned-checkout`; supported `next` plus `agent tasks move-task --owned-checkout` claimed this work package. The command shown in the initial task text was not accepted by the CLI.

### Known limitations

- Arbitrary external editors are not fenced; all pre/post race checks and failure outcomes are explicit.
- External mutable org/global authority is unsupported by this project-only transaction.
- Full implementation review, final acceptance and publication remain pending. No Aletheia write, HA readiness, merge or deployment is implied.
