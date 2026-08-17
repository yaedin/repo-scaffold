"""JSONL read/write for measurement records.

One JSON object per line, one line per measurement. Append-friendly, streamable,
diffable, and readable by every tool you will ever want to use. Resist the urge to
reach for a dataframe at write time: raw records should record what happened, not
what you plan to compute.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path


def write(path: Path | str, rows: Iterable[dict], *, append: bool = False) -> int:
    """Write rows as JSONL. Returns the number written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "a" if append else "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    return n


def read(path: Path | str) -> list[dict]:
    """Read a whole JSONL file into memory."""
    return list(stream(path))


def stream(path: Path | str) -> Iterator[dict]:
    """Yield records one at a time, for files too large to hold in memory.

    A malformed line raises with its line number rather than failing anonymously
    three functions later.
    """
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: malformed JSON record: {exc}") from exc


def read_all(paths: Iterable[Path | str], *, add_source: bool = False) -> list[dict]:
    """Read and concatenate several shard files.

    Order follows the order of `paths`, so pass a sorted list if you want
    determinism. `add_source=True` tags each record with `_source_file`, which is
    worth turning on when a shard is suspect and you need to find which one.
    """
    out: list[dict] = []
    for path in paths:
        path = Path(path)
        for row in stream(path):
            if add_source:
                row["_source_file"] = path.name
            out.append(row)
    return out


def write_json(path: Path | str, obj: object) -> Path:
    """Write a small derived artifact (summary.json) with stable formatting."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def read_json(path: Path | str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
