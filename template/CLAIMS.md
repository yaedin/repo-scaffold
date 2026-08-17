# Claim ledger

Every number that appears in the writeup gets a row here, bound to the code that
produced it and the artifact it came out of. `just check` verifies that every
cited path exists and that no claim row is left without a source.

**The rule: if a number cannot get a row, it cannot go in the paper.**

This is cheap to maintain live and expensive to reconstruct afterwards. Add the
row when you get the number, not the night before the deadline — that is the
night you discover a figure whose producing script no longer exists.

## Status vocabulary

| Status | Meaning |
|---|---|
| `POSITIVE` | The effect is present and the interval excludes the null. |
| `NULL` | No effect detected. **This is a result.** State the sensitivity you had. |
| `RETRACTED` | Withdrawn. Keep the row, add why. Never delete it. |
| `OPEN` | Measured, not yet interpreted. |

## Claims

The **Artifact** cell may carry a JSON pointer — `path/to/summary.json#dotted.key`. <!-- check:ignore -->
When it does, `just check` resolves it and asserts the resolved value is quoted in
the **Number** cell. That is what stops a claim drifting from its artifact: rerun
an experiment, the effect moves, and the build goes red until the ledger is
updated. Existence checks alone would stay green while the ledger lied.

Cite one pointer per number you quote. Rows without a pointer are still allowed —
not every claim is a scalar — but they are only checked for path existence.

| ID | Claim | Number | Status | Produced by | Artifact |
|---|---|---|---|---|---|
| C00 | The scaffold produces a defensible number end to end. | Δ = +14.4pp | POSITIVE | `experiments/e00_smoke/analyze.py` | `experiments/e00_smoke/output/summary.json#comparisons.treatment_vs_control.delta` |
| C01 | It declines to find an effect where none exists. | Δ = 0.0pp | NULL | `experiments/e00_smoke/analyze.py` | `experiments/e00_smoke/output/summary.json#comparisons.null_control.delta` |

<!-- Add rows above. Copy this template:
| C02 | One sentence, falsifiable. | the number with its interval | POSITIVE/NULL | `experiments/eNN_slug/analyze.py` | `experiments/eNN_slug/output/summary.json#comparisons.main.delta` |
-->

## Retractions

Nothing retracted yet. When something is, it moves here **and keeps its row above**
with status `RETRACTED`, so the record shows what was believed and what changed it.

| ID | What was claimed | What killed it | Date |
|---|---|---|---|
| — | — | — | — |

## Known gaps

Claims you would like to make and cannot, or numbers quoted from elsewhere that
have no source in this repo. Being explicit here is worth more than it costs: a
reader who finds an unsourced number you did not flag stops trusting the ones you
did.

- _None yet._
