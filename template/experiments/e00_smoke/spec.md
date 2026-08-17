# E00 — Smoke: does the scaffold produce a defensible number end to end?

**Status:** permanent fixture. Do not delete; do not repurpose.

## Why this experiment exists

This is not a research question. It is the scaffold's own test. A template whose
example does not execute is a lie, and it is how templates rot — you discover at
hour zero of a sprint that the thing you built in calm conditions no longer runs.

E00 exercises the whole path in under ten seconds, with no GPU, no API key and no
network: **seed → generate records → integrity-check → statistics → summary.json →
RESULTS.md → figure**. CI runs it on every push. If E00 is green, the machinery
under `src/lab/` works and a real experiment can be written against it.

It is also the worked example. Copy this directory, not `_template/`, when you
want something that already runs.

## The toy question

Two Bernoulli generators stand in for two models. `control` fires at p=0.50,
`treatment` at p=0.62. We ask whether a matched comparison recovers that
difference — and, just as importantly, whether it *declines* to find a difference
between control and itself.

## Design

| Knob | Value | Why |
|---|---|---|
| Arms | `control`, `treatment` | An arm with no control arm produces no claim. |
| Items | 8 | Varying the item shows per-item spread, not just a pooled rate. |
| Replicates | 40 per item per arm | n > 1. One draw is an anecdote. |
| Total records | 640 | 320 per arm. |
| Seed | 0 | Fixed and recorded in the manifest. |
| Per-cell seeding | `seeds.spawn(seed, index=i)` | Independent streams per cell, not `seed + i`. |

## Decisions

- **DECISION — effect size.** `treatment` p=0.62 against control p=0.50. Chosen so
  the effect is detectable at n=320 per arm but not so large that a broken test
  would still pass. A smoke test that passes with a broken statistic is worthless.
- **DECISION — a null arm is included.** The analysis also compares `control`
  against a resample of itself. If that comparison shows a "significant" effect,
  the statistics are wrong, not the data.

## What would make this fail

- Integrity check reports missing or duplicated records → the run loop is broken.
- The control-vs-control comparison comes out significant → `stats.py` is broken.
- The treatment-vs-control comparison comes out null → the seeding is collapsing
  the two arms onto the same stream.
