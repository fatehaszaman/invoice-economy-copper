"""Narrow tracked/staged-file guard, not a comprehensive credential scanner.

Read Git's index blobs rather than working-tree files so a staged secret cannot
be hidden by changing the working copy. Output rule/path/line only, never content.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path, PurePosixPath

RULES = {
    "private_key": re.compile(rb"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----"),
    "github_token": re.compile(
        rb"(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})"
    ),
    "aws_access_key_id": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
}


def forbidden_path(path: str) -> bool:
    p = PurePosixPath(path)
    name = p.name.lower()
    return (
        ((name == ".env" or name.startswith(".env.")) and name != ".env.example")
        or name.endswith((".db", ".sqlite", ".sqlite3", ".pem", ".key", "-wal", "-shm"))
        or (path.startswith("ingest/archive/") and name.endswith((".bin", ".meta.json")))
    )


def scan_blob(path: str, data: bytes) -> list[dict[str, str | int]]:
    findings: list[dict[str, str | int]] = []
    if forbidden_path(path):
        findings.append({"path": path, "line": 0, "rule": "restricted_file"})
    for line_no, line in enumerate(data.splitlines(), 1):
        for name, pattern in RULES.items():
            if pattern.search(line):
                findings.append({"path": path, "line": line_no, "rule": name})
    return findings


def scan_index(root: Path) -> list[dict[str, str | int]]:
    entries = subprocess.check_output(
        ["git", "ls-files", "--stage", "-z"], cwd=root,
    ).split(b"\0")
    findings = []
    for entry in entries:
        if not entry:
            continue
        metadata, path_bytes = entry.split(b"\t", 1)
        mode, oid, stage = metadata.split()
        path = path_bytes.decode("utf-8", errors="replace")
        if stage != b"0" or mode not in {b"100644", b"100755"}:
            findings.append({"path": path, "line": 0, "rule": "non_regular_index_entry"})
            continue
        blob = subprocess.check_output(["git", "cat-file", "blob", oid.decode()], cwd=root)
        findings.extend(scan_blob(path, blob))
    return findings


def main() -> int:
    import json

    root = Path(__file__).resolve().parents[1]
    findings = scan_index(root)
    for finding in findings:
        print(json.dumps(finding, sort_keys=True))
    print(f"Repository hygiene: {len(findings)} finding(s) in the Git index.")
    return int(bool(findings))


if __name__ == "__main__":
    raise SystemExit(main())
