"""The publication gate: functions 6 (governance) and 7 (dissemination).

Run this before making a repo public or putting its URL in an application. It
encodes the failure modes that are individually trivial and collectively decide
whether anyone can use, cite, or build on your work:

    no LICENSE          -> legally all-rights-reserved; nobody may fork it
    no CITATION.cff     -> no machine-readable attribution, no "Cite this repository"
    placeholders left   -> the repo says "Untitled Research Project"
    no figures          -> a reader who will not clone sees no evidence at all
    paper PDF, no source-> the paper cannot be amended, forked, or diffed
    unresolved claims   -> a number in the writeup with nothing behind it
    oversized history   -> the first push to a public remote hangs

Every item here is fixable in minutes. The point is that they are invisible until
something checks, and by then the deadline has passed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from lab import size  # noqa: E402

PLACEHOLDERS = [
    "scaffold-project",
    "Untitled Research Project",
    "A research project. Replace this line via `just init`.",
    "{{YEAR}}",
    "{{DATE}}",
]

SCANNED = ["README.md", "AGENTS.md", "CITATION.cff", "pyproject.toml", "LICENSE"]


def _fail(problems: list[str], msg: str) -> None:
    problems.append(msg)


def check_governance(problems: list[str]) -> None:
    if not (REPO_ROOT / "LICENSE").exists():
        _fail(problems, "LICENSE is missing — the repo is legally all-rights-reserved.")
    cff = REPO_ROOT / "CITATION.cff"
    if not cff.exists():
        _fail(problems, "CITATION.cff is missing — no machine-readable attribution.")
    elif "REPLACE" in cff.read_text(encoding="utf-8"):
        _fail(problems, "CITATION.cff still contains REPLACE markers.")

    if (REPO_ROOT / ".env").exists():
        try:
            tracked = subprocess.check_output(
                ["git", "ls-files", ".env"],
                cwd=REPO_ROOT,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            if tracked:
                _fail(problems, "CRITICAL: .env is tracked by git. Secrets may be published.")
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass


def check_placeholders(problems: list[str]) -> None:
    for rel in SCANNED:
        path = REPO_ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for ph in PLACEHOLDERS:
            if ph in text:
                _fail(problems, f"{rel}: placeholder still present: {ph!r} — run `just init`.")


def check_dissemination(problems: list[str]) -> None:
    figures_dir = REPO_ROOT / "figures"
    figures = list(figures_dir.glob("*.png")) if figures_dir.exists() else []
    if not figures:
        _fail(problems, "figures/ is empty — a reader who will not clone sees no evidence.")

    writeup = REPO_ROOT / "writeup"
    if writeup.exists():
        pdfs = list(writeup.glob("*.pdf"))
        sources = (
            list(writeup.glob("*.md")) + list(writeup.glob("*.typ")) + list(writeup.glob("*.tex"))
        )
        if pdfs and not sources:
            _fail(problems, "writeup/ has a PDF but no source — the paper cannot be amended.")
        if not sources:
            _fail(problems, "writeup/ has no paper source.")

    readme = REPO_ROOT / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        if "![" not in text:
            _fail(problems, "README.md embeds no figure — the headline result is invisible.")
        if len(text.split()) < 120:
            _fail(problems, "README.md is very short — it should state the claim, not the setup.")


def report_size(problems: list[str]) -> None:
    """Report repository size and the ten largest tracked blobs.

    This script's whole purpose is "run before making the repo public", and size
    is exactly the class of problem that is invisible locally and fatal remotely:
    the failure that motivated `lab.size` showed up as a push that hung. Printing
    the ten largest blobs unconditionally — not only on failure — is deliberate.
    A reader glancing at the list notices a checkpoint nobody meant to commit long
    before it trips a threshold.
    """
    if not size.is_git_repo():
        print("size: not a git repo yet — skipping size report.")
        return

    store = size.object_store_bytes()
    if store is not None:
        print(f"size: .git object store is {size.human(store)}")

    largest = size.largest_tracked(10)
    if largest:
        print("size: ten largest tracked blobs")
        for path, nbytes in largest:
            marker = "  !! " if nbytes > size.MAX_BLOB_BYTES else "     "
            print(f"{marker}{size.human(nbytes):>9}  {path}")

    problems.extend(size.problems())


def check_claims(problems: list[str]) -> None:
    """Reuse the standing linter rather than duplicating its logic."""
    result = subprocess.run(
        [sys.executable, "-m", "lab.check"], cwd=REPO_ROOT, capture_output=True, text=True
    )
    if result.returncode != 0:
        _fail(problems, "`just check` fails — claims or repo map cite paths that do not exist.")


def main() -> int:
    problems: list[str] = []
    check_governance(problems)
    check_placeholders(problems)
    check_dissemination(problems)
    report_size(problems)
    check_claims(problems)

    if problems:
        print(f"publish-check: NOT READY ({len(problems)} problem(s))\n", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print("\nSee docs/publish-checklist.md in the scaffold for the reasoning.", file=sys.stderr)
        return 1

    print("publish-check: READY — licensed, citable, illustrated, and every claim resolves.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
