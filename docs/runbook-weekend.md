# Weekend runbook

A 48-hour research sprint, solo. The point of the scaffold is that almost nothing
in the first hour is thinking work — it is copying and filling in — so the thinking
starts early and the shipping is not improvised at 3am.

Times are from the start of the sprint.

## Before the clock starts (do this the week before)

- [ ] `just verify` passes on a fresh copy of the template. **Do not skip this.**
      An untested scaffold at hour zero is worse than no scaffold.
- [ ] Read the sprint brief and put it in `docs/` — the judging criteria are the
      spec, and last time having them in-repo demonstrably shaped better decisions.
- [ ] Skim whatever reference papers you already know matter. Distil to notes; do
      not commit third-party PDFs (redistribution, and a full-text extraction is as
      much a redistribution as the PDF).

## Hour 0–1: setup, not science

```bash
cp -r repo-scaffold/template my-project
rm -rf my-project/.git   # the template is versioned; do not inherit its history
cd my-project
uv sync
just init                # fills name, title, author, description
just verify              # confirm green before you touch anything
git init && git add -A && git commit -m "Scaffold"
```

That commit contains a working licence, citation file, CI, and a passing
end-to-end experiment. Functions 2, 5, 6 are done in hour one and never revisited.

- [ ] Decide the experiment numbering (`e01`, `e02`, …) and **never reuse a
      number.** Two numbering schemes that never got reconciled cost real reader
      time last time.
- [ ] Write `docs/journal/<today>.md` and keep it open all weekend.

## Hour 1–4: one question, specified before code

- [ ] `cp -r experiments/_template experiments/e01_<slug>`
- [ ] **Settle the unit of analysis first, stimuli second.** One record is one
      *what*? Everything downstream depends on it — what n counts, what a cell is,
      whether two measurements are independent or paired. Choosing stimuli before
      the unit means rebuilding the battery when the unit changes.
- [ ] Fill in `spec.md` **completely** before writing any code — hypothesis, arms,
      what falsifies it, sample size and why, and the null comparison.
- [ ] Cost estimate in the spec if anything is metered. Show the arithmetic.
- [ ] **Get the stub backend working end to end before the real one.** The full
      pipeline should run in seconds against synthetic data. Every analysis bug
      you find here is one you do not find after paying for a GPU.

The spec is not bureaucracy. The single most expensive failure mode in a sprint is
running a large batch that answers a question you did not actually mean to ask.

## Hour 4–20: run, analyse, commit

The loop, once per experiment:

1. `run.py` produces records, through a `Checkpoint` so a crash costs the
   remainder rather than the run. Compute nothing here.
2. `analyze.py` integrity-checks — including provenance against the manifest —
   computes with intervals, and generates `RESULTS.md`.
3. `just verify`.
4. Add a row to `CLAIMS.md`, with a JSON pointer so the number is checked and not
   merely accompanied.
5. Commit with a message that states the *finding*, not the activity:
   `E01: no single-token trigger exists — hypothesis class closed`.

- [ ] **Every experiment gets a `RESULTS.md`, including the negative ones.** A null
      with a stated sensitivity is a finding. A deleted experiment is a hole in the
      record and you will not remember why it went.
- [ ] If a result overturns an earlier one, add the retraction to `CLAIMS.md` and
      the journal. Do not edit history. The record of a changed mind is worth more
      to a careful reader than the original finding was.

## Hour 20–36: the second question, or the control you are missing

Usually the highest-value experiment at this point is **not** the next new idea.
It is one of:

- The **confound-killer**: does your headline effect survive holding fixed the
  thing you did not vary? (Last time this retracted the headline finding — which
  was the right outcome, and it was the strongest thing in the paper.)
- The **positive control**: does your method detect an effect you *know* is there?
  Without it, every null you report is unbounded — a clean subject, an insensitive
  method and an unlucky stimulus set all produce the same sentence.

## Hour 36–44: write

- [ ] `writeup/paper.md`. Abstract last. One to three specific, falsifiable claims.
- [ ] Every number in the paper has a row in `CLAIMS.md`. `just check` enforces it.
- [ ] `just figures` — committed figures, so a reader who will not clone still sees
      the result.
- [ ] `just wordcount` — per-section counts, for the reduction passes. Informational.
- [ ] Limitations section written before anyone asks. Name the strongest argument
      against your own result.

## Hour 44–48: ship

- [ ] `just verify-full` — `verify` plus `figures` and `paper`. Needs
      `uv sync --group paper` once; produces `writeup/paper.pdf`.
- [ ] `just publish-check` — licence, citation, placeholders, figures, paper source,
      unresolved claims, repo size. Fix whatever it names; each item is minutes.
- [ ] README: the claim in the first paragraph, the results table, the figure, and
      a **Known gaps** section. Being explicit about holes buys more credibility
      than it costs — a reader who finds a hole you did not flag stops trusting the
      ones you did.
- [ ] Push. Link the repo from the submission.

## The failure modes this is designed against

Each of these actually happened, and each is now mechanically prevented:

| Failure | Prevention |
|---|---|
| Numbers in the paper with no source in the repo | `CLAIMS.md` + `just check` |
| A generated table drops a row and nobody notices | Render tables off the data the analysis iterates, never hardcoded rows |
| Gigabytes of raw tensors land in git history | `.gitignore` denies by content under `output/`; `just check` fails on a blob over 5 MB |
| Reports crash on Windows on the first `Δ` they print | UTF-8 at every call site, `lab/__init__` stdout reconfig, three-OS CI |
| Repo map gone stale, agent acts on it confidently | Durable `AGENTS.md`, volatile `docs/journal/`, path linting |
| No licence, so nobody can build on it | `LICENSE` in the first commit; `publish-check` |
| Paper is a PDF with no source | `writeup/paper.md` committed, PDF gitignored |
| No figures, so a non-cloning reader sees nothing | `just figures`, `publish-check` |
| Two numbering schemes never reconciled | Decide at hour 0, never reuse a number |
| Silently dropped records inflate an effect | `check_records(expected_per_cell=...)` |
| Hand-transcribed model output contains fabrications | Generate evidence excerpts by script, never by hand |
| A stale manifest mislabels real output as synthetic | Provenance stamped per record; `check_records(manifest=...)` hard-fails on disagreement |
| The ledger still quotes a number the rerun moved | JSON pointers in `CLAIMS.md`, checked by `just check` |
| A job dies at 70% and the rerun duplicates or drops work | `Checkpoint` — rerun the same command, pay only the remainder |
| A crashed run leaves half a record and breaks the resume | `Checkpoint` repairs the truncated tail on open |
| A failed remote job reports success | Never pipe a long-running command through `grep`/`tail`; the pipeline returns the last command's status |
| Rounds spent asking about decisions the agent should own | The decision-rights section in `AGENTS.md` |
