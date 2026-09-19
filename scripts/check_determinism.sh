#!/usr/bin/env bash
# Same data, same config, same seed must produce identical output.
# A research result that cannot be reproduced exactly is not a result.
set -euo pipefail
cd "$(dirname "$0")/.."

run() {
  python - <<'PY'
import hashlib, json
from research.bootstrap import block_bootstrap_beta
from research.exposure import fit_exposure
from research.permutation import permutation_test
from tests.synthetic.make_panel import make_panel

panel = make_panel(beta=-1.0, seed=42)
out = {
    "beta": round(fit_exposure(panel).beta, 12),
    "boot": [round(b, 12) for b in block_bootstrap_beta(panel, n_boot=50, seed=42)],
    "perm": {k: (round(v, 12) if isinstance(v, float) else v)
             for k, v in permutation_test(panel, n_perm=100, seed=42).items()},
}
print(hashlib.sha256(json.dumps(out, sort_keys=True).encode()).hexdigest())
PY
}

A=$(run); B=$(run)
if [ "$A" != "$B" ]; then
  echo "DETERMINISM FAILURE: $A != $B" >&2
  exit 1
fi
echo "deterministic: $A"
