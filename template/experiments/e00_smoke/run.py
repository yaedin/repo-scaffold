"""E00 smoke — generate the raw records.

Pattern to copy for a real experiment:

    1. Declare a BACKEND. `stub` is the default and costs nothing; the real one is
       a flag away. Build the synthetic path first, always — analysis bugs then
       cost seconds instead of a GPU-hour.
    2. Declare parameters as module constants, so the manifest can record them.
    3. Seed once, explicitly, and pass the seed into the manifest.
    4. Stamp every record with the backend's provenance, at the point of
       measurement. This is what survives an execution path that bypasses this
       file entirely — a remote launcher, a resumed job.
    5. Write one shard per arm THROUGH A CHECKPOINT, plus the manifest. Rerunning
       this script resumes rather than restarting, so a job that dies at 70% costs
       the remaining 30%. Compute nothing.

The separation matters: `run.py` is expensive and you want to run it once,
`analyze.py` is cheap and you will run it fifty times as your thinking changes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make `lab` importable when this file is run directly as a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import numpy as np  # noqa: E402

from lab.core import backend as backends  # noqa: E402
from lab.core import manifest, seeds  # noqa: E402
from lab.core.checkpoint import Checkpoint  # noqa: E402
from lab.core.paths import RunPaths  # noqa: E402

EXPERIMENT = "e00_smoke"

# --- Parameters. Everything that could change a number lives here. ------------
ARMS = {"control": 0.50, "treatment": 0.62}
N_ITEMS = 8
N_REPLICATES = 40
SEED = 0


class CoinBackend(backends.StubBackend):
    """Two Bernoulli generators standing in for two models.

    A real backend replaces this: same `generate` signature, same stamping, a
    different `name` and `reportable = True`. Nothing downstream changes.
    """

    name = "stub"
    model_id = "bernoulli-coin"
    dtype = "float64"

    def generate(self, p_fire: float, n: int, rng: np.random.Generator) -> list[bool]:
        return [bool(x) for x in rng.random(n) < p_fire]


backends.register(CoinBackend)


def generate(backend: backends.Backend) -> dict[str, list[dict]]:
    """Records per arm. Each cell draws from its own independent stream.

    Sequential seeds (seed + i) would correlate the first draw across cells and
    quietly couple arms that must be independent.
    """
    stamp = backend.stamp()
    shards: dict[str, list[dict]] = {}

    for arm_index, (arm, p_fire) in enumerate(ARMS.items()):
        rows = []
        for item in range(N_ITEMS):
            cell_seed = seeds.spawn(SEED, index=arm_index * N_ITEMS + item)
            rng = np.random.default_rng(cell_seed)
            outcomes = backend.generate(p_fire, N_REPLICATES, rng)
            for rep, fired in enumerate(outcomes):
                rows.append(
                    {
                        "record_id": f"{arm}-i{item:02d}-r{rep:02d}",
                        "arm": arm,
                        "item_id": f"item_{item:02d}",
                        "replicate": rep,
                        "cell_seed": int(cell_seed),
                        "fired": fired,
                        # Provenance travels with the measurement, not beside it.
                        **stamp,
                    }
                )
        shards[arm] = rows
    return shards


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--backend",
        default="stub",
        choices=backends.available(),
        help="which backend produces the measurements (default: stub)",
    )
    ap.add_argument(
        "--fresh",
        action="store_true",
        help="discard existing shards and re-measure from scratch "
        "(the default is to resume, which is what you want after a crash)",
    )
    args = ap.parse_args()

    backend = backends.resolve(args.backend)
    paths = RunPaths(EXPERIMENT).ensure()
    seeds.seed_all(SEED)

    if args.fresh:
        # Discarding recorded data is deliberate and explicit, never a side effect
        # of changing a parameter and rerunning.
        for shard in paths.record_files():
            shard.unlink()
        print(f"run: --fresh, discarded {len(ARMS)} shard(s)")

    shards = generate(backend)

    total = 0
    for arm, rows in shards.items():
        # One file per arm, written through a Checkpoint. Expensive runs are rarely
        # one process; hand-merging shards is where duplicated and dropped records
        # come from, and a crash partway should cost the remainder, not the run.
        #
        # Rerunning this script is therefore idempotent: a complete shard is a
        # no-op, a partial one is topped up, and a truncated final line left by a
        # killed process is repaired on open.
        ck = Checkpoint(paths.records_for(arm))
        written = ck.extend(rows)
        print(f"run: {ck.status()} (+{written} this pass)")
        total += ck.count()

    manifest.write(
        paths.output,
        {
            "arms": ARMS,
            "n_items": N_ITEMS,
            "n_replicates": N_REPLICATES,
            "total_records": total,
            "shards": sorted(shards),
        },
        seed=SEED,
        backend=backend,
    )

    paths.log.write_text(
        f"backend={backend.name} model={backend.model_id} reportable={backend.reportable}\n"
        f"wrote {total} records across {len(shards)} shard(s)\n",
        encoding="utf-8",
    )
    print(f"run: backend={backend!r} reportable={backend.reportable}")
    print(f"run: wrote {total} records across {len(shards)} shards -> {paths.rel(paths.output)}")
    print("run: next step is `uv run python experiments/e00_smoke/analyze.py`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
