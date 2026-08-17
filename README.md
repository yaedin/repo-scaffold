# repo-scaffold

A starting point for empirical research repos, e.g. hackathon sprints, small
independent experiments, private projects.

## Use it

```bash
cp -r repo-scaffold/template my-project
rm -rf my-project/.git   # the template is versioned; your project starts fresh
cd my-project
uv sync          # installs dependencies AND the `just` task runner itself
just init        # fills in name, title, author, description
just verify      # lint + tests + doc checks + a real end-to-end experiment
git init         # `just check` guards blob size from your first commit on
```

`uv` is the only thing assumed to be on the machine. `just` arrives as a locked
dependency, so the repo behaves identically on macOS, Linux and Windows. CI runs
all three on every push.

The Python package inside is permanently named `lab` and is **not** renamed per
project: `from lab.core import ...` means the same thing in every repo you start
this way, so imports never churn and code examples never go stale.

## What you get

| Command | What it does |
|---|---|
| `just smoke` | A real experiment, end to end, in under ten seconds. No GPU, no API key, no network. |
| `just test` | Unit tests for the statistics and integrity machinery |
| `just check` | Every path cited in `CLAIMS.md` and `AGENTS.md` must exist; no oversized blob is staged |
| `just figures` | Regenerate every committed figure from source data |
| `just paper` | Render the Markdown writeup to PDF via Typst. No LaTeX. |
| `just verify` | lint + test + smoke + check |
| `just verify-full` | `verify`, plus `figures` and `paper`. What CI runs. |
| `just wordcount` | Per-section prose counts. Informational; never gates anything. |
| `just publish-check` | Licence, citation, placeholders, figures, paper source, unresolved claims, repo size |

And the files: `AGENTS.md` (durable agent instructions), `CLAIMS.md` (the linted
claim ledger), `LICENSE`, `CITATION.cff`, CI across three platforms, an experiment
template, and `src/lab/`: paths, seeds, manifests, JSONL, proportion statistics,
data-integrity checks, a repository size guard, and a house figure style.

## The idea

A research repo is **an argument plus the machinery that produced it**, and it has
seven jobs. Full model in [docs/seven-functions.md](docs/seven-functions.md).

| # | Function | Fails when |
|---|---|---|
| 1 | Claim ledger | A number in the paper has no traceable source |
| 2 | Re-execution | Clone → figure is impossible without you in the room |
| 3 | Orientation | A newcomer forms a wrong model of the repo |
| 4 | Provenance & integrity | Numbers float free of the run that made them |
| 5 | Reuse surface | Nothing is extractable |
| 6 | Governance | No licence → legally unusable by anyone |
| 7 | Dissemination | Excellent work, zero readers |

Functions 1–5 are always on. **6 and 7 are files that sit inert until you are
shipping** — a private project simply never runs `publish-check`. That is
deliberate: one template, not two.

Note: `AGENTS.md` holds only durable rules; anything with a date lives in `docs/journal/`.
A stale map is worse than no map, because an agent acts on it confidently.

## Also here

- [docs/runbook-weekend.md](docs/runbook-weekend.md) — hour-by-hour timeline for a
  48-hour sprint, and the table of failure modes each mechanism prevents
- [docs/publish-checklist.md](docs/publish-checklist.md) — the reasoning behind
  `publish-check`, plus what is worth doing beyond it and what is not
