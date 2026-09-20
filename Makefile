.PHONY: help install test lint ingest canonical ontology warehouse compute lock pcs estimate robustness realtime monthly report determinism all clean security audit

PY := python

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## install dependencies
	$(PY) -m pip install -e ".[dev]"

test:  ## full test suite
	$(PY) -m pytest tests -q

lint:  ## style and type checks
	$(PY) -m ruff check .
	$(PY) -m mypy pcs research warehouse --ignore-missing-imports --explicit-package-bases

ingest:  ## fetch + archive raw payloads (idempotent, resumable)
	$(PY) -m scripts.run_ingest

canonical:  ## units, calendars, identifier resolution
	@echo "canonical layer: see canonical/"

ontology:  ## classify + validate; non-zero exit on violations
	@command -v swipl >/dev/null 2>&1 || { echo "swipl not installed; skipping ontology validation"; exit 0; }
	swipl -g "consult('ontology/flows.pl'), consult('ontology/inventory.pl'), halt."

warehouse:  ## local SQLite vintage store and read-only SQL reports
	@echo "SQLite DDL: warehouse/pit.py; reviewed queries: warehouse/sql/; model: docs/DATA_MODEL.md"

security:  ## narrow secret and restricted-file check against Git index
	$(PY) -m scripts.check_repository_hygiene

audit:  ## read-only warehouse report; provide ARGS with db, asof and expected raw series
	$(PY) -m scripts.audit_warehouse $(ARGS)

compute:  ## Java curves, VAT-adjusted wedge, turnover proxies
	@echo "compute: see compute/"

lock:  ## freeze the PCS instrument definition -> pcs.lock
	$(PY) -m pcs.lock

pcs:  ## original specification (refuses unresolved mixed-frequency scoring)
	@$(PY) -c "from pcs.lock import verify_lock; verify_lock()"
	$(PY) -m scripts.run_realtime

# The pre-registration guarantee is a BUILD DEPENDENCY, not a promise.
# This target refuses to run if the instrument definition drifted after
# PREREGISTRATION.md was committed.
estimate:  ## exposure design, monotonicity, inference (synthetic until ingestion lands)
	@$(PY) -c "from pcs.lock import verify_lock; verify_lock(); print('lock verified: instrument unchanged since pre-registration')"
	$(PY) -m scripts.run_research

robustness:  ## pre-trends, placebos, confounder ladder, spec grid
	@echo "Structural modules implemented: research/placebos.py, research/confounders.py, pcs/sensitivity.py."
	@echo "Validated against the synthetic panel (tests/unit/test_placebos.py, test_confounders.py, test_sensitivity.py)."
	@echo "Cannot run on real copper data yet: no public source publishes a per-channel,"
	@echo "invoice-exposure-tiered outcome panel at the intermediary granularity this design needs."
	@echo "See README \"Live ingestion status\" and \"Open research gap\"."
	@exit 1

realtime:  ## original snapshot diagnostic; not a historical real-time backtest
	$(PY) -m scripts.run_realtime

monthly:  ## exploratory monthly snapshot; unvalidated and not preregistered
	$(PY) -m scripts.run_realtime --config config/pcs_monthly_exploratory.yaml

report:  ## regenerate every figure and table in FINDINGS.md
	@echo "NOT YET IMPLEMENTED: FINDINGS.md does not exist and will not until the analysis runs."
	@exit 1

determinism:  ## run twice, diff outputs, fail on drift
	bash scripts/check_determinism.sh

all: test ontology estimate  ## offline synthetic validation, NOT the empirical pipeline
	@echo "Offline synthetic stages complete. Use make ingest and make monthly for descriptive data."
	@echo "Empirical validation and findings remain unavailable."

clean:
	rm -rf build dist *.egg-info .pytest_cache out
	find . -name __pycache__ -type d -exec rm -rf {} +
