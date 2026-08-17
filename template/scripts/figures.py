"""Regenerate every committed figure by re-running each experiment's analyze.py.

Figures are committed so the README can show the result to someone who will never
clone the repo. They must therefore be reproducible on demand, not hand-exported
from a notebook that no longer exists.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    analyzers = sorted(REPO_ROOT.glob("experiments/*/analyze.py"))
    analyzers = [a for a in analyzers if a.parent.name != "_template"]

    if not analyzers:
        print("figures: no experiments/*/analyze.py found.")
        return 0

    failed = []
    for script in analyzers:
        rel = script.relative_to(REPO_ROOT)
        result = subprocess.run([sys.executable, str(script)], cwd=REPO_ROOT)
        if result.returncode != 0:
            failed.append(str(rel))
        print(f"figures: {'FAILED' if result.returncode else 'ok'} {rel}")

    if failed:
        print(f"\nfigures: {len(failed)} analyzer(s) failed: {', '.join(failed)}", file=sys.stderr)
        print("If the raw records are gone, re-run the corresponding run.py.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
