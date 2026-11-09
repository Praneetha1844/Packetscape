# ADR 0002: One seed, an independent random stream per component

- Status: accepted
- Date: 2026-11-09

## Context

Comparisons between policies are only meaningful if two runs differ in the policy and nothing else. A single shared random stream breaks this: adding a flow or changing a queue changes how many numbers every other component consumes, so unrelated parts of the scenario see different randomness.

## Decision

The scenario has one integer `seed`. Each stochastic component (each link direction, each queue, each Poisson source) owns a `random.Random` created by `child_rng(seed, name)`, with names such as `link/r1->r2`, `queue/r1->r2` and `source/f2`.

`random.Random` accepts a string seed and derives its state from it deterministically (it does not use Python's per-process string hash), so results do not depend on `PYTHONHASHSEED`.

## Consequences

- Same scenario file and seed give the same results on every run and platform with the same Python version and floating-point behaviour. A test checks that two runs agree.
- Changing the congestion controller of one flow does not alter the loss pattern of a link, which makes before/after comparisons cleaner.
- Stream names are part of the reproducibility contract: renaming a component changes its stream, so a rename is a behaviour change and belongs in the changelog.
- The standard-library generator is not suitable for statistical guarantees across very long runs; it is adequate for the intended scale.
