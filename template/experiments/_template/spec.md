# E<NN> — <one-line question this experiment answers>

**Status:** specified <!-- specified | running | complete | abandoned -->

## 1. Why this experiment exists

What do we currently believe, what would this change, and what decision downstream
depends on the answer? If nothing downstream changes either way, do not run it.

## 2. Hypothesis

State it so it can be wrong. "X differs from the control on metric M" is testable;
"we investigate X" is not.

- **H1:** ...
- **What would falsify H1:** ...

## 3. Unit of analysis

**One record is one ____.**

Settle this before you choose stimuli. Everything downstream depends on it: what
`record_id` identifies, what a cell is, what n counts, and whether two
measurements are independent or paired. Getting it wrong is not a bug you find
later — it silently changes what every statistic means.

- Unit: ...
- Independent across: ...
- Paired within: ... (use `paired_bootstrap_ci`, not two independent samples)

## 4. Design

| Knob | Value | Why |
|---|---|---|
| Backend | `stub` first, then ... | Build the synthetic path before the real one. |
| Arms | `treatment`, `control` | No control arm, no claim. |
| Control | | What is held fixed? |
| Items | | |
| Replicates | | n > 1. Size for a tolerable interval width. |
| Total records | | |
| Seed | 0 | Fixed and recorded in the manifest. |
| Primary metric | | |
| Statistic | | e.g. two-proportion z-test on fire rate, Wilson 95% CI |

**Exactly one factor varies between arms.** Name it: ...

## 5. Decisions

Record the knobs you chose and why, so a later reader does not have to guess
whether a value was reasoned or arbitrary.

- **DECISION — backend.** The stub returns <shape>; the real backend is <what>
  and is `reportable = True`. Numbers below the stub line are leads only.
- **DECISION — <knob>.** Chose <value> because ...
- **DECISION — sample size.** n = <N> gives a Wilson interval of roughly ±<W>pp at
  p≈0.5, which is narrow enough to separate the arms if the effect is ≥ <E>pp.

## 6. Null comparison

Which comparison in this design *should* come out non-significant? If none does,
add one. Without it, a positive result cannot be distinguished from a broken
statistic.

## 7. Cost

Estimated: <calls> × <unit cost> = <total>. Confirm before running anything metered.

## 8. What would make this fail

- ...
