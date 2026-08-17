"""Reconstruct what produced a set of records, from the records themselves.

This module exists because of a real production failure. The manifest was written
by `run.py`, but a remote job launcher bypassed `run.py` — so a stale manifest
labelled real 7B-model output as synthetic. Nothing crashed. Every number computed
afterwards inherited the mislabelling.

The fix is not "remember to update the manifest". It is to stop treating the
manifest as authoritative:

    derive(rows)              what the DATA says produced it
    manifest["provenance"]    what the WRITER said produced it
    disagreement              -> fatal, always

A manifest that agrees with its records is a useful summary. A manifest that
disagrees is a bug that has already happened, and the only safe response is to
refuse to compute.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence

from lab.core.backend import PROVENANCE_FIELDS


class ProvenanceError(ValueError):
    """Raised when records disagree with each other or with the manifest."""


def derive(rows: Iterable[dict], *, fields: Sequence[str] = PROVENANCE_FIELDS) -> dict[str, str]:
    """The single provenance shared by every record, or raise.

    Every record must carry the same backend, model and dtype. Two backends in one
    file means the file is a concatenation of two runs, and any rate computed
    across it is a rate over a population that never existed.
    """
    rows = list(rows)
    if not rows:
        raise ProvenanceError("cannot derive provenance from zero records")

    derived: dict[str, str] = {}
    for f in fields:
        values = Counter(str(r.get(f)) for r in rows)
        if None in (r.get(f) for r in rows) or "None" in values:
            missing = sum(1 for r in rows if r.get(f) is None)
            raise ProvenanceError(
                f"{missing}/{len(rows)} records carry no {f!r}. Records must be stamped "
                f"at the point of measurement — see lab.core.backend.Backend.stamp()."
            )
        if len(values) > 1:
            spread = ", ".join(f"{v}x{c}" for v, c in values.most_common())
            raise ProvenanceError(
                f"records disagree on {f!r}: {spread}. This file mixes runs; "
                f"split it by {f!r} before analysing."
            )
        derived[f] = next(iter(values))
    return derived


def compare(derived: dict[str, str], claimed: dict[str, str] | None) -> list[str]:
    """Field-by-field disagreements between the data and the manifest."""
    if not claimed:
        return []
    problems = []
    for f, actual in derived.items():
        if f in claimed and str(claimed[f]) != actual:
            problems.append(f"manifest says {f}={claimed[f]!r} but records say {actual!r}")
    return problems


def verify(rows: Iterable[dict], manifest: dict | None = None) -> dict[str, str]:
    """Derive provenance and assert the manifest agrees. Returns the derived truth.

    Call this before computing anything. It is the check that would have caught
    the failure this module is named for.
    """
    derived = derive(rows)
    problems = compare(derived, (manifest or {}).get("provenance"))
    if problems:
        raise ProvenanceError(
            "manifest disagrees with the records it describes:\n  "
            + "\n  ".join(problems)
            + "\n\nThe records are the evidence; the manifest is a summary of them. "
            "Regenerate the manifest, or find out which execution path wrote these "
            "records without going through run.py."
        )
    return derived


def is_reportable(manifest: dict | None) -> bool:
    """Whether numbers from this run may be quoted as results.

    A stub or reduced-precision backend produces leads, not results. Reports
    should state which they are showing.
    """
    return bool((manifest or {}).get("backend", {}).get("reportable", False))
