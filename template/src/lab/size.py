"""Repository size guard: catch a large blob before it reaches history.

Why this exists, precisely. A `.gitignore` gap put 894 MB of raw activation
tensors into git history during a 3-day sprint. Nothing noticed. It surfaced when
the first push to a public remote hung, hours before a deadline, and recovery
meant `git-filter-repo` and a force-push on a repo other people had already been
told about.

The asymmetry is the whole argument for this file. Catching an oversized blob
*before* it is committed costs one `git rm --cached`. Catching it ten commits
later costs a history rewrite, and every clone anyone made is now wrong. The
check is cheap and runs on every `just check`; the failure it prevents is
expensive and runs on a deadline.

`.gitignore` is the primary defence and this is the backstop. They fail
differently on purpose: the ignore rules deny by content pattern under experiment
output directories, while this notices size wherever it appears — a 40 MB PDF in
`writeup/`, a CSV committed from the repo root, a model checkpoint saved somewhere
nobody predicted.

Thresholds are constants, not configuration. If a project genuinely needs to
commit something larger, raising the number here is a deliberate, reviewable,
one-line edit — which is the right amount of friction.
"""

from __future__ import annotations

import subprocess

from lab.core.paths import REPO_ROOT

MB = 1024 * 1024

#: Any single tracked or staged blob above this fails the check. GitHub warns at
#: 50 MB and hard-refuses at 100 MB, but those are the wrong thresholds to design
#: against: by the time a 50 MB file is refused it is already in your history.
MAX_BLOB_BYTES = 5 * MB

#: Total object store above this fails the check. A research repo that is not
#: shipping binaries has no business being this large, so crossing it means
#: something is being committed that should not be.
MAX_GIT_BYTES = 100 * MB


def human(n: int) -> str:
    """Bytes as something a person can act on."""
    if n >= MB:
        return f"{n / MB:.1f} MB"
    if n >= 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n} B"


def _git(*args: str, stdin: str | None = None) -> str | None:
    """Run a git command in the repo. None if git is absent or this is not a repo.

    Returning None rather than raising matters: a freshly copied template is not
    a git repo yet, and `just check` must still work there. A guard that explodes
    on a clean checkout gets deleted, and then it guards nothing.
    """
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, FileNotFoundError):
        return None
    return result.stdout if result.returncode == 0 else None


def is_git_repo() -> bool:
    return _git("rev-parse", "--git-dir") is not None


def indexed_blob_sizes() -> dict[str, int]:
    """Map path -> blob size for everything in the index.

    The index is both what is tracked and what is staged, so one pass covers the
    "already committed" and "about to be committed" cases. Sizes come from the
    object store rather than the working tree, so this is the size git will
    actually carry, not the size on disk.
    """
    listing = _git("ls-files", "-s", "-z")
    if not listing:
        return {}

    by_sha: dict[str, list[str]] = {}
    for entry in listing.split("\0"):
        if not entry or "\t" not in entry:
            continue
        meta, path = entry.split("\t", 1)
        parts = meta.split()
        if len(parts) < 2:
            continue
        by_sha.setdefault(parts[1], []).append(path)

    if not by_sha:
        return {}

    # One batch call rather than one process per file: a repo with a few thousand
    # tracked files would otherwise make `just check` noticeably slow, and a slow
    # check is a check people stop running.
    batch = _git("cat-file", "--batch-check", stdin="\n".join(by_sha) + "\n")
    if not batch:
        return {}

    sizes: dict[str, int] = {}
    for line in batch.splitlines():
        fields = line.split()
        if len(fields) != 3 or fields[1] != "blob":
            continue
        sha, _, raw_size = fields
        for path in by_sha.get(sha, []):
            sizes[path] = int(raw_size)
    return sizes


def largest_tracked(n: int = 10) -> list[tuple[str, int]]:
    """The n largest tracked blobs, biggest first."""
    sizes = indexed_blob_sizes()
    return sorted(sizes.items(), key=lambda kv: kv[1], reverse=True)[:n]


def object_store_bytes() -> int | None:
    """Size of the git object store, loose + packed. None if not a repo.

    Uses `git count-objects` rather than walking `.git`, which is both faster and
    the number git itself reports.
    """
    out = _git("count-objects", "-v")
    if out is None:
        return None
    total_kib = 0
    for line in out.splitlines():
        key, _, value = line.partition(":")
        if key.strip() in {"size", "size-pack"}:
            try:
                total_kib += int(value.strip())
            except ValueError:
                continue
    return total_kib * 1024


REWRITE_NOTE = (
    "Note: `git rm --cached <path>` unstages the file but does NOT shrink history "
    "if it was already committed. Removing it from history needs a rewrite "
    "(git-filter-repo) and a force-push, which invalidates every existing clone. "
    "That is why this check runs before the commit rather than after the push."
)


def problems() -> list[str]:
    """Human-readable size problems. Empty list means clean.

    Returns problems only. `REWRITE_NOTE` is the caller's to print as a footer —
    folding it in here would make one oversized file report as "2 problems", and
    a checker that cannot count is a checker people stop believing.
    """
    if not is_git_repo():
        return []

    found: list[str] = []

    oversized = sorted(
        ((p, s) for p, s in indexed_blob_sizes().items() if s > MAX_BLOB_BYTES),
        key=lambda kv: kv[1],
        reverse=True,
    )
    for path, size in oversized:
        found.append(
            f"{path}: {human(size)} exceeds the {human(MAX_BLOB_BYTES)} blob limit. "
            f"If it is regenerable output, add it to .gitignore and `git rm --cached` it."
        )

    store = object_store_bytes()
    if store is not None and store > MAX_GIT_BYTES:
        found.append(
            f".git object store is {human(store)}, over the {human(MAX_GIT_BYTES)} limit. "
            f"Something large is in history — run `just publish-check` for the ten "
            f"largest tracked blobs."
        )

    return found
