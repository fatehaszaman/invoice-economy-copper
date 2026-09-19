"""Run the full estimation and inference sequence.

Until live ingestion lands, this runs against the SYNTHETIC panel and says so
on every line of output. Its purpose today is to demonstrate that the
estimator recovers a known effect and declines to invent one — not to report
a finding about copper.
"""
from __future__ import annotations

import sys

from research.bootstrap import block_bootstrap_beta, percentile_ci
from research.exposure import fit_by_tier, fit_exposure
from research.monotonicity import check_monotonicity
from research.permutation import permutation_test
from research.pretrends import check_pretrends
from tests.synthetic.make_panel import make_panel

BANNER = "[SYNTHETIC DATA — validation only, not an empirical result]"


def run(beta: float, label: str) -> bool:
    print(f"\n{BANNER}")
    print(f"--- {label}: planted beta = {beta:+.2f} ---")
    panel = make_panel(beta=beta, seed=42)

    fit = fit_exposure(panel)
    print(f"estimated beta      : {fit.beta:+.4f}   (n={fit.n_obs}, channels={fit.n_channels})")
    print(f"cluster SE (2nd'ry) : {fit.se_cluster:.4f}")

    pre = check_pretrends(panel)
    print(f"pre-trend           : {'PASS' if pre.passes else 'FAIL — design invalid'} "
          f"(slope={pre.slope:+.5f}, p={pre.p_value:.3f})")
    if not pre.passes:
        print("  kill condition triggered; estimation would stop here on real data")

    mono = check_monotonicity(fit_by_tier(panel))
    print(f"monotonicity        : ordered={mono.ordered_as_predicted} "
          f"rho={mono.spearman_rho:+.3f} p={mono.spearman_p:.3f}")
    for tier, eff in mono.effects.items():
        print(f"    {tier:<9} {eff:+.4f}")

    lo, hi = percentile_ci(block_bootstrap_beta(panel, n_boot=200, seed=42))
    print(f"block bootstrap 90% : [{lo:+.4f}, {hi:+.4f}]")

    perm = permutation_test(panel, n_perm=400, seed=42)
    print(f"permutation         : p={perm['p_value']:.4f} "
          f"({perm['n_permutations']} label reassignments)")
    return True


if __name__ == "__main__":
    run(-1.0, "recovery check")
    run(0.0, "null check — must NOT find an effect")
    print(f"\n{BANNER}")
    print("No copper finding is reported. FINDINGS.md is written only after live "
          "ingestion completes.")
    sys.exit(0)
