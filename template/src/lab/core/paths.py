"""Canonical on-disk layout for an experiment run.

One place decides where things go, so every experiment in the repo is navigable
without reading its code. The layout is deliberately boring:

    experiments/<name>/
        spec.md            what we are testing and why (hand-written, before the run)
        run.py             produces raw records
        analyze.py         raw records -> summary + report (never hand-authored numbers)
        RESULTS.md         the human report; source of truth for this experiment
        output/
            records.jsonl  raw, one JSON object per measurement  [GITIGNORED]
            summary.json   derived, small, committed
            manifest.json  provenance for the run, committed
            run.log        stdout/stderr of the run, committed if small

`records.jsonl` is gitignored on purpose: it is regenerable from `run.py` plus the
manifest, it can be large, and in eval work it can contain material you should not
redistribute. Everything a reader needs to check your arithmetic lives in
`summary.json` and `RESULTS.md`.
"""

from __future__ import annotations

from pathlib import Path

# Repo root = three parents up from src/lab/core/paths.py
REPO_ROOT = Path(__file__).resolve().parents[3]

EXPERIMENTS_DIR = REPO_ROOT / "experiments"
FIGURES_DIR = REPO_ROOT / "figures"


class RunPaths:
    """Resolved paths for one experiment's output directory.

    >>> p = RunPaths("e00_smoke")
    >>> p.records.name
    'records.jsonl'
    """

    def __init__(self, experiment: str, variant: str | None = None):
        self.experiment = experiment
        self.variant = variant
        self.dir = EXPERIMENTS_DIR / experiment
        # A variant gets a sibling output dir rather than overwriting the primary
        # one: output_bf16/ next to output/, never on top of it.
        self.output = self.dir / (f"output_{variant}" if variant else "output")

    @property
    def records(self) -> Path:
        """The single-shard record file, for experiments that produce one."""
        return self.output / "records.jsonl"

    def records_for(self, shard: str) -> Path:
        """One record file per shard — usually per arm, or per remote job.

        Expensive runs are rarely one process. You launch a job per arm, or resume
        a job that died at 70%, and each writes its own file. Forcing everything
        into one `records.jsonl` means either serialising work that could run in
        parallel or merging files by hand, and hand-merging is where duplicated
        and dropped records come from.

        Every shard is stamped with its own provenance, so `read_all()` can verify
        the set is homogeneous rather than assuming it.
        """
        return self.output / f"records_{shard}.jsonl"

    def record_files(self) -> list[Path]:
        """Every record file in this run, sharded or not, in stable order."""
        if not self.output.exists():
            return []
        return sorted(self.output.glob("records*.jsonl"))

    @property
    def summary(self) -> Path:
        return self.output / "summary.json"

    @property
    def manifest(self) -> Path:
        return self.output / "manifest.json"

    @property
    def log(self) -> Path:
        return self.output / "run.log"

    @property
    def results_md(self) -> Path:
        return self.dir / "RESULTS.md"

    @property
    def spec_md(self) -> Path:
        return self.dir / "spec.md"

    def figure(self, name: str) -> Path:
        """Figures live in one top-level dir so the README can embed them."""
        FIGURES_DIR.mkdir(parents=True, exist_ok=True)
        return FIGURES_DIR / f"{self.experiment}_{name}.png"

    def ensure(self) -> RunPaths:
        self.output.mkdir(parents=True, exist_ok=True)
        return self

    def rel(self, path: Path) -> str:
        """Repo-relative string, for citing artifacts inside reports."""
        return str(Path(path).resolve().relative_to(REPO_ROOT))

    def __repr__(self) -> str:
        return f"RunPaths(experiment={self.experiment!r}, output={self.rel(self.output)!r})"
