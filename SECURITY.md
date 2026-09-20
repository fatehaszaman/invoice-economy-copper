# Security scope and local evidence protection

This is a local research repository with public-source and potentially licensed
market data. It is not a hosted application and has no implemented user accounts,
network-facing API or production access-control service. The controls below address
specific local risks; they are not a penetration test or a security certification.

## Threat model and implemented controls

| Risk | Implemented control | Boundary |
|---|---|---|
| Audit accidentally changes evidence | SQLite URI `mode=ro` plus `PRAGMA query_only=ON` | Other processes and the ingestion connection can still write |
| Series identifier interpreted as SQL | Bound parameters and allowlisted report names | Query files and local repository code are trusted |
| Raw payload changed or lost | Recompute SHA-256 for each distinct referenced payload | Hash match is byte integrity, not source authenticity or signed provenance |
| Database hash used for path traversal | Require 64 lowercase hexadecimal characters before opening a file | Archive root is chosen by the operator |
| Payload path is a symlink | Reject symlinked payload files | Does not prevent a malicious concurrent filesystem race |
| Secrets or private data accidentally committed | Ignore rules plus Git-index hygiene checks in CI | Limited patterns; not comprehensive secret detection |
| Excess CI token authority | Workflow declares `contents: read` | Repository settings, dependencies and third-party Actions remain separate risks |

Archive verification reads bytes in a stream rather than loading whole payloads.
Missing, malformed, unreadable, symlinked and hash-mismatched references are
reported separately. An attacker who can change both the database and files can
replace evidence consistently; hashes alone do not prevent that. Metadata sidecars,
historical provenance and source identity are not authenticated.

## Repository hygiene

Run this after staging the intended files and before committing:

```bash
make security
```

The scanner reads Git index blobs, not working-tree contents. It catches a staged
credential even if the working copy has subsequently been cleaned. It rejects
tracked database files, raw archive blobs/metadata, environment files other than
`.env.example`, private-key extensions, and non-regular index entries. It recognizes
selected GitHub-token, AWS access-key-ID and PEM private-key patterns. Findings
contain a path, line number and rule, not the matching credential value.

This does not scan untracked files, old commit history, arbitrary API keys,
obfuscated secrets, all personal data or provider-specific license restrictions.
`.gitignore` is not an access-control mechanism and can be bypassed with forced
adds. A clean scan cannot establish that a repository contains no secrets.

Use environment variables or a proper secret manager if an adapter later needs
credentials. Never put credential-bearing URLs or tokens into logs, source URLs,
payload metadata or example configuration. Current public-source adapters do not
require adding secrets to this audit workflow.

## If a credential or licensed file is exposed

Stop publishing the affected material. Revoke and rotate exposed credentials at
their provider before attempting repository cleanup; deleting a working-tree file
does not remove copies or Git history. Inspect the exposure scope and follow the
data provider's license obligations. Review history removal separately because it
rewrites commits and affects other clones.

Do not paste a live credential into an issue or send raw licensed datasets with a
bug report. Report only the affected component and a sanitized reproduction.

## Verification and remaining work

`tests/unit/test_warehouse_audit.py` exercises read-only enforcement, parameter
binding, duplicate detection, unchanged database bytes and archive failure modes.
`tests/unit/test_repository_hygiene.py` exercises restricted paths, selected
credential patterns, redacted findings and index-versus-working-copy behavior.

No dependency vulnerability scan, signed raw-data manifest, encrypted database,
backup/restore drill, role-based access control or concurrent-writer hardening is
implemented. Add those only when deployment, sensitivity or usage warrants them.
Passing these checks does not validate the PCS hypothesis or historical publication
metadata.
