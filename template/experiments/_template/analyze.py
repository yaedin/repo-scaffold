"""E<NN> — records in, report out. No number in RESULTS.md is typed by hand.

Rules this file follows (see AGENTS.md):
  * Integrity-check BEFORE computing anything, and raise on failure. Pass
    manifest= so the records are confronted with what the manifest claims.
  * Every rate gets an interval.
  * Include a comparison that should come out null.
  * Generate summary.json and RESULTS.md. Regenerate; never hand-edit.

Copy experiments/e00_smoke/analyze.py for a version that actually runs.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from lab import figstyle  # noqa: E402
from lab.analysis import check_records  # noqa: E402
from lab.core import manifest, records  # noqa: E402
from lab.core.paths import RunPaths  # noqa: E402

EXPERIMENT = "eNN_slug"  # TODO
ARMS = ["control", "treatment"]  # TODO


def make_figure(paths: RunPaths, comparisons: dict[str, dict]) -> list[Path]:
    """One figure, from the same numbers as the report.

    Always go through `lab.figstyle`. It supplies a colour-vision-safe palette
    paired with marker shapes, sizes in inches matched to text width, and PDF+PNG
    output — none of which you want to re-decide per experiment, and all of which
    matplotlib's defaults get wrong for a paper.
    """
    plt = figstyle.use()
    fig, ax = plt.subplots(figsize=(figstyle.WIDTH_HALF, 2.4))

    for i, (name, c) in enumerate(comparisons.items()):
        colour, marker = figstyle.series(i)
        ax.plot([i], [c["delta"]], marker=marker, color=colour, label=name)

    ax.axhline(0, color=figstyle.OKABE_ITO["black"], linewidth=0.6)
    ax.set_ylabel("Δ")  # TODO: name the measurement
    ax.set_title(f"{EXPERIMENT} — effect by comparison")

    written = figstyle.save(fig, figstyle.FIGURES_DIR, f"{EXPERIMENT}_effects")
    plt.close(fig)
    return written


def render_comparisons(comparisons: dict[str, dict]) -> str:
    """Render one table row per comparison, driven off the comparisons dict itself.

    THIS IS THE PATTERN. Copy it. Any table in generated output whose rows are
    written out by hand is a latent version of the following bug.

    In the sprint this scaffold was built from, an analysis computed seven model
    effects and its RESULTS.md writer had six hardcoded rows. The missing effect
    (M×I, p = 2.9e-76) was the most significant one in the table. Every check in
    this repo stayed green — the ledger cited a path that existed, the number it
    quoted matched the artifact, the integrity report passed — because none of
    them can see a row that was never written. It reached the submitted paper and
    was caught by a human counting rows against a sentence that said "seven
    effects".

    A hardcoded table does not drift when you edit it. It drifts when you edit
    something ELSE — the analysis grows an eighth effect and the table silently
    keeps showing seven. That is why the fix is structural rather than a matter of
    remembering: the row list and the result list are the same list.

    The assertion below is the second half of the pattern. Iteration alone can
    still lose a row to a filter or a `continue` added later, so the invariant
    "as many rows as results" is stated once, here, where it is cheap.
    """
    if not comparisons:
        return "_No comparisons computed yet._"

    header = "| Comparison | Δ | z | p |\n|---|---|---|---|"
    body = [
        f"| `{name}` | {c['delta']:+.1%} | {c['z']:.2f} | {c['p_value']:.2g} |"
        for name, c in comparisons.items()
    ]
    assert len(body) == len(comparisons), "a comparison was computed but not rendered"
    return "\n".join([header, *body])


def main() -> int:
    paths = RunPaths(EXPERIMENT)
    if not paths.records.exists():
        print(
            f"analyze: no records at {paths.rel(paths.records)}. Run run.py first.", file=sys.stderr
        )
        return 1

    rows = records.read(paths.records)
    man = manifest.read(paths.output)

    report = check_records(
        rows,
        required=["record_id", "arm", "item_id"],  # TODO: add the measurement field
        categorical={"arm": ARMS},
        unique_key="record_id",
        group_by=["arm", "item_id"],
        expected_per_cell=man["params"]["n_replicates"],
        manifest=man,  # fatal if the records disagree with what wrote them
    )
    print(report.summary())
    report.raise_if_failed()

    # TODO: compute per-arm rates with wilson_ci, compare with two_proportion_ztest,
    # add a null comparison. See experiments/e00_smoke/analyze.py.
    #
    # Whatever you compute, put it in ONE dict and let both the summary and the
    # report read from that dict. Do not maintain a second, hand-written list of
    # what to display. See render_comparisons() for why.
    comparisons: dict[str, dict] = {}

    summary = {
        "experiment": EXPERIMENT,
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_sha": man["git_sha"],
        "seed": man["seed"],
        "backend": man.get("backend") or {},
        "reportable": bool((man.get("backend") or {}).get("reportable")),
        "n_records": len(rows),
        "integrity": report.to_dict(),
        "comparisons": comparisons,
    }
    records.write_json(paths.summary, summary)

    md = f"""# {EXPERIMENT} — Results

<!-- GENERATED by experiments/{EXPERIMENT}/analyze.py — do not edit by hand. -->

## Comparisons

{render_comparisons(comparisons)}
"""
    paths.results_md.write_text(md, encoding="utf-8")
    print(f"analyze: wrote {paths.rel(paths.summary)}, {paths.rel(paths.results_md)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
