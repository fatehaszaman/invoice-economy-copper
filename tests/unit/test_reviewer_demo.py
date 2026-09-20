"""Ensure the reviewer walkthrough is real, deterministic and fail-closed."""
from pathlib import Path

from scripts.run_demo import collect_evidence, main, render

EXPECTED = Path(__file__).resolve().parents[2] / "docs" / "DEMO.md"


def test_reviewer_evidence_values():
    got = collect_evidence()
    assert got["production_before_revision"] == 100.0
    assert got["production_after_revision"] == 110.0
    assert got["trade_rows_before_retrieval"] == 0
    assert got["net_with_reported_zero_export"] == 500.0
    assert got["net_with_missing_export"] is None
    assert got["absent_series_rows"] == 0
    assert got["duplicate_groups"] == 0
    assert got["matching_payloads"] == 1
    assert got["tampered_payload_status"] == "hash_mismatch"
    assert got["readonly_delete_blocked"] is True
    assert got["rows_after_delete_attempt"] == 5


def test_reviewer_output_is_deterministic_and_matches_document():
    first = render(collect_evidence())
    assert render(collect_evidence()) == first
    assert first == EXPECTED.read_text(encoding="utf-8")


def test_check_rejects_drift_without_overwriting(tmp_path, capsys):
    wrong = tmp_path / "wrong.md"
    wrong.write_text("outdated output\n", encoding="utf-8")
    assert main(["--check", str(wrong)]) == 1
    assert wrong.read_text(encoding="utf-8") == "outdated output\n"
    assert "differs" in capsys.readouterr().out


def test_check_accepts_current_document(capsys):
    assert main(["--check", str(EXPECTED)]) == 0
    assert "matches" in capsys.readouterr().out


def test_check_rejects_missing_document(tmp_path):
    absent = tmp_path / "absent.md"
    assert main(["--check", str(absent)]) == 1
    assert not absent.exists()


def test_cli_output_labels_synthetic_evidence(capsys):
    assert main([]) == 0
    output = capsys.readouterr().out
    assert "SYNTHETIC fixtures" in output
    assert "hash_mismatch" in output
