"""The lock is what makes the pre-registration claim verifiable."""
import json

import pytest

from pcs import lock
from pcs.lock import LockError, fingerprint, verify_lock, write_lock


@pytest.fixture(autouse=True)
def isolated_lock(tmp_path, monkeypatch):
    """Tests must never regenerate the repository's preregistration lock."""
    monkeypatch.setattr(lock, "LOCK_PATH", tmp_path / "pcs.lock")


def test_lock_captures_all_preregistered_files():
    fp = fingerprint()
    assert set(fp["files"]) == {
        "config/pcs.yaml",
        "config/exposure.yaml",
        "config/events.yaml",
        "PREREGISTRATION.md",
    }


def test_lock_records_the_preregistration_commit():
    fp = fingerprint()
    assert fp["prereg_commit"], "the commit that introduced PREREGISTRATION.md"


def test_verify_passes_on_an_unmodified_tree():
    write_lock()
    assert verify_lock()["version"] == 1


def test_verify_detects_config_drift(tmp_path):
    """Changing the instrument after pre-registration must fail the build."""
    write_lock()
    locked = json.loads(lock.LOCK_PATH.read_text())
    locked["files"]["config/pcs.yaml"] = "0" * 64
    lock.LOCK_PATH.write_text(json.dumps(locked, indent=2, sort_keys=True))
    try:
        with pytest.raises(LockError, match="drifted after pre-registration"):
            verify_lock()
    finally:
        write_lock()


def test_missing_lock_blocks_estimation():
    original = lock.LOCK_PATH.read_text() if lock.LOCK_PATH.exists() else None
    lock.LOCK_PATH.unlink(missing_ok=True)
    try:
        with pytest.raises(LockError, match="missing"):
            verify_lock()
    finally:
        if original is not None:
            lock.LOCK_PATH.write_text(original)
        else:
            write_lock()
