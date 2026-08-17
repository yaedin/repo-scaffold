"""E<NN> — generate raw records.

Rules this file follows (see AGENTS.md):
  * Declare a BACKEND. `stub` is the default; build the synthetic path first.
  * Parameters are module constants, so the manifest can record them.
  * Seed once, explicitly, and pass the seed to the manifest.
  * One record per measurement, with every field you might later group by, and
    the backend's provenance stamp merged in at the point of measurement.
  * Write one shard per arm, through a Checkpoint, so a job that dies partway
    resumes by rerunning the same command instead of starting over.
  * Compute nothing — analysis belongs in analyze.py.

Copy experiments/e00_smoke/run.py for a version that actually runs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from lab.core import backend as backends  # noqa: E402
from lab.core import manifest, seeds  # noqa: E402
from lab.core.checkpoint import Checkpoint  # noqa: E402
from lab.core.paths import RunPaths  # noqa: E402

EXPERIMENT = "eNN_slug"  # TODO: must match this directory's name

ARMS = ["control", "treatment"]  # TODO
N_ITEMS = 0  # TODO
N_REPLICATES = 0  # TODO
SEED = 0

PARAMS = {
    "arms": ARMS,
    "n_items": N_ITEMS,
    "n_replicates": N_REPLICATES,
}


class MyBackend(backends.StubBackend):
    """TODO: rename, and add a real sibling when the stub path is proven.

    A real backend subclasses `backends.Backend`, sets `reportable = True`, and
    keeps the same `generate` signature — so switching is a flag, not an edit.
    """

    name = "stub"
    model_id = "TODO"
    dtype = "none"

    def generate(self, *args, **kwargs):
        raise NotImplementedError


backends.register(MyBackend)


def generate(backend: backends.Backend) -> dict[str, list[dict]]:
    """Records per arm. Each cell draws from its own independent stream."""
    stamp = backend.stamp()
    shards: dict[str, list[dict]] = {}
    for arm_index, arm in enumerate(ARMS):
        rows: list[dict] = []
        for item in range(N_ITEMS):
            cell_seed = seeds.spawn(SEED, index=arm_index * N_ITEMS + item)
            for rep in range(N_REPLICATES):
                rows.append(
                    {
                        "record_id": f"{arm}-i{item:02d}-r{rep:02d}",
                        "arm": arm,
                        "item_id": f"item_{item:02d}",
                        "replicate": rep,
                        "cell_seed": int(cell_seed),
                        # TODO: the measurement itself
                        **stamp,  # provenance travels WITH the measurement
                    }
                )
        shards[arm] = rows
    return shards


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--backend", default="stub", choices=backends.available())
    args = ap.parse_args()

    backend = backends.resolve(args.backend)
    paths = RunPaths(EXPERIMENT).ensure()
    seeds.seed_all(SEED)

    total = 0
    for arm, rows in generate(backend).items():
        # Resumable by construction: rerunning after a crash appends only what is
        # missing, and rerunning a finished arm is a no-op.
        ck = Checkpoint(paths.records_for(arm))
        written = ck.extend(rows)
        print(f"run: {ck.status()} (+{written} this pass)")
        total += ck.count()

    manifest.write(paths.output, PARAMS, seed=SEED, backend=backend)

    print(f"run: backend={backend!r} reportable={backend.reportable}")
    print(f"run: wrote {total} records -> {paths.rel(paths.output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
