"""Fail the build when the repo's own documentation stops being true.

Three failure modes this exists to prevent, all observed in the wild:

**A claim with no source.** A number reaches the paper, and by the time anyone
asks which script produced it, nobody can say. `CLAIMS.md` binds every claim to a
producing script and an output artifact; this linter verifies those paths exist.
The ledger then maintains itself under deadline pressure, because a claim you
cannot back fails `just check` immediately rather than during review.

**A claim that has drifted from its source.** Existence is not agreement. You
rerun an experiment, the effect moves, and the ledger still quotes the old number
— every path resolves, so the linter stays green while the ledger lies. An
artifact citation may therefore carry a JSON pointer, and the quoted value is
checked against what the artifact actually contains.

**A repo map that has drifted.** `AGENTS.md` tells an agent where things live. A
stale map is worse than no map: an agent will act on it confidently. Every path
cited in `AGENTS.md` must resolve, or this fails.

**A large blob reaching history.** Cheap to prevent, expensive to undo — see
`lab.size` for the incident that motivated it.

Escape hatch: put `<!-- check:ignore -->` at the end of a line to skip it.

Run with `just check` or `uv run python -m lab.check`.
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

from lab import size
from lab.core.paths import REPO_ROOT

BACKTICKED = re.compile(r"`([^`]+)`")
IGNORE_MARKER = "<!-- check:ignore -->"

# Tokens that look like paths but are commands or placeholders.
COMMAND_PREFIXES = ("just ", "uv ", "git ", "python ", "pytest ", "ruff ")
PLACEHOLDER_CHARS = set("*?{}<>$|")


def _strip_pointer(token: str) -> str:
    """`a/b.json#x.y` -> `a/b.json`. Pointer citations are still path citations."""
    return token.split("#", 1)[0]


def looks_like_path(token: str) -> bool:
    """Conservative: a token counts as a path only if it contains a separator.

    A bare `run.py` or `RESULTS.md` in prose is almost always generic — "each
    experiment has a `run.py`" — not a reference to a file at the repo root.
    Requiring a `/` costs almost nothing (real references are nearly always
    qualified) and removes the largest class of false positives. A linter that
    cries wolf gets disabled, and then it protects nothing.
    """
    token = token.strip()
    if not token or " " in token or "/" not in token:
        return False
    if token.startswith(COMMAND_PREFIXES):
        return False
    if PLACEHOLDER_CHARS & set(token):
        return False
    return not token.startswith(("http://", "https://"))


def _strip_html_comments(markdown: str) -> list[str]:
    """Blank out HTML comment blocks, preserving line numbering.

    Commented-out template rows are examples, not claims — they cite paths that
    are meant not to exist yet.
    """
    lines = markdown.splitlines()
    inside = False
    out = []
    for line in lines:
        opens, closes = "<!--" in line, "-->" in line
        if inside or opens:
            out.append("")
            inside = not closes if (inside or opens) else inside
            if opens and closes:
                inside = False
        else:
            out.append(line)
    return out


def paths_in(markdown: str) -> list[tuple[int, str]]:
    """Every path-like backticked token, with its 1-indexed line number."""
    found: list[tuple[int, str]] = []
    for lineno, line in enumerate(_strip_html_comments(markdown), start=1):
        if IGNORE_MARKER in line:
            continue
        for token in BACKTICKED.findall(line):
            # A directory is written with a trailing slash; strip it for the check.
            candidate = _strip_pointer(token).rstrip("/")
            if looks_like_path(candidate):
                found.append((lineno, candidate))
    return found


def check_file(relpath: str) -> list[str]:
    """Return a list of human-readable problems for one markdown file."""
    path = REPO_ROOT / relpath
    if not path.exists():
        return [f"{relpath}: file is missing"]

    problems = []
    for lineno, cited in paths_in(path.read_text(encoding="utf-8")):
        if not (REPO_ROOT / cited).exists():
            problems.append(f"{relpath}:{lineno}: cited path does not exist: {cited}")
    return problems


def _claim_rows() -> list[tuple[int, str, list[str]]]:
    """(lineno, raw line, cells) for each data row under `## Claims`.

    Only that table is checked. The status-vocabulary and retractions tables
    elsewhere in the file are documentation, not claims.
    """
    path = REPO_ROOT / "CLAIMS.md"
    rows = []
    in_claims_section = False
    for lineno, line in enumerate(_strip_html_comments(path.read_text(encoding="utf-8")), start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            in_claims_section = stripped.lower().lstrip("# ").startswith("claims")
            continue
        if not in_claims_section or not stripped.startswith("|") or IGNORE_MARKER in line:
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        first = cells[0] if cells else ""
        # Skip the header row, the |---|---| separator, and empty placeholder rows.
        if not first or set(first) <= set("-:— ") or first.lower() in {"#", "id", "claim"}:
            continue
        rows.append((lineno, line, cells))
    return rows


def check_claims_have_sources() -> list[str]:
    """Every claim row must cite at least one path."""
    if not (REPO_ROOT / "CLAIMS.md").exists():
        return ["CLAIMS.md: file is missing"]

    problems = []
    for lineno, line, cells in _claim_rows():
        if not any(
            looks_like_path(_strip_pointer(t).rstrip("/")) for t in BACKTICKED.findall(line)
        ):
            problems.append(
                f"CLAIMS.md:{lineno}: claim {cells[0]!r} cites no producing script or artifact"
            )
    return problems


# --- claim values must match the artifacts they point at ----------------------
#
# Checking that a cited file EXISTS is necessary and not sufficient. A number can
# drift from its artifact silently: you rerun an experiment, the effect moves from
# +14.4pp to +9.1pp, and CLAIMS.md still says +14.4pp because nothing forces it to
# change. Every path still resolves, so the linter stays green while the ledger is
# lying — which is the exact failure the ledger exists to prevent.
#
# The fix: an artifact citation may carry a JSON pointer,
#
#     `experiments/e00_smoke/output/summary.json#comparisons.main.delta`
#
# and the linter resolves it, then asserts the resolved value is present in the
# row's Number cell. Rows with no pointer are still allowed — not everything is a
# scalar — but a pointer, once added, cannot silently go stale.

POINTER = re.compile(r"^([^#]+)#(.+)$")
NUMERIC = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")

#: A value quoted to 1dp as a percentage is not identical to the stored float, so
#: matching is tolerant. Loose enough for "+14.4pp" vs 0.14375, tight enough that
#: a genuine change of result cannot slip through.
REL_TOL = 0.03
ABS_TOL = 0.06


def resolve_pointer(json_path: Path, dotted: str) -> float | None:
    """Walk a dotted path into a JSON document. None if it does not resolve."""
    try:
        node = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    for part in dotted.split("."):
        if isinstance(node, list):
            try:
                node = node[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return float(node) if isinstance(node, (int, float)) and not isinstance(node, bool) else None


def value_is_quoted(resolved: float, cell: str) -> bool:
    """Does `cell` quote `resolved`, in any of the forms people actually write?

    Accepts the raw value, the percentage form, and either sign — so 0.14375 is
    satisfied by "+14.4pp", "14.4%", or "0.144".
    """
    candidates = {resolved, resolved * 100, abs(resolved), abs(resolved) * 100}
    found = [float(m) for m in NUMERIC.findall(cell)]
    return any(
        math.isclose(n, c, rel_tol=REL_TOL, abs_tol=ABS_TOL) for c in candidates for n in found
    )


def check_claim_values() -> list[str]:
    """Every JSON pointer in CLAIMS.md must resolve, and match the quoted number."""
    if not (REPO_ROOT / "CLAIMS.md").exists():
        return []

    problems = []
    for lineno, line, cells in _claim_rows():
        # The Number cell is the second column by convention; fall back to the
        # whole row so a reordered table degrades to permissive rather than wrong.
        number_cell = cells[2] if len(cells) > 2 else line

        for token in BACKTICKED.findall(line):
            match = POINTER.match(token.strip())
            if not match:
                continue
            rel, dotted = match.group(1), match.group(2)
            target = REPO_ROOT / rel

            if not target.exists():
                problems.append(f"CLAIMS.md:{lineno}: cited artifact does not exist: {rel}")
                continue

            resolved = resolve_pointer(target, dotted)
            if resolved is None:
                problems.append(
                    f"CLAIMS.md:{lineno}: {dotted!r} does not resolve to a number in {rel}"
                )
                continue

            if not value_is_quoted(resolved, number_cell):
                problems.append(
                    f"CLAIMS.md:{lineno}: claim {cells[0]!r} quotes {number_cell!r} but "
                    f"{rel}#{dotted} is {resolved:.6g} — the ledger has drifted from the artifact"
                )
    return problems


def main() -> int:
    problems: list[str] = []
    problems += check_file("AGENTS.md")
    problems += check_file("CLAIMS.md")
    problems += check_file("README.md")
    problems += check_claims_have_sources()
    problems += check_claim_values()

    # Kept separate so the closing advice can match the failure. "Retract the
    # claim" is useless guidance for a 40 MB checkpoint.
    size_problems = size.problems()

    if problems or size_problems:
        total = len(problems) + len(size_problems)
        print(f"check: FAILED ({total} problem(s))\n", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        for p in size_problems:
            print(f"  {p}", file=sys.stderr)
        if problems:
            print(
                "\nEither fix the path, or produce the artifact, or retract the claim.",
                file=sys.stderr,
            )
        if size_problems:
            print(f"\n{size.REWRITE_NOTE}", file=sys.stderr)
        return 1

    print("check: OK — paths resolve, claims have sources, quoted values match their artifacts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
