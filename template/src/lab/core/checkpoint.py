"""Resume a run that died partway through, without duplicating or dropping work.

Long jobs fail. The process is killed, the spot instance is reclaimed, the API
rate-limits, the laptop sleeps. What happens next decides whether you lose an
afternoon or a result:

  * **Rerun from scratch** — correct, and you pay twice.
  * **Rerun and append** — cheap, and now n is inflated by duplicates.
  * **Hand-merge the shards** — this is where dropped records come from.

A `Checkpoint` makes the cheap option the correct one. It reads what is already on
disk, tells you what is left, and appends only that. Rerunning a completed job is
a no-op; rerunning a job that died at 70% costs the remaining 30%.

    ck = Checkpoint(paths.records_for("treatment"))
    todo = ck.pending(planned_units)          # what still needs doing
    for batch in chunks(todo, 8):
        ck.extend(measure(batch))             # appended and flushed immediately

Three properties worth knowing about:

**Crash-tolerant.** A process killed mid-write leaves a truncated final line.
Opening a checkpoint repairs that by truncating back to the last complete record,
so a resumed run starts from valid data instead of crashing on a half-object.

**Flushed per batch.** A kill loses at most the batch in flight, not the run.

**Provenance-guarded.** Resuming with a different backend than the one that wrote
the existing records is refused. Otherwise you get a file that silently mixes a
stub run and a real one, and every rate computed over it describes a population
that never existed. This is the same rule `lab.core.provenance` enforces at
analysis time, applied earlier — at the moment the mixing would happen.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from pathlib import Path

from lab.core import records
from lab.core.backend import PROVENANCE_FIELDS
from lab.core.provenance import ProvenanceError

DEFAULT_KEY = "record_id"


def repair(path: Path | str) -> int:
    """Drop a truncated trailing line. Returns the number of bytes removed.

    A JSONL file written by a killed process is valid right up to its last
    newline. Truncating there is lossless for every complete record and removes
    the fragment that would otherwise make the whole file unreadable.
    """
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return 0

    data = path.read_bytes()
    if data.endswith(b"\n"):
        return 0

    cut = data.rfind(b"\n")
    keep = data[: cut + 1] if cut != -1 else b""
    path.write_bytes(keep)
    return len(data) - len(keep)


class Checkpoint:
    """Append-only, resumable writer for one shard of measurement records."""

    def __init__(self, path: Path | str, *, key: str = DEFAULT_KEY):
        self.path = Path(path)
        self.key = key
        self.repaired_bytes = repair(self.path)

    # --- reading what already exists ------------------------------------------

    def existing(self) -> list[dict]:
        """Records already on disk. Empty if the shard has not been started."""
        if not self.path.exists():
            return []
        return records.read(self.path)

    def done(self) -> set:
        """The key values already recorded."""
        return {r.get(self.key) for r in self.existing()}

    def count(self) -> int:
        return len(self.existing())

    def pending(self, planned: Sequence) -> list:
        """The planned work units not yet on disk, in planned order.

        `planned` may be a list of key values, or of dicts carrying the key —
        whichever your run loop naturally has.
        """
        done = self.done()

        def key_of(unit: object) -> object:
            return unit.get(self.key) if isinstance(unit, dict) else unit

        return [u for u in planned if key_of(u) not in done]

    def is_complete(self, planned: Sequence) -> bool:
        return not self.pending(planned)

    # --- writing --------------------------------------------------------------

    def _guard_provenance(self, rows: Sequence[dict]) -> None:
        """Refuse to mix a stub run and a real one in the same file."""
        existing = self.existing()
        if not existing or not rows:
            return

        for f in PROVENANCE_FIELDS:
            old = {r.get(f) for r in existing if f in r}
            new = {r.get(f) for r in rows if f in r}
            if old and new and old != new:
                raise ProvenanceError(
                    f"refusing to append to {self.path.name}: existing records have "
                    f"{f}={sorted(map(str, old))} but the incoming batch has "
                    f"{f}={sorted(map(str, new))}. Resuming with a different backend "
                    f"would silently mix two runs. Write a new shard instead."
                )

    def extend(self, rows: Iterable[dict]) -> int:
        """Append records and flush. Returns how many were written.

        Records whose key is already present are skipped, so an over-eager caller
        that recomputes a boundary batch cannot inflate n.
        """
        rows = list(rows)
        if not rows:
            return 0

        self._guard_provenance(rows)

        done = self.done()
        fresh = [r for r in rows if r.get(self.key) not in done]
        if not fresh:
            return 0

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            for row in fresh:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
        return len(fresh)

    def status(self, planned: Sequence | None = None) -> str:
        """One line for the run log, so a resumed job says what it resumed from."""
        have = self.count()
        note = f" (repaired {self.repaired_bytes}B truncated tail)" if self.repaired_bytes else ""
        if planned is None:
            return f"{self.path.name}: {have} records on disk{note}"
        todo = len(self.pending(planned))
        return (
            f"{self.path.name}: {have}/{have + todo} done, {todo} pending{note}"
            if todo
            else f"{self.path.name}: complete ({have} records){note}"
        )

    def __repr__(self) -> str:
        return f"Checkpoint({self.path.name!r}, key={self.key!r}, n={self.count()})"
