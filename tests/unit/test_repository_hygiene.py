"""Narrow security guard regression fixtures; no real credentials."""
import subprocess

import pytest

from scripts.check_repository_hygiene import forbidden_path, scan_blob, scan_index


@pytest.mark.parametrize(
    "path",
    [".env", "nested/.env.local", "warehouse/data/live.db",
     "local.sqlite3", "private.pem", "data.db-wal",
     "ingest/archive/a.bin", "ingest/archive/a.meta.json"],
)
def test_restricted_paths(path):
    assert forbidden_path(path)


def test_safe_documentation_and_placeholder_example():
    assert not forbidden_path(".env.example")
    assert not forbidden_path("warehouse/sql/as_of.sql")
    assert scan_blob("README.md", b"Use environment variables; never commit credentials.") == []


@pytest.mark.parametrize(
    "value,rule",
    [(b"gh" + b"p_" + b"x" * 36, "github_token"),
     (b"AK" + b"IA" + b"A" * 16, "aws_access_key_id"),
     (b"-----BEGIN " + b"RSA PRIVATE KEY-----", "private_key")],
)
def test_secrets_are_reported_without_values(value, rule):
    result = scan_blob("config.txt", b"safe line\n" + value)
    assert result == [{"path": "config.txt", "line": 2, "rule": rule}]
    assert value.decode() not in str(result)


def test_scans_index_not_clean_working_copy(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    path = tmp_path / "settings.txt"
    secret = b"gh" + b"p_" + b"x" * 36
    path.write_bytes(secret)
    subprocess.run(["git", "add", "settings.txt"], cwd=tmp_path, check=True)
    path.write_text("clean working copy")
    assert scan_index(tmp_path) == [
        {"path": "settings.txt", "line": 1, "rule": "github_token"}
    ]
