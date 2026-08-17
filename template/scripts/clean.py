"""Remove generated output. Cross-platform, and deliberately conservative.

Deletes: raw records, run logs, caches, rendered PDFs.
Keeps:   summary.json, manifest.json, RESULTS.md, figures/ — that is the evidence.

If you want a truly clean slate, `git clean -xdf` is the tool; this is the safe
everyday version that will not eat your committed results.
"""

from __future__ import annotations

import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

FILE_PATTERNS = [
    "experiments/**/output*/records.jsonl",
    "experiments/**/output*/run.log",
    "writeup/*.pdf",
]
DIR_NAMES = {"__pycache__", ".pytest_cache", ".ruff_cache"}


def main() -> int:
    removed = 0
    for pattern in FILE_PATTERNS:
        for path in REPO_ROOT.glob(pattern):
            if path.is_file():
                path.unlink()
                print(f"removed {path.relative_to(REPO_ROOT)}")
                removed += 1

    for path in REPO_ROOT.rglob("*"):
        if path.is_dir() and path.name in DIR_NAMES and ".venv" not in path.parts:
            shutil.rmtree(path, ignore_errors=True)
            removed += 1

    print(f"clean: removed {removed} item(s). Committed evidence untouched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
