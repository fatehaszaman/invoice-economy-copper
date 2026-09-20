"""CLI labels and failures are part of the research-integrity contract."""
import subprocess
import sys
from datetime import date

from warehouse.pit import Observation, PITStore


def _database(tmp_path):
    path = tmp_path / "test.db"
    store = PITStore(path)
    store.append(Observation(
        canonical_series_id="volume_oi_churn", economic_object="business_transaction",
        observation_ts=date(2026, 1, 5), publication_ts=date(2026, 1, 5),
        retrieval_ts=date(2026, 1, 5), canonical_value=1.0, unit="ratio",
        source="shfe", frequency="daily",
    ))
    store.conn.close()
    return str(path)


def test_original_cli_returns_failure_for_mixed_frequency(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "scripts.run_realtime", "--db", _database(tmp_path)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 1
    assert "Mixed-frequency PCS is blocked" in result.stdout


def test_monthly_cli_labels_exploration_and_snapshot_limit(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "scripts.run_realtime", "--db", _database(tmp_path),
         "--config", "config/pcs_monthly_exploratory.yaml", "--asof", "2026-02-01"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "exploratory_unvalidated" in result.stdout
    assert "Not a historical real-time backtest" in result.stdout
    assert "unavailable" in result.stdout
