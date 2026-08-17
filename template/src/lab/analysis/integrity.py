"""Verify the measured data before you compute anything from it.

The premise: **you cannot do research without first establishing that the data you
measured is the data you think you measured.** Almost every embarrassing retraction
in small-scale empirical work traces to one of six things, and all six are
mechanically checkable:

0. The records did not come from what you believe produced them. A second
   execution path — a remote launcher, a resumed job — wrote records without
   going through the code that wrote the manifest, so the metadata describes a
   run that did not happen. Nothing crashes; every number inherits the error.
1. Records are missing a field you later group by.
2. Records silently dropped — a retry loop swallowed a failure, so one arm has
   n=47 where you believe n=50, and your "effect" is the missing three.
3. Duplicate records — a resumed run re-appended, and n is inflated.
4. A categorical field contains a value you did not expect (`"ERROR"`, `""`, `None`)
   that your analysis is quietly counting as a level.
5. Arms are unbalanced in a way you did not intend.

Call `check_records(...)` at the top of every `analyze.py`, before any statistic.
It costs milliseconds and it is the difference between a null result and an
undetected bug that looks like one.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from lab.core import provenance


@dataclass
class Issue:
    severity: str  # "error" | "warning"
    code: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.code}: {self.message}"


@dataclass
class IntegrityReport:
    n_records: int
    issues: list[Issue] = field(default_factory=list)
    cells: dict[str, int] = field(default_factory=dict)
    #: What the records themselves say produced them. None if unstamped.
    provenance: dict[str, str] | None = None

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        origin = ""
        if self.provenance:
            origin = " from " + "/".join(str(v) for v in self.provenance.values())
        lines = [
            f"integrity: {self.n_records} records{origin}, "
            f"{len(self.errors)} error(s), {len(self.warnings)} warning(s)"
        ]
        lines += [f"  {i}" for i in self.issues]
        return "\n".join(lines)

    def raise_if_failed(self) -> IntegrityReport:
        """Stop the analysis rather than computing a statistic on broken data."""
        if not self.ok:
            raise ValueError("Data integrity check failed:\n" + self.summary())
        return self

    def to_dict(self) -> dict:
        """For embedding in summary.json, so the report carries its own audit."""
        return {
            "n_records": self.n_records,
            "ok": self.ok,
            "provenance": self.provenance,
            "cells": self.cells,
            "issues": [
                {"severity": i.severity, "code": i.code, "message": i.message} for i in self.issues
            ],
        }


def _check_provenance(rows: list[dict], manifest: dict | None, report: IntegrityReport) -> None:
    """Derive origin from the data and confront the manifest with it.

    Three outcomes:
      * records unstamped        -> warning (legacy data, or a backend that
                                    predates the stamping convention)
      * records disagree         -> error (the file mixes runs)
      * records vs manifest      -> error (a code path bypassed run.py)

    The third is the one that actually happened: a remote launcher produced real
    model output while a stale manifest described it as synthetic.
    """
    try:
        derived = provenance.derive(rows)
    except provenance.ProvenanceError as exc:
        message = str(exc).splitlines()[0]
        severity = "warning" if "carry no" in message else "error"
        code = "provenance_missing" if severity == "warning" else "provenance_conflict"
        report.issues.append(Issue(severity, code, message))
        return

    report.provenance = derived

    if manifest is None:
        return
    if manifest.get("provenance") is None:
        report.issues.append(
            Issue(
                "warning",
                "provenance_unverifiable",
                "manifest records no provenance, so it cannot be cross-checked; "
                "pass backend= to manifest.write()",
            )
        )
        return
    for problem in provenance.compare(derived, manifest["provenance"]):
        report.issues.append(Issue("error", "provenance_mismatch", problem))


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and value != value:  # NaN
        return True
    return isinstance(value, str) and not value.strip()


def check_records(
    rows: Iterable[dict],
    *,
    required: Sequence[str] = (),
    categorical: dict[str, Sequence[object]] | None = None,
    unique_key: str | Sequence[str] | None = None,
    group_by: Sequence[str] = (),
    expected_per_cell: int | None = None,
    manifest: dict | None = None,
) -> IntegrityReport:
    """Structural and provenance checks on measurement records.

    Args:
        rows: the records, as loaded from JSONL.
        required: fields that must be present and non-missing in every record.
        categorical: field -> allowed values. Anything else is an error.
        unique_key: field (or tuple of fields) that must not repeat.
        group_by: fields defining a cell, e.g. ("arm", "prompt_id").
        expected_per_cell: if set, every cell must have exactly this many records.
        manifest: the run's manifest. When given, the provenance stamped into the
            records must agree with it — a mismatch is fatal, because it means
            some execution path wrote records without going through the code that
            wrote the manifest.

    Returns:
        An IntegrityReport. Call `.raise_if_failed()` to make it blocking.
    """
    rows = list(rows)
    report = IntegrityReport(n_records=len(rows))

    if not rows:
        report.issues.append(Issue("error", "empty", "no records found"))
        return report

    # 0. Provenance. Run first: if the data is not what the manifest claims it is,
    #    nothing computed below means anything.
    _check_provenance(rows, manifest, report)

    # 1 + 2. Required fields present and populated.
    for f in required:
        absent = sum(1 for r in rows if f not in r)
        empty = sum(1 for r in rows if f in r and _is_missing(r[f]))
        if absent:
            report.issues.append(
                Issue("error", "missing_field", f"{absent}/{len(rows)} records lack {f!r}")
            )
        if empty:
            report.issues.append(
                Issue("error", "empty_value", f"{empty}/{len(rows)} records have empty {f!r}")
            )

    # 3. Duplicates.
    if unique_key:
        keys = (unique_key,) if isinstance(unique_key, str) else tuple(unique_key)
        seen = Counter(tuple(r.get(k) for k in keys) for r in rows)
        dupes = {k: c for k, c in seen.items() if c > 1}
        if dupes:
            example = next(iter(dupes))
            report.issues.append(
                Issue(
                    "error",
                    "duplicate_key",
                    f"{len(dupes)} duplicated value(s) of {keys}, e.g. {example} x{dupes[example]}",
                )
            )

    # 4. Unexpected categorical levels.
    for f, allowed in (categorical or {}).items():
        allowed_set = set(allowed)
        seen_vals = {r.get(f) for r in rows}
        unexpected = seen_vals - allowed_set
        if unexpected:
            report.issues.append(
                Issue(
                    "error",
                    "unexpected_level",
                    f"field {f!r} contains unexpected value(s): {sorted(map(repr, unexpected))}",
                )
            )

    # 5. Cell completeness — the check that catches silently dropped records.
    if group_by:
        counts = Counter(" | ".join(f"{g}={r.get(g)}" for g in group_by) for r in rows)
        report.cells = dict(sorted(counts.items()))
        if expected_per_cell is not None:
            short = {c: n for c, n in counts.items() if n != expected_per_cell}
            for cell, n in sorted(short.items()):
                report.issues.append(
                    Issue(
                        "error",
                        "incomplete_cell",
                        f"cell [{cell}] has n={n}, expected {expected_per_cell}",
                    )
                )
        elif len(set(counts.values())) > 1:
            lo, hi = min(counts.values()), max(counts.values())
            report.issues.append(
                Issue(
                    "warning",
                    "unbalanced_cells",
                    f"cell sizes range {lo}..{hi}; unbalanced arms weaken every comparison",
                )
            )

    return report
