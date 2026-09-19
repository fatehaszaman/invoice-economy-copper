# Mistakes and discarded designs

Kept in version control deliberately. A repository with no record of its wrong
turns is either trivial or incompletely reported.

---

## 1. Scrap versus cathode as treatment and control — DISCARDED

**The appealing version.** Invoice enforcement raised scrap invoice costs from
roughly 7% to 10% in the first half of 2026, and capped individual sellers at
CNY 5m per year. Scrap is the treated group, cathode the control, and the
difference is the effect. Clean, and it maps onto the reported facts.

**Why it is wrong.** Cathode is not a control. It is an *outcome* of the
treatment. The documented response to scrap friction was substitution toward
cathode — refined imports reached a nine-month high in June. So the "control"
absorbs the treatment effect with the opposite sign, and the estimated
difference is inflated by an unknown amount that cannot be signed from the data.

This is the standard bad-control problem, and it is easy to miss because the
grouping looks physical and objective rather than behavioural.

**What replaced it.** Treatment is *pre-existing invoice exposure intensity*
per channel, continuous on [0,1]. Substitution then moves observations along
the exposure dimension rather than contaminating a comparison group. Because
enforcement was national and no channel is untreated, the design is
dose-response and the primary reported result is the *monotonicity* of the
effect across exposure, not a magnitude.

**Cost of the error.** The rejected design was the original plan. Discovering
the problem required rewriting the identification strategy, the config schema,
and the estimator before any data was fetched.

---

## 2. Market premiums inside the PCS — CORRECTED

**The original draft** placed the Yangshan premium, the Shanghai spot premium,
and the SHFE–LME arbitrage state inside the commercial block of the score.

**Why it is wrong.** The project's headline claim is that PCS anticipates
physical tightness, and physical tightness is observed *through* premiums. A
premium that is an input to the predictor cannot then be the thing predicted.
Worse, a premium can rise from genuine scarcity with no invoice mechanism at
all, so including it imports exactly the confound the design is meant to
separate.

**The fix.** Premiums, arb, and spreads form a third block, `M_t`, held
entirely outside the score and tested as a *consequence*:

```
M_{t+h} = alpha + beta_1 * Headline_t + beta_2 * PCS_t + eps
```

The question then has an answer that can come back negative: does PCS carry
information about later market confirmation beyond what the headline enforcement
date already told everyone? If beta_2 is indistinguishable from zero, the
indicator adds nothing and that gets reported.

---

## 3. Imputing missing values to keep the panel rectangular — REJECTED

Filling gaps with zeros after standardisation is conventional and silently
pulls every affected score toward the mean, which biases a difference-of-means
indicator toward "no disagreement" — the null this project is testing.

Blocks are averaged over *available* series with the denominator set to the
*expected* count. Missing series lower coverage rather than moving the score.
Below 0.60 coverage a value is labelled `low_confidence`; at zero it is
`unavailable` and carries no number at all. `tests/unit/test_pcs.py` locks
this in: a period with every series missing must be NaN, never 0.0.

---

## 4. Reconciling disagreeing sources in the pipeline — REJECTED

Good data-engineering instinct, wrong project. Customs, NBS, and exchange
figures disagree, and the ordinary response is a reconciliation layer that
makes them agree. That layer would delete the measurement.

Disagreement is flagged with both original values preserved and never
auto-corrected. Where a unit, calendar, or VAT-treatment difference makes a
comparison invalid, the comparison is *refused* rather than computed on an
adjusted basis.

---

## 5. Monte Carlo for causal inference — CORRECTED

An earlier specification proposed a Monte Carlo distribution for the treatment
effect. Monte Carlo samples an assumed generating process; it cannot establish
a causal magnitude from observational data, and the resulting interval would
describe the assumptions rather than the evidence.

Inference is now block bootstrap plus permutation of exposure labels.
Monte Carlo survives in exactly one role: propagating *measurement* uncertainty
through constructed physical quantities, where the assumed distribution is the
declared object of interest.

---

## 6. Overclaiming in project framing — CORRECTED

An early draft asserted that no other candidate plausibly combined this set of
skills. Unfalsifiable, unverifiable, and it invites the reader to look for a
counterexample instead of reading the method. Deleted.

A related claim about the size of a previous engineering team was removed for
the same reason: it could not be substantiated, so it does not appear.
