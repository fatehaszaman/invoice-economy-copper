"""Pre-registration lock.

Converts "I pre-registered" from a claim into a build dependency.

`make estimate` requires a valid pcs.lock. The lock records the hash of the
frozen PCS config alongside the commit that introduced PREREGISTRATION.md.
If the instrument definition changed after pre-registration, the build fails
and names the drift rather than quietly producing a tuned result.

A reviewer can verify the whole mechanism in about thirty seconds:

    git log --diff-filter=A --format='%ad %h' -- PREREGISTRATION.md
    git log --diff-filter=A --format='%ad %h' -- research/
    cat pcs.lock
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK_PATH = ROOT / "pcs.lock"
LOCKED_FILES = [
    "config/pcs.yaml",
    "config/exposure.yaml",
    "config/events.yaml",
    "PREREGISTRATION.md",
]


class LockError(RuntimeError):
    """Raised when the instrument definition drifted after pre-registration."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def fingerprint() -> dict:
    files = {}
    for rel in LOCKED_FILES:
        p = ROOT / rel
        if not p.exists():
            raise LockError(f"locked file missing: {rel}")
        files[rel] = _sha256(p)

    prereg_commit = _git(
        "log", "--diff-filter=A", "--format=%H", "--", "PREREGISTRATION.md"
    ).splitlines()
    return {
        "version": 1,
        "files": files,
        "prereg_commit": prereg_commit[-1] if prereg_commit else None,
        "locked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def write_lock() -> dict:
    fp = fingerprint()
    LOCK_PATH.write_text(json.dumps(fp, indent=2, sort_keys=True) + "\n")
    return fp


def verify_lock() -> dict:
    """Raise unless the current config matches the lock. Called by `make estimate`."""
    if not LOCK_PATH.exists():
        raise LockError(
            "pcs.lock is missing. Run `make lock` BEFORE estimation. The lock is "
            "what makes the pre-registration claim verifiable."
        )
    locked = json.loads(LOCK_PATH.read_text())
    current = fingerprint()

    drift = [
        rel
        for rel in LOCKED_FILES
        if locked["files"].get(rel) != current["files"].get(rel)
    ]
    if drift:
        raise LockError(
            "PCS instrument definition drifted after pre-registration: "
            + ", ".join(drift)
            + ". Either revert the change, or record it in DECISIONS.md with the "
            "old value, new value, reason, date, and whether the result changed — "
            "then re-lock deliberately."
        )
    return locked


if __name__ == "__main__":  # pragma: no cover
    print(json.dumps(write_lock(), indent=2, sort_keys=True))
