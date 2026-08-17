# The seven functions a research repo has to fulfil

This is the model the template is built from. It exists so that future-you knows
*why* each file is there and can tell the difference between deleting something
unnecessary and deleting something load-bearing.

A research repo is not a codebase that happens to contain science. It is **an
argument, plus the machinery that produced it**. Seven functions, each defined by
the question it answers. They are MECE as *functions*; individual files often
serve two, and those couplings are named below rather than pretended away.

| # | Function | The question it answers | Fails when |
|---|---|---|---|
| 1 | Claim ledger | What do we assert, and which artifact backs each assertion? | A number in the paper has no traceable source |
| 2 | Re-execution | Can a stranger regenerate any artifact from source? | Clone → figure is impossible without you in the room |
| 3 | Orientation | Does a reader — human *or* agent — know where to go, in what order? | A newcomer reads files in arbitrary order and forms a wrong model |
| 4 | Provenance & integrity | What produced this artifact, when, under what conditions — and what did we get wrong? | Numbers float free of the run that made them; errors are silently edited away |
| 5 | Reuse surface | What can someone lift out and use elsewhere? | Everything is a 400-line script; nothing is extractable |
| 6 | Governance | What may I legally do with this, who gets credit, what is unsafe to release? | No licence → legally unusable by anyone |
| 7 | Dissemination | How does anyone discover this exists, and cite it? | Excellent work, zero readers |

**1–4 are the scientific spine** — they are what make it research rather than a
demo. **5 is engineering leverage.** **6–7 are what convert private work into
public standing.**

Hackathon repos routinely nail 2 and 5 and fail 1, 4, 6 and 7, which is exactly
backwards if the repo is also a portfolio artifact.

## Where each function lives in the template

| Function | Implemented by |
|---|---|
| 1 Claim ledger | `CLAIMS.md` (with JSON pointers), the results table in `README.md`, `src/lab/check.py` |
| 2 Re-execution | `pyproject.toml` + `uv.lock`, `justfile`, `.github/workflows/ci.yml`, `experiments/e00_smoke/` |
| 3 Orientation | `AGENTS.md`, `CLAUDE.md`, `README.md`, `experiments/_template/`, the `check` linter |
| 4 Provenance | `src/lab/core/backend.py`, `src/lab/core/provenance.py`, `src/lab/core/manifest.py`, `src/lab/core/seeds.py`, `src/lab/analysis/integrity.py`, `docs/journal/` |
| 5 Reuse | `src/lab/` as a package, separated from `experiments/` |
| 6 Governance | `LICENSE`, `CITATION.cff`, `.gitignore`, `src/lab/size.py`, `scripts/publish_check.py` |
| 7 Dissemination | `figures/` committed, `writeup/` source committed, `scripts/build_paper.py`, `src/lab/figstyle.py`, `docs/index.md`, `scripts/publish_check.py` |

## The four mechanisms that do the real work

Everything else is a file you could have written by hand. These four are the
reason the discipline survives contact with a deadline.

### The smoke experiment actually runs

`experiments/e00_smoke/` is a real end-to-end experiment — seed, records,
integrity check, statistics, `summary.json`, generated `RESULTS.md`, committed
figure — in under ten seconds with no GPU, no API key and no network. CI runs it
on every push, on Linux, macOS and Windows.

**Templates rot because their examples do not execute.** You find out at hour zero
of a sprint that the thing you built in calm conditions no longer works. A smoke
experiment that is genuinely cheap is the only version of this that stays green.

The same reasoning generalises into a method rule: every experiment declares a
backend, and `stub` is the default. Building the synthetic path first stops being
advice you have to remember and becomes the path of least resistance — analysis
bugs surface in seconds rather than after a GPU bill.

### The claim ledger is linted, not curated

`CLAIMS.md` binds every claim to a producing script and an output artifact.
`just check` fails if any cited path does not exist, if a claim row cites nothing
at all, or — via a JSON pointer in the artifact cell — if the quoted number no
longer matches what the artifact contains.

The last of those was added after the first real use. Existence checking alone is
necessary and not sufficient: you rerun an experiment, the effect moves from
+14.4pp to +9.1pp, and the ledger still says +14.4pp because every path still
resolves. The linter stays green while the ledger lies, which is precisely the
failure the ledger was invented to prevent.

A curated document decays; a linted one cannot.

### Provenance is derived, never asserted

Every record carries the backend, model and dtype that produced it, stamped at the
point of measurement. `check_records(manifest=...)` derives origin from the data
and refuses to proceed if the manifest disagrees.

This too came from a real failure. The manifest was written by `run.py`, but a
remote launcher bypassed `run.py` — so a stale manifest labelled real 7B output as
synthetic. Nothing crashed, and every number computed afterwards inherited the
mislabelling. The lesson generalises:

> **Provenance asserted by the writer is a comment. Provenance derived from the
> artifact is a fact.**

A manifest that agrees with its records is a useful summary. A manifest that
disagrees is a bug that has already happened, and the only safe response is to
refuse to compute.

### Volatile state is quarantined

`AGENTS.md` holds only durable rules — no dates, no status, no "in flight". Every
timestamped thing goes in `docs/journal/`. And `just check` verifies that every
path named in `AGENTS.md` still exists.

A stale map is worse than no map, because an agent will act on it confidently. The
observed failure mode is a repo map written excellently on day one that references
three files which have moved by day fourteen, still being read as authoritative.

## What this model deliberately does not do

- **No modes or profiles.** One template. Functions 1–5 are always on; 6–7 are
  files that sit inert until you are shipping. A private project simply never runs
  `just publish-check`.
- **No provider integrations.** `backend.py` defines a protocol and a stub; it ships
  no client for Modal, Kaggle, SLURM or anything else. Those disagree about
  everything, and a wrong abstraction there is how a template rots. Job launching
  belongs in the project.
- **No domain machinery.** `src/lab/analysis` carries proportion statistics and
  data-integrity checks — the minimum needed to verify that measured data is what
  you think it is — and nothing about LLMs, models or evals. That belongs in the
  project.
- **No renaming.** The package is permanently `lab`. Renaming per project churns
  every import path and every code example, and resets muscle memory, in exchange
  for nothing.

## Sources

The model is a synthesis, but the individual pieces are not original:

- Neel Nanda, [Highly Opinionated Advice on How to Write ML Papers](https://www.alignmentforum.org/posts/eJGptPbbFPZGLpjsp/highly-opinionated-advice-on-how-to-write-ml-papers) — claims-first structure, limitations as a credibility signal
- Papers with Code, [Releasing Research Code](https://github.com/paperswithcode/releasing-research-code) — the ML Code Completeness Checklist; a README results table with the exact commands is the item that most predicts adoption
- Semmelrock et al., [Reproducibility in ML-based research](https://onlinelibrary.wiley.com/doi/10.1002/aaai.70002) — the artifact set: code, data, environment, seeds, hyperparameters, logs
- [AGENTS.md](https://www.morphllm.com/agents-md-guide) — open spec since Aug 2025, donated to the Linux Foundation's Agentic AI Foundation Dec 2025, read by 30+ tools
- [Context Engineering for AI Agents in OSS](https://arxiv.org/html/2510.21413v1) (MSR '26) — agent context must persist in the repo, not in chat history
- [thought-anchors](https://github.com/interp-reasoning/thought-anchors) / [thought-anchors.com](https://www.thought-anchors.com/) — the constellation pattern: paper + repo + hosted interface + HF dataset
