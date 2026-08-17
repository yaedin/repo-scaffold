"""Per-run provenance, so a results directory is self-describing.

Every `run.py` writes one of these next to its records. It captures the things
that actually change a number — the commit, the seed, the installed versions, the
device, and the run parameters — so that six weeks later you can tell whether two
directories disagree because the code changed or because the draw did.

This is not a lockfile. `uv.lock` is the lockfile. This is the receipt.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

from lab.core.backend import Backend
from lab.core.paths import REPO_ROOT

# Packages whose version plausibly changes a result. Extend per project.
TRACKED_PACKAGES = ["numpy", "matplotlib"]


def git_sha(short: bool = False) -> str | None:
    """Current commit, or None outside a git repo."""
    cmd = ["git", "rev-parse", "--short" if short else "HEAD"]
    try:
        return subprocess.check_output(
            cmd, cwd=REPO_ROOT, stderr=subprocess.DEVNULL, text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def git_dirty() -> bool | None:
    """True if the working tree has uncommitted changes.

    A dirty tree means the recorded SHA does not fully describe the code that ran.
    The manifest records it rather than refusing, but a dirty flag on a number you
    intend to publish is a defect.
    """
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=REPO_ROOT, stderr=subprocess.DEVNULL, text=True
        )
        return bool(out.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _versions() -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for pkg in TRACKED_PACKAGES:
        try:
            out[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            out[pkg] = None
    return out


def _device() -> str:
    try:
        import torch
    except ImportError:
        return "cpu"
    if torch.cuda.is_available():
        return f"cuda:{torch.cuda.get_device_name(0)}"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def build(
    params: dict | None = None,
    *,
    seed: int | None = None,
    backend: Backend | None = None,
) -> dict:
    """Assemble the manifest dict without writing it.

    `provenance` duplicates the stamp written into every record on purpose. That
    redundancy is the point: `lab.core.provenance.verify` compares the two and
    refuses to proceed when they disagree, which is how a manifest written by a
    bypassed code path gets caught instead of quietly poisoning the analysis.
    """
    return {
        "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_sha": git_sha(),
        "git_dirty": git_dirty(),
        "seed": seed,
        "provenance": backend.stamp() if backend else None,
        "backend": backend.describe() if backend else None,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "device": _device(),
        "versions": _versions(),
        "params": params or {},
    }


def write(
    outdir: Path | str,
    params: dict | None = None,
    *,
    seed: int | None = None,
    backend: Backend | None = None,
) -> Path:
    """Write `manifest.json` into `outdir` and return its path.

    Pass the `backend` that produced the records. Omitting it is allowed but means
    the manifest cannot be cross-checked, which is the situation this scaffold
    exists to prevent — `check_records` will warn.
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / "manifest.json"
    path.write_text(
        json.dumps(build(params, seed=seed, backend=backend), indent=2) + "\n", encoding="utf-8"
    )
    return path


def read(outdir: Path | str) -> dict:
    return json.loads((Path(outdir) / "manifest.json").read_text(encoding="utf-8"))
